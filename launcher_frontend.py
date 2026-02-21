"""
launcher_frontend.py
Frontend del actualizador de modpacks de Minecraft.
Diseño moderno estilo gaming con CustomTkinter.
"""

import os
import platform
import customtkinter as ctk
from tkinter import filedialog

# ── Paleta de colores ────────────────────────────────────────────────────────
COLOR_BG_DARK      = "#0d1117"     # Fondo principal (casi negro)
COLOR_BG_CARD      = "#161b22"     # Fondo de paneles/cards
COLOR_BG_CARD_ALT  = "#1c2333"     # Fondo alternativo
COLOR_ACCENT       = "#2ea043"     # Verde esmeralda (acento principal)
COLOR_ACCENT_HOVER = "#3fb950"     # Verde hover
COLOR_ACCENT_DIM   = "#1a7f37"     # Verde oscuro
COLOR_TEXT         = "#e6edf3"     # Texto principal (blanco suave)
COLOR_TEXT_DIM     = "#8b949e"     # Texto secundario
COLOR_PROGRESS_BG  = "#21262d"     # Fondo barra de progreso
COLOR_BORDER       = "#30363d"     # Bordes sutiles
COLOR_RED          = "#f85149"     # Rojo para errores
COLOR_YELLOW       = "#d29922"     # Amarillo para avisos


class ModpackLauncherFrontend(ctk.CTk):
    def __init__(self, backend_callback=None):
        super().__init__()

        self.backend_callback = backend_callback

        # ── Configuración de ventana ──
        self.title("⛏ Modpack Launcher")
        self.geometry("700x520")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG_DARK)

        ctk.set_appearance_mode("dark")

        # Grid principal: 1 columna, filas con peso
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)  # El log se expande

        # ══════════════════════════════════════════════════════════════════════
        # HEADER
        # ══════════════════════════════════════════════════════════════════════
        self.frame_header = ctk.CTkFrame(
            self, fg_color=COLOR_BG_CARD, corner_radius=0, height=80
        )
        self.frame_header.grid(row=0, column=0, sticky="ew")
        self.frame_header.grid_propagate(False)
        self.frame_header.grid_columnconfigure(1, weight=1)

        # Icono de pico (emoji como placeholder)
        self.lbl_icon = ctk.CTkLabel(
            self.frame_header, text="⛏",
            font=ctk.CTkFont(size=36),
            text_color=COLOR_ACCENT
        )
        self.lbl_icon.grid(row=0, column=0, padx=(25, 10), pady=20)

        # Título + subtítulo
        self.frame_titles = ctk.CTkFrame(self.frame_header, fg_color="transparent")
        self.frame_titles.grid(row=0, column=1, sticky="w", pady=15)

        self.lbl_title = ctk.CTkLabel(
            self.frame_titles, text="Modpack Launcher",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=COLOR_TEXT
        )
        self.lbl_title.grid(row=0, column=0, sticky="w")

        self.lbl_subtitle = ctk.CTkLabel(
            self.frame_titles, text="Actualizador de mods automático",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLOR_TEXT_DIM
        )
        self.lbl_subtitle.grid(row=1, column=0, sticky="w")

        # Versión (se actualiza desde el backend)
        self.lbl_version = ctk.CTkLabel(
            self.frame_header, text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_ACCENT
        )
        self.lbl_version.grid(row=0, column=2, padx=25, pady=20)

        # ══════════════════════════════════════════════════════════════════════
        # SELECTOR DE DIRECTORIO
        # ══════════════════════════════════════════════════════════════════════
        self.frame_dir = ctk.CTkFrame(
            self, fg_color=COLOR_BG_CARD, corner_radius=12,
            border_width=1, border_color=COLOR_BORDER
        )
        self.frame_dir.grid(row=1, column=0, padx=20, pady=(15, 8), sticky="ew")
        self.frame_dir.grid_columnconfigure(1, weight=1)

        self.lbl_dir_label = ctk.CTkLabel(
            self.frame_dir, text="📂  Directorio:",
            font=ctk.CTkFont(size=13),
            text_color=COLOR_TEXT_DIM
        )
        self.lbl_dir_label.grid(row=0, column=0, padx=(15, 8), pady=12)

        self.dir_var = ctk.StringVar(value=self._get_default_minecraft_dir())

        self.entry_dir = ctk.CTkEntry(
            self.frame_dir,
            textvariable=self.dir_var,
            state="readonly",
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=COLOR_BG_DARK,
            border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_DIM,
            height=32
        )
        self.entry_dir.grid(row=0, column=1, padx=(0, 8), pady=12, sticky="ew")

        self.btn_browse = ctk.CTkButton(
            self.frame_dir, text="Cambiar",
            width=80, height=32,
            font=ctk.CTkFont(size=12),
            fg_color=COLOR_BG_CARD_ALT,
            hover_color=COLOR_BORDER,
            border_width=1, border_color=COLOR_BORDER,
            text_color=COLOR_TEXT_DIM,
            command=self._browse_directory
        )
        self.btn_browse.grid(row=0, column=2, padx=(0, 12), pady=12)

        # ══════════════════════════════════════════════════════════════════════
        # ESTADO + PROGRESO
        # ══════════════════════════════════════════════════════════════════════
        self.frame_progress = ctk.CTkFrame(
            self, fg_color=COLOR_BG_CARD, corner_radius=12,
            border_width=1, border_color=COLOR_BORDER
        )
        self.frame_progress.grid(row=2, column=0, padx=20, pady=(8, 8), sticky="ew")
        self.frame_progress.grid_columnconfigure(0, weight=1)

        self.lbl_status = ctk.CTkLabel(
            self.frame_progress,
            text="🟢  Listo",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLOR_TEXT,
            anchor="w"
        )
        self.lbl_status.grid(row=0, column=0, padx=15, pady=(12, 4), sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(
            self.frame_progress,
            width=400, height=12,
            corner_radius=6,
            fg_color=COLOR_PROGRESS_BG,
            progress_color=COLOR_ACCENT
        )
        self.progress_bar.grid(row=1, column=0, padx=15, pady=(4, 12), sticky="ew")
        self.progress_bar.set(0.0)

        # ══════════════════════════════════════════════════════════════════════
        # LOG EN VIVO (reemplaza la consola)
        # ══════════════════════════════════════════════════════════════════════
        self.frame_log = ctk.CTkFrame(
            self, fg_color=COLOR_BG_CARD, corner_radius=12,
            border_width=1, border_color=COLOR_BORDER
        )
        self.frame_log.grid(row=4, column=0, padx=20, pady=(8, 8), sticky="nsew")
        self.frame_log.grid_columnconfigure(0, weight=1)
        self.frame_log.grid_rowconfigure(1, weight=1)

        self.lbl_log_title = ctk.CTkLabel(
            self.frame_log, text="📋  Registro de actividad",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_TEXT_DIM,
            anchor="w"
        )
        self.lbl_log_title.grid(row=0, column=0, padx=15, pady=(10, 4), sticky="w")

        self.txt_log = ctk.CTkTextbox(
            self.frame_log,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=COLOR_BG_DARK,
            text_color=COLOR_TEXT_DIM,
            corner_radius=8,
            border_width=0,
            wrap="word",
            state="disabled",
            height=120
        )
        self.txt_log.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # ══════════════════════════════════════════════════════════════════════
        # BOTÓN PRINCIPAL
        # ══════════════════════════════════════════════════════════════════════
        self.frame_bottom = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_bottom.grid(row=5, column=0, padx=20, pady=(4, 18), sticky="ew")
        self.frame_bottom.grid_columnconfigure(0, weight=1)

        self.btn_main_action = ctk.CTkButton(
            self.frame_bottom,
            text="⚡ Jugar",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            height=52,
            corner_radius=12,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            text_color="#ffffff",
            command=self._on_main_action_click
        )
        self.btn_main_action.grid(row=0, column=0, sticky="ew")

    # ══════════════════════════════════════════════════════════════════════════
    # UTILIDADES PRIVADAS
    # ══════════════════════════════════════════════════════════════════════════

    def _get_default_minecraft_dir(self):
        system = platform.system()
        if system == "Windows":
            return os.path.join(os.getenv("APPDATA"), ".minecraft")
        elif system == "Darwin":
            return os.path.expanduser("~/Library/Application Support/minecraft")
        else:
            return os.path.expanduser("~/.minecraft")

    def _browse_directory(self):
        selected_dir = filedialog.askdirectory(
            initialdir=self.dir_var.get(),
            title="Seleccionar carpeta de Minecraft"
        )
        if selected_dir:
            self.dir_var.set(selected_dir)

    def _on_main_action_click(self):
        accion = self.btn_main_action.cget("text")
        # Limpiar prefijos de emoji para obtener la acción limpia
        accion_limpia = accion.replace("⚡ ", "").replace("🔄 ", "").replace("⏳ ", "").strip()
        directorio = self.dir_var.get()

        if self.backend_callback:
            self.backend_callback(accion_limpia, directorio)
        else:
            print(f"[UI] Acción '{accion_limpia}' solicitada en: {directorio}")

    # ══════════════════════════════════════════════════════════════════════════
    # MÉTODOS PÚBLICOS PARA EL BACKEND (thread-safe)
    # ══════════════════════════════════════════════════════════════════════════

    def actualizar_progreso(self, valor: float):
        """Actualiza la barra de progreso (0.0 a 1.0). Thread-safe."""
        self.after(0, lambda: self.progress_bar.set(valor))

    def actualizar_estado(self, texto: str):
        """Actualiza el texto de estado y añade la línea al log. Thread-safe."""
        def _update():
            self.lbl_status.configure(text=f"🟢  {texto}")
            self._append_log(texto)
        self.after(0, _update)

    def cambiar_estado_boton(self, texto_boton: str):
        """Cambia el texto del botón principal con el icono correspondiente."""
        iconos = {
            "Jugar": "⚡ Jugar",
            "Actualizar": "🔄 Actualizar",
            "Verificando…": "⏳ Verificando…",
        }
        texto_final = iconos.get(texto_boton, texto_boton)

        def _update():
            self.btn_main_action.configure(text=texto_final)
            # Cambiar color según estado
            if texto_boton == "Jugar":
                self.btn_main_action.configure(
                    fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_HOVER
                )
            elif texto_boton == "Actualizar":
                self.btn_main_action.configure(
                    fg_color="#1f6feb", hover_color="#388bfd"
                )
            else:
                self.btn_main_action.configure(
                    fg_color=COLOR_ACCENT_DIM, hover_color=COLOR_ACCENT_DIM
                )
        self.after(0, _update)

    def mostrar_alerta(self, titulo: str, mensaje: str):
        """Muestra una notificación nativa de escritorio."""
        try:
            from plyer import notification
            notification.notify(
                title=titulo,
                message=mensaje,
                app_name="Modpack Launcher",
                timeout=7
            )
        except Exception as e:
            print(f"[Alerta] {titulo}: {mensaje} (plyer error: {e})")

    def mostrar_resultado(self, exito: bool, mensaje: str):
        """
        Muestra un popup visual dentro de la app indicando
        si la actualización fue exitosa o falló.
        """
        def _show():
            popup = ctk.CTkToplevel(self)
            popup.title("Resultado")
            popup.geometry("420x220")
            popup.resizable(False, False)
            popup.configure(fg_color=COLOR_BG_DARK)
            popup.transient(self)
            popup.grab_set()

            # Centrar sobre la ventana principal
            popup.update_idletasks()
            x = self.winfo_x() + (self.winfo_width() // 2) - 210
            y = self.winfo_y() + (self.winfo_height() // 2) - 110
            popup.geometry(f"+{x}+{y}")

            color = COLOR_ACCENT if exito else COLOR_RED
            icono = "✅" if exito else "❌"
            titulo = "¡Actualización exitosa!" if exito else "Ocurrió un error"

            # Card interior
            card = ctk.CTkFrame(
                popup, fg_color=COLOR_BG_CARD, corner_radius=16,
                border_width=2, border_color=color
            )
            card.pack(fill="both", expand=True, padx=15, pady=15)
            card.grid_columnconfigure(0, weight=1)

            # Icono grande
            ctk.CTkLabel(
                card, text=icono,
                font=ctk.CTkFont(size=40)
            ).grid(row=0, column=0, pady=(20, 5))

            # Título
            ctk.CTkLabel(
                card, text=titulo,
                font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
                text_color=color
            ).grid(row=1, column=0, pady=(0, 4))

            # Mensaje
            ctk.CTkLabel(
                card, text=mensaje,
                font=ctk.CTkFont(size=12),
                text_color=COLOR_TEXT_DIM,
                wraplength=350
            ).grid(row=2, column=0, padx=20, pady=(0, 10))

            # Botón cerrar
            ctk.CTkButton(
                card, text="Aceptar", width=120, height=36,
                corner_radius=10,
                fg_color=color,
                hover_color=COLOR_ACCENT_HOVER if exito else "#da3633",
                font=ctk.CTkFont(size=14, weight="bold"),
                command=popup.destroy
            ).grid(row=3, column=0, pady=(0, 18))

        self.after(0, _show)

    def _append_log(self, texto: str):
        """Añade una línea al panel de log con scroll automático."""
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", f"  {texto}\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRACIÓN CON EL BACKEND REAL
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import threading as _threading
    from tkinter import messagebox
    from updater_backend import ModpackUpdaterBackend

    def backend_logica(accion, directorio):
        """Callback que el frontend invoca al presionar el botón principal."""

        if accion == "Actualizar":
            app.cambiar_estado_boton("Verificando…")

            def on_progress(valor, mensaje):
                app.actualizar_progreso(valor)
                app.actualizar_estado(mensaje)

            def on_finished(exito, mensaje):
                app.actualizar_estado(mensaje)
                if exito:
                    app.actualizar_progreso(1.0)
                    app.cambiar_estado_boton("Jugar")
                else:
                    app.actualizar_progreso(0.0)
                    app.cambiar_estado_boton("Actualizar")
                # Mostrar popup visual de resultado
                app.mostrar_resultado(exito, mensaje)

            def on_version(version):
                app.after(0, lambda: app.lbl_version.configure(
                    text=f"v{version}"
                ))

            def on_confirm(mensaje):
                """Diálogo sí/no thread-safe."""
                respuesta = [False]
                evento = _threading.Event()

                def _mostrar_dialogo():
                    respuesta[0] = messagebox.askyesno(
                        "Confirmación", mensaje, parent=app
                    )
                    evento.set()

                app.after(0, _mostrar_dialogo)
                evento.wait()
                return respuesta[0]

            updater = ModpackUpdaterBackend(
                minecraft_dir=directorio,
                progress_cb=on_progress,
                finished_cb=on_finished,
                version_cb=on_version,
                confirm_cb=on_confirm,
            )
            updater.start()

        elif accion == "Jugar":
            app.actualizar_estado("Iniciando Minecraft…")
            app.mostrar_alerta("Iniciando Juego", "Minecraft se abrirá en unos instantes.")

    # ── Lanzar la aplicación ──
    app = ModpackLauncherFrontend(backend_callback=backend_logica)

    app.cambiar_estado_boton("Actualizar")
    app.actualizar_estado("Presiona Actualizar para verificar y sincronizar.")

    app.mainloop()
