"""
updater_backend.py
Backend del actualizador de modpacks de Minecraft.
Se integra con launcher_frontend.py vía callbacks thread-safe.

FLUJO:
  1. Verificar que Java esté instalado.
  2. Verificar Forge: buscar carpeta con .jar y .json en versions/.
     Si no está → PREGUNTAR al usuario si desea instalarlo.
  3. Comparar carpeta local mods/ con el JSON del repo.
  4. Descargar mods faltantes y eliminar obsoletos.

Repositorio:
  https://github.com/fpereira22/modpack-installer-minecraft
"""

import os
import sys
import threading
import subprocess
import requests
import urllib.parse
import traceback


# ── URL base del repositorio en GitHub (rama main) ──────────────────────────
GITHUB_RAW_BASE = (
    "https://raw.githubusercontent.com/"
    "fpereira22/modpack-installer-minecraft/main"
)
CONFIG_URL = f"{GITHUB_RAW_BASE}/configuracion.json"
MODS_BASE_URL = f"{GITHUB_RAW_BASE}/mods/"


class ModpackUpdaterBackend:
    """
    Clase que maneja toda la lógica de actualización.

    Callbacks:
      - progress_cb(valor: float, mensaje: str)
      - finished_cb(exito: bool, mensaje: str)
      - version_cb(version: str)          ← opcional, para mostrar la versión
      - confirm_cb(mensaje: str) -> bool   ← pregunta sí/no al usuario
    """

    def __init__(self, minecraft_dir: str, progress_cb, finished_cb,
                 version_cb=None, confirm_cb=None):
        self.minecraft_dir = minecraft_dir
        self.mods_dir = os.path.join(minecraft_dir, "mods")
        self.versions_dir = os.path.join(minecraft_dir, "versions")
        self.progress_cb = progress_cb
        self.finished_cb = finished_cb
        self.version_cb = version_cb
        # confirm_cb debe bloquear hasta que el usuario responda True/False
        self.confirm_cb = confirm_cb

    # ── Punto de entrada público ─────────────────────────────────────────────
    def start(self):
        """Inicia la actualización en un hilo daemon para no bloquear la UI."""
        thread = threading.Thread(target=self._run_update, daemon=True)
        thread.start()

    # ── Flujo principal (corre en hilo secundario) ───────────────────────────
    def _run_update(self):
        try:
            # ── PASO 1: Verificar Java ───────────────────────────────────────
            self.progress_cb(0.05, "Verificando Java…")
            if not self._check_java():
                print("[AVISO] Java no fue encontrado en el sistema.")
                self.finished_cb(
                    False,
                    "Java no está instalado. Es necesario para Minecraft y Forge.\n"
                    "Descárgalo desde: https://adoptium.net"
                )
                return
            print("[OK] Java encontrado en el sistema.")

            # ── PASO 2: Obtener configuracion.json ───────────────────────────
            self.progress_cb(0.10, "Obteniendo configuración del servidor…")
            config = self._fetch_config()

            forge_version = config.get("forge_version", "")
            forge_installer = config.get("forge_installer", "")
            modpack_version = config.get("modpack_version", "")
            mods_list: list[str] = config.get("mods", [])

            print(f"[INFO] Modpack v{modpack_version} | Forge requerido: {forge_version}")
            print(f"[INFO] Mods en el servidor: {len(mods_list)}")

            if self.version_cb and modpack_version:
                self.version_cb(modpack_version)

            # ── PASO 3: Verificar Forge ──────────────────────────────────────
            self.progress_cb(0.15, "Verificando Forge…")
            forge_ok = self._check_forge_installed(forge_version)

            if forge_ok:
                print(f"[OK] Forge {forge_version} verificado (carpeta, .jar y .json presentes).")
                self.progress_cb(0.20, f"Forge {forge_version} verificado ✓")
            else:
                # Forge NO está instalado → PREGUNTAR al usuario
                print(f"[AVISO] Forge {forge_version} NO encontrado.")

                if self.confirm_cb:
                    usuario_acepta = self.confirm_cb(
                        f"Forge {forge_version} no está instalado.\n\n"
                        f"¿Deseas descargarlo e instalarlo ahora?"
                    )
                else:
                    # Sin callback de confirmación, no se puede preguntar
                    usuario_acepta = False

                if usuario_acepta:
                    self._install_forge(forge_version, forge_installer)
                else:
                    print("[INFO] El usuario declinó instalar Forge.")
                    self.finished_cb(
                        False,
                        f"Forge {forge_version} es necesario para jugar.\n"
                        "Instálalo manualmente o vuelve a intentar."
                    )
                    return

            # ── PASO 4: Comparar y sincronizar mods ──────────────────────────
            self._sync_mods(mods_list, forge_installer)

            self.progress_cb(1.0, "¡Actualización completada!")
            self.finished_cb(True, "Mods sincronizados correctamente.")

        except requests.exceptions.ConnectionError as e:
            print(f"[ERROR RED] No se pudo establecer conexión: {e}")
            self.finished_cb(False, "Error: Sin conexión a internet.")
        except requests.exceptions.Timeout as e:
            print(f"[ERROR TIMEOUT] La solicitud tardó demasiado: {e}")
            self.finished_cb(False, "Error: Tiempo de espera agotado.")
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code
            url = e.response.url
            print(f"[ERROR HTTP {status}] URL: {url}")
            if status == 404:
                print(" >> Archivo no encontrado. Verifica el repo de GitHub.")
                self.finished_cb(False, "Error 404: Archivo no encontrado en el repositorio.")
            elif status >= 500:
                print(" >> Error del servidor (GitHub podría estar caído).")
                self.finished_cb(False, f"Error {status}: Problema del servidor.")
            else:
                self.finished_cb(False, f"Error HTTP {status}")
        except Exception as e:
            print(f"[ERROR INESPERADO] {type(e).__name__}: {e}")
            traceback.print_exc()
            self.finished_cb(False, f"Error: {e}")

    # ═════════════════════════════════════════════════════════════════════════
    # VERIFICACIONES
    # ═════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _check_java() -> bool:
        """Comprueba si Java está disponible en el PATH. No instala nada."""
        try:
            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(
                ["java", "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
                timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _check_forge_installed(self, forge_version: str) -> bool:
        """
        Busca en .minecraft/versions/ la carpeta de Forge.
        El JSON tiene forge_version='1.20.1-47.4.16' pero la carpeta
        real de Minecraft se llama '1.20.1-forge-47.4.16'.
        Verifica que dentro haya un .jar y un .json.
        """
        if not forge_version:
            print("[AVISO] No se especificó versión de Forge en el JSON.")
            return True  # Si no se requiere, no bloquear

        if not os.path.isdir(self.versions_dir):
            print(f"[AVISO] Carpeta versions/ no existe: {self.versions_dir}")
            return False

        # Construir el nombre de carpeta real: "1.20.1-47.4.16" → "1.20.1-forge-47.4.16"
        parts = forge_version.split("-", 1)  # ["1.20.1", "47.4.16"]
        if len(parts) == 2:
            expected_folder = f"{parts[0]}-forge-{parts[1]}"
        else:
            expected_folder = forge_version

        print(f"[CHECK] Buscando carpeta: {expected_folder}")

        folder_path = os.path.join(self.versions_dir, expected_folder)

        if not os.path.isdir(folder_path):
            print(f"[CHECK] Carpeta NO encontrada: {folder_path}")
            return False

        # Verificar que dentro haya un .jar y un .json
        archivos = os.listdir(folder_path)
        tiene_jar = any(f.endswith(".jar") for f in archivos)
        tiene_json = any(f.endswith(".json") for f in archivos)

        print(f"[CHECK] Carpeta encontrada: {expected_folder}")
        print(f"  .jar presente: {'✓' if tiene_jar else '✗'}")
        print(f"  .json presente: {'✓' if tiene_json else '✗'}")

        return tiene_jar and tiene_json

    # ═════════════════════════════════════════════════════════════════════════
    # INSTALACIÓN DE FORGE (solo si el usuario acepta)
    # ═════════════════════════════════════════════════════════════════════════

    def _install_forge(self, forge_version: str, forge_installer: str):
        """
        Descarga el installer de Forge desde el repo de GitHub (/mods/)
        y lo ejecuta con --installClient. Solo se llama si el usuario aceptó.
        """
        if not forge_installer:
            raise RuntimeError(
                "No se especificó 'forge_installer' en configuracion.json"
            )

        # ── Descargar ──
        self.progress_cb(0.20, "Descargando instalador de Forge…")
        print(f"[DESCARGA] Forge installer: {forge_installer}")

        installer_path = os.path.join(self.minecraft_dir, forge_installer)
        installer_url = MODS_BASE_URL + urllib.parse.quote(forge_installer)
        self._download_file(installer_url, installer_path)
        print(f"[OK] Installer descargado en: {installer_path}")

        # ── Ejecutar silenciosamente ──
        self.progress_cb(0.25, "Instalando Forge (esto puede tardar)…")
        print("[EJECUTANDO] java -jar ... --installClient")

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
            print(f"[OK] Forge {forge_version} instalado correctamente.")
            self.progress_cb(0.30, f"Forge {forge_version} instalado ✓")
        except FileNotFoundError:
            raise RuntimeError("Java no se encontró al intentar instalar Forge.")
        except subprocess.CalledProcessError:
            raise RuntimeError("La instalación de Forge falló.")
        finally:
            # Limpiar el installer descargado
            if os.path.exists(installer_path):
                os.remove(installer_path)
                print(f"[LIMPIEZA] Installer eliminado: {installer_path}")

    # ═════════════════════════════════════════════════════════════════════════
    # CONFIGURACIÓN
    # ═════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _fetch_config() -> dict:
        resp = requests.get(CONFIG_URL, timeout=15)
        resp.raise_for_status()
        return resp.json()

    # ═════════════════════════════════════════════════════════════════════════
    # SINCRONIZACIÓN DE MODS
    # ═════════════════════════════════════════════════════════════════════════

    def _sync_mods(self, mods_list: list[str], forge_installer: str = ""):
        """
        Compara la carpeta local mods/ con la lista del JSON.
        - Descarga los mods que faltan.
        - Elimina los .jar que ya no están en la lista (obsoletos).
        - Ignora el installer de Forge (no es un mod).
        """
        os.makedirs(self.mods_dir, exist_ok=True)

        # ── Leer estado local ──
        self.progress_cb(0.35, "Comparando mods locales con el servidor…")
        local_jars = set(f for f in os.listdir(self.mods_dir) if f.endswith(".jar"))
        server_mods = set(mods_list)

        # Archivos a ignorar (no son mods)
        ignorar = set()
        if forge_installer:
            ignorar.add(forge_installer)

        # ── Identificar diferencias ──
        mods_faltantes = server_mods - local_jars
        mods_obsoletos = local_jars - server_mods - ignorar
        mods_ok = local_jars & server_mods

        print(f"\n[COMPARACIÓN DE MODS]")
        print(f"  Ya presentes:    {len(mods_ok)}")
        print(f"  Por descargar:   {len(mods_faltantes)}")
        print(f"  Obsoletos:       {len(mods_obsoletos)}")

        for mod in sorted(mods_obsoletos):
            print(f"  [ELIMINAR] {mod}")
        for mod in sorted(mods_faltantes):
            print(f"  [DESCARGAR] {mod}")

        # ── Eliminar obsoletos ──
        if mods_obsoletos:
            self.progress_cb(0.40, f"Eliminando {len(mods_obsoletos)} mod(s) obsoleto(s)…")
            for mod in mods_obsoletos:
                mod_path = os.path.join(self.mods_dir, mod)
                try:
                    os.remove(mod_path)
                    print(f"  [OK] Eliminado: {mod}")
                except OSError as e:
                    print(f"  [ERROR] No se pudo eliminar {mod}: {e}")

        # Limpiar installer de Forge de mods/ si quedó
        if forge_installer:
            installer_in_mods = os.path.join(self.mods_dir, forge_installer)
            if os.path.exists(installer_in_mods):
                try:
                    os.remove(installer_in_mods)
                    print(f"  [LIMPIEZA] Installer eliminado de mods/: {forge_installer}")
                except OSError as e:
                    print(f"  [AVISO] No se pudo limpiar installer: {e}")

        # ── Descargar faltantes ──
        if not mods_faltantes:
            self.progress_cb(0.95, "Todos los mods están al día ✓")
            print("\n[OK] No hay mods por descargar.")
            return

        mods_a_descargar = sorted(mods_faltantes)
        total = len(mods_a_descargar)

        for i, mod_name in enumerate(mods_a_descargar):
            progreso = 0.45 + 0.50 * ((i + 1) / total)
            self.progress_cb(progreso, f"Descargando ({i+1}/{total}): {mod_name}")

            mod_url = MODS_BASE_URL + urllib.parse.quote(mod_name)
            mod_local_path = os.path.join(self.mods_dir, mod_name)

            try:
                self._download_file(mod_url, mod_local_path)
                print(f"  [OK] Descargado: {mod_name}")
            except requests.exceptions.HTTPError as e:
                print(f"  [ERROR] {mod_name}: HTTP {e.response.status_code}")
                continue
            except Exception as e:
                print(f"  [ERROR] {mod_name}: {e}")
                continue

    # ═════════════════════════════════════════════════════════════════════════
    # UTILIDAD
    # ═════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _download_file(url: str, dest_path: str):
        resp = requests.get(url, stream=True, timeout=30)
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
