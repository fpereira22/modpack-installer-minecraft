"""
updater_backend.py
Backend del actualizador de modpacks de Minecraft.
Se integra con launcher_frontend.py vía callbacks thread-safe.

Repositorio de configuración y mods:
  https://github.com/fpereira22/modpack-installer-minecraft
"""

import os
import sys
import threading
import subprocess
import requests
import urllib.parse


# ── URL base del repositorio en GitHub (rama main) ──────────────────────────
GITHUB_RAW_BASE = (
    "https://raw.githubusercontent.com/"
    "fpereira22/modpack-installer-minecraft/main"
)
CONFIG_URL = f"{GITHUB_RAW_BASE}/configuracion.json"
MODS_BASE_URL = f"{GITHUB_RAW_BASE}/mods/"


class ModpackUpdaterBackend:
    """
    Clase que maneja toda la lógica de actualización:
      1. Lee configuracion.json desde GitHub.
      2. Verifica / instala Forge.
      3. Sincroniza la carpeta local de mods (descarga faltantes, elimina obsoletos).

    Todos los procesos de red/IO corren en un hilo separado (daemon).
    Se comunica con la UI mediante tres callbacks:
      - progress_cb(valor: float, mensaje: str)
      - finished_cb(exito: bool, mensaje: str)
      - version_cb(version: str)          ← opcional, para mostrar la versión
    """

    def __init__(self, minecraft_dir: str, progress_cb, finished_cb, version_cb=None):
        self.minecraft_dir = minecraft_dir
        self.mods_dir = os.path.join(minecraft_dir, "mods")
        self.versions_dir = os.path.join(minecraft_dir, "versions")
        self.progress_cb = progress_cb
        self.finished_cb = finished_cb
        self.version_cb = version_cb

    # ── Punto de entrada público ─────────────────────────────────────────────
    def start(self):
        """Inicia la actualización en un hilo daemon para no bloquear la UI."""
        thread = threading.Thread(target=self._run_update, daemon=True)
        thread.start()

    # ── Flujo principal (corre en hilo secundario) ───────────────────────────
    def _run_update(self):
        try:
            # Paso 1 ─ Descargar configuracion.json
            self.progress_cb(0.05, "Obteniendo configuración del servidor…")
            config = self._fetch_config()

            forge_version = config.get("forge_version", "")
            forge_installer = config.get("forge_installer", "")
            modpack_version = config.get("modpack_version", "")
            mods_list: list[str] = config.get("mods", [])

            if self.version_cb and modpack_version:
                self.version_cb(modpack_version)

            # Paso 2 ─ Verificar / instalar Forge
            self._check_and_install_forge(forge_version, forge_installer)

            # Paso 3 ─ Sincronizar mods (excluir el installer de la lista de mods)
            self._sync_mods(mods_list, forge_installer)

            self.progress_cb(1.0, "¡Actualización completada!")
            self.finished_cb(True, "Forge y mods listos para jugar.")

        except requests.exceptions.ConnectionError as e:
            print(f"[ERROR RED] No se pudo establecer conexión: {e}")
            self.finished_cb(False, "Error: Sin conexión a internet.")
        except requests.exceptions.Timeout as e:
            print(f"[ERROR TIMEOUT] La solicitud tardó demasiado: {e}")
            self.finished_cb(False, "Error: Tiempo de espera agotado.")
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            print(f"[ERROR HTTP {status}] Error en la solicitud: {e.response.url}")
            if status == 404:
                print(" >> El archivo no fue encontrado. Verifica que el configuracion.json o los mods estén en el repo.")
                self.finished_cb(False, f"Error HTTP 404: No encontrado.")
            elif status >= 500:
                print(" >> Error interno del servidor (GitHub podría estar caído).")
                self.finished_cb(False, f"Error HTTP {status}: Error de servidor.")
            else:
                self.finished_cb(False, f"Error HTTP {status}")
        except Exception as e:
            print(f"[ERROR INESPERADO] {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc() # Imprime el stack trace completo en consola
            self.finished_cb(False, f"Error crítico: {str(e)}")

    # ── Descarga del JSON de configuración ───────────────────────────────────
    @staticmethod
    def _fetch_config() -> dict:
        resp = requests.get(CONFIG_URL, timeout=15)
        resp.raise_for_status()
        return resp.json()

    # ── Forge ────────────────────────────────────────────────────────────────
    def _check_and_install_forge(self, forge_version: str, forge_installer: str):
        if not forge_version:
            self.progress_cb(0.10, "Sin versión de Forge especificada, saltando…")
            return

        # ── 1. Comprobar si Forge ya está instalado en .minecraft/versions/ ──
        forge_installed = False
        if os.path.isdir(self.versions_dir):
            for folder_name in os.listdir(self.versions_dir):
                if forge_version in folder_name:
                    forge_installed = True
                    break

        if forge_installed:
            self.progress_cb(0.15, f"Forge {forge_version} ya instalado ✓")
            # Limpiar el installer de la carpeta mods si quedó ahí
            self._cleanup_forge_installer(forge_installer)
            return

        # ── 2. Descargar el installer desde GitHub /mods/ ──
        if not forge_installer:
            raise RuntimeError(
                "No se especificó forge_installer en configuracion.json"
            )

        self.progress_cb(0.10, f"Descargando instalador de Forge desde GitHub…")
        installer_path = os.path.join(self.minecraft_dir, forge_installer)
        installer_url = MODS_BASE_URL + urllib.parse.quote(forge_installer)
        self._download_file(installer_url, installer_path)

        # ── 3. Ejecutar de forma completamente silenciosa ──
        self.progress_cb(0.20, "Instalando Forge silenciosamente…")

        # CREATE_NO_WINDOW evita que aparezca la consola negra en Windows
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW

        try:
            subprocess.run(
                ["java", "-jar", installer_path, "--installClient"],
                cwd=self.minecraft_dir,
                check=True,
                creationflags=creation_flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "Java no está instalado o no se encuentra en el PATH del sistema."
            )
        except subprocess.CalledProcessError:
            raise RuntimeError("La instalación de Forge falló. Revisa tu conexión.")
        finally:
            # Limpiar el instalador de donde se descargó
            if os.path.exists(installer_path):
                os.remove(installer_path)
            # También limpiar si quedó en la carpeta mods/
            self._cleanup_forge_installer(forge_installer)

        self.progress_cb(0.25, f"Forge {forge_version} instalado ✓")

    def _cleanup_forge_installer(self, forge_installer: str):
        """Elimina el installer .jar de la carpeta mods/ si existe (no es un mod)."""
        if not forge_installer:
            return
        installer_in_mods = os.path.join(self.mods_dir, forge_installer)
        if os.path.exists(installer_in_mods):
            os.remove(installer_in_mods)

    # ── Sincronización de Mods ───────────────────────────────────────────────
    def _sync_mods(self, mods_list: list[str], forge_installer: str = ""):
        # Asegurarse de que la carpeta mods exista
        os.makedirs(self.mods_dir, exist_ok=True)

        # ── Eliminar mods obsoletos (que ya no están en el JSON) ──
        self.progress_cb(0.30, "Eliminando mods obsoletos…")
        local_jars = [f for f in os.listdir(self.mods_dir) if f.endswith(".jar")]
        mods_set = set(mods_list)

        eliminados = 0
        for jar in local_jars:
            # Si no está en la lista Y no es el installer de Forge → eliminar
            if jar not in mods_set and jar != forge_installer:
                os.remove(os.path.join(self.mods_dir, jar))
                eliminados += 1

        # También eliminar el installer de Forge si quedó en mods/
        self._cleanup_forge_installer(forge_installer)

        if eliminados:
            self.progress_cb(0.35, f"{eliminados} mod(s) obsoleto(s) eliminado(s).")

        # ── Descargar mods faltantes ──
        total = len(mods_list)
        if total == 0:
            self.progress_cb(0.95, "La lista de mods está vacía.")
            return

        for i, mod_name in enumerate(mods_list):
            mod_local_path = os.path.join(self.mods_dir, mod_name)

            if os.path.exists(mod_local_path):
                # Ya existe localmente, solo actualizar barra
                progreso = 0.35 + 0.60 * ((i + 1) / total)
                self.progress_cb(progreso, f"Mod ya presente: {mod_name}")
                continue

            # Descargar desde GitHub (encode para nombres con espacios/caracteres)
            progreso = 0.35 + 0.60 * ((i + 1) / total)
            self.progress_cb(progreso, f"Descargando ({i+1}/{total}): {mod_name}")

            mod_url = MODS_BASE_URL + urllib.parse.quote(mod_name)
            self._download_file(mod_url, mod_local_path)

    # ── Utilidad de descarga con streaming ───────────────────────────────────
    @staticmethod
    def _download_file(url: str, dest_path: str):
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
