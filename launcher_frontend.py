import os
import platform
import threading
import customtkinter as ctk
from tkinter import filedialog
from plyer import notification

class ModpackLauncherFrontend(ctk.CTk):
    def __init__(self, backend_callback=None):
        """
        Inicializa la ventana principal del launcher.
        
        :param backend_callback: Función de retorno que el backend puede inyectar para
                                 recibir eventos (ej. cuando se presiona el botón principal).
                                 Debería aceptar (accion, directorio_minecraft).
        """
        super().__init__()

        self.backend_callback = backend_callback

        # Configuración de la ventana
        self.title("Modpack Launcher & Updater")
        self.geometry("600x400")
        self.resizable(False, False)
        
        # Tema oscuro moderno
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Configuración del grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        # ==========================================
        # ELEMENTOS DE LA INTERFAZ
        # ==========================================

        # 1. Título
        self.lbl_title = ctk.CTkLabel(
            self, text="Modpack Launcher", 
            font=ctk.CTkFont(size=26, weight="bold")
        )
        self.lbl_title.grid(row=0, column=0, pady=(30, 20))

        # 2. Selector de Directorio
        self.frame_dir = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_dir.grid(row=1, column=0, padx=40, pady=(0, 20), sticky="ew")
        self.frame_dir.grid_columnconfigure(0, weight=1)

        self.dir_var = ctk.StringVar(value=self._get_default_minecraft_dir())
        
        self.entry_dir = ctk.CTkEntry(
            self.frame_dir, 
            textvariable=self.dir_var, 
            state="readonly",
            font=ctk.CTkFont(size=12)
        )
        self.entry_dir.grid(row=0, column=0, padx=(0, 10), sticky="ew")

        self.btn_browse = ctk.CTkButton(
            self.frame_dir, 
            text="Examinar...", 
            width=100, 
            command=self._browse_directory
        )
        self.btn_browse.grid(row=0, column=1)

        # 3. Etiqueta de Estado
        self.lbl_status = ctk.CTkLabel(
            self, 
            text="Estado: Listo", 
            font=ctk.CTkFont(size=14)
        )
        self.lbl_status.grid(row=2, column=0, pady=(10, 5))

        # 4. Barra de Progreso
        self.progress_bar = ctk.CTkProgressBar(self, width=450)
        self.progress_bar.grid(row=3, column=0, pady=(5, 30))
        self.progress_bar.set(0.0)

        # 5. Botón de Acción Principal
        self.btn_main_action = ctk.CTkButton(
            self, 
            text="Jugar", 
            font=ctk.CTkFont(size=18, weight="bold"), 
            height=50, 
            width=200,
            command=self._on_main_action_click
        )
        self.btn_main_action.grid(row=4, column=0, pady=(10, 20))

    def _get_default_minecraft_dir(self):
        """Devuelve la ruta por defecto de .minecraft según el sistema operativo."""
        system = platform.system()
        if system == "Windows":
            return os.path.join(os.getenv("APPDATA"), ".minecraft")
        elif system == "Darwin": # macOS
            return os.path.expanduser("~/Library/Application Support/minecraft")
        else: # Linux
            return os.path.expanduser("~/.minecraft")

    def _browse_directory(self):
        """Abre un diálogo para que el usuario pueda cambiar la carpeta de destino."""
        selected_dir = filedialog.askdirectory(
            initialdir=self.dir_var.get(), 
            title="Seleccionar carpeta de Minecraft"
        )
        if selected_dir:
            self.dir_var.set(selected_dir)

    def _on_main_action_click(self):
        """Maneja el evento de click del botón principal y delega la lógica al backend."""
        accion = self.btn_main_action.cget("text")
        directorio = self.dir_var.get()
        
        if self.backend_callback:
            self.backend_callback(accion, directorio)
        else:
            print(f"[UI] Acción '{accion}' solicitada en: {directorio}")

    # ==========================================
    # MÉTODOS PÚBLICOS PARA EL BACKEND
    # ==========================================

    def actualizar_progreso(self, valor: float):
        """
        Actualiza la barra de progreso. Es thread-safe.
        
        :param valor: float entre 0.0 y 1.0 indicando el porcentaje.
        """
        # .after asegura que los cambios en la UI ocurran en el hilo principal
        self.after(0, lambda: self.progress_bar.set(valor))

    def actualizar_estado(self, texto: str):
        """
        Actualiza el texto descriptivo del estado actual (ej. 'Descargando mods...').
        
        :param texto: El mensaje de estado a mostrar.
        """
        self.after(0, lambda: self.lbl_status.configure(text=f"Estado: {texto}"))

    def cambiar_estado_boton(self, texto_boton: str):
        """
        Modifica el texto del botón de acción ('Instalar', 'Actualizar', 'Jugar').
        Puede usarse para deshabilitar temporalmente el botón usando un texto como 'Procesando...'.
        
        :param texto_boton: Nuevo texto a mostrar en el botón principal.
        """
        self.after(0, lambda: self.btn_main_action.configure(text=texto_boton))

    def mostrar_alerta(self, titulo: str, mensaje: str):
        """
        Lanza una notificación nativa de escritorio usando plyer.
        
        :param titulo: Título de la notificación del sistema.
        :param mensaje: Cuerpo de la alerta (ej. '¡Actualización disponible!').
        """
        try:
            notification.notify(
                title=titulo,
                message=mensaje,
                app_name="Modpack Launcher",
                timeout=7  # Segundos que durará la notificación en pantalla
            )
        except Exception as e:
            print(f"[Alerta Fallida] {titulo}: {mensaje}. Error: {e}")

# ==========================================
# INTEGRACIÓN CON EL BACKEND REAL
# ==========================================
if __name__ == "__main__":
    from updater_backend import ModpackUpdaterBackend

    def backend_logica(accion, directorio):
        """Callback que el frontend invoca al presionar el botón principal."""

        if accion in ["Instalar", "Actualizar"]:
            # Deshabilitamos el botón mientras trabaja
            app.cambiar_estado_boton("Trabajando…")

            # Callbacks thread-safe que el backend invocará desde su hilo
            def on_progress(valor, mensaje):
                app.actualizar_progreso(valor)
                app.actualizar_estado(mensaje)

            def on_finished(exito, mensaje):
                app.actualizar_estado(mensaje)
                app.actualizar_progreso(1.0 if exito else 0.0)
                app.cambiar_estado_boton("Jugar")
                if exito:
                    app.mostrar_alerta("¡Modpack Listo!", mensaje)
                else:
                    app.mostrar_alerta("Error", mensaje)

            def on_version(version):
                app.after(0, lambda: app.lbl_title.configure(
                    text=f"Modpack Launcher  v{version}"
                ))

            updater = ModpackUpdaterBackend(
                minecraft_dir=directorio,
                progress_cb=on_progress,
                finished_cb=on_finished,
                version_cb=on_version,
            )
            updater.start()

        elif accion == "Jugar":
            app.actualizar_estado("Iniciando Minecraft…")
            app.mostrar_alerta("Iniciando Juego", "Minecraft se abrirá en unos instantes.")

    # ── Lanzar la aplicación ──
    app = ModpackLauncherFrontend(backend_callback=backend_logica)

    # Al abrir, el botón muestra "Actualizar" para invitar al usuario
    app.cambiar_estado_boton("Actualizar")
    app.actualizar_estado("Presiona Actualizar para sincronizar el modpack.")

    app.mainloop()
