import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk, ImageOps
import os
import shutil
from datetime import datetime, timedelta
import customtkinter as ctk

# Configuración visual global
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def ruta_base_datos(nombre):
    """Localiza una base existente sin crear otra copia vacía por una ruta relativa.

    Prioriza archivos existentes y, si hay duplicados, usa el de mayor tamaño como
    candidato más probable a contener datos. Si no existe ninguno, devuelve la ruta
    junto al programa para que la creación sea explícita y consistente.
    """
    carpeta_script = os.path.dirname(os.path.abspath(__file__))
    carpeta_actual = os.path.abspath(os.getcwd())
    home = os.path.expanduser('~')
    carpetas = [carpeta_script, carpeta_actual, home]
    for sub in ('Desktop', 'Escritorio', 'Documents', 'Documentos', 'Downloads', 'Descargas', 'OneDrive'):
        carpetas.append(os.path.join(home, sub))

    candidatos = []
    vistos = set()
    for carpeta in carpetas:
        ruta = os.path.abspath(os.path.join(carpeta, nombre))
        if ruta not in vistos and os.path.isfile(ruta):
            vistos.add(ruta)
            try:
                candidatos.append((os.path.getsize(ruta), ruta))
            except OSError:
                candidatos.append((0, ruta))

    # Búsqueda limitada dentro de la carpeta de usuario para detectar bases guardadas
    # en subcarpetas; no se recorren carpetas del sistema ni perfiles ajenos.
    for raiz, dirs, archivos in os.walk(home):
        dirs[:] = [d for d in dirs if d not in {'AppData', '.git', 'node_modules', '.cache'}]
        if nombre in archivos:
            ruta = os.path.abspath(os.path.join(raiz, nombre))
            if ruta not in vistos:
                vistos.add(ruta)
                try:
                    candidatos.append((os.path.getsize(ruta), ruta))
                except OSError:
                    candidatos.append((0, ruta))

    if candidatos:
        # No se modifica ni elimina ninguna copia; solo se selecciona una para lectura/escritura.
        candidatos.sort(key=lambda item: (item[0], item[1] == os.path.join(home, nombre)), reverse=True)
        return candidatos[0][1]
    return os.path.join(carpeta_script, nombre)


class AppUnificadaNeon(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Sistema Almacén y Rastreo de Cajas")
        self.geometry("1400x850")
        self.minsize(1200, 750)
        self.configure(fg_color="#030712")

        # Motor de animaciones: transiciones y contadores de KPI.
        self._vista_actual = None
        self._animaciones_kpi = {}
        self._transicion_activa = False
        self._ultimo_estado_pulso = False
        self._kpi_cards = []
        self._kpi_barra_visible = True
        self._kpi_animacion_id = None
        self._kpi_altura = 112
        self._kpi_pulse_index = 0
        self._kpi_accentos = ["#2563EB", "#7C3AED", "#E11D48", "#059669"]
        self._kpi_bordes_base = ["#1E3A8A", "#311B92", "#7F1D1D", "#064E3B"]

        # Configuración de estilo oscuro para tablas (ttk.Treeview)
        self.configurar_estilos_tabla()

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.crear_sidebar_lateral()

        self.frame_derecho = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_derecho.grid(row=0, column=1, sticky="nsew", padx=15, pady=10)
        self.frame_derecho.grid_columnconfigure(0, weight=1)
        self.frame_derecho.grid_rowconfigure(2, weight=1)

        self.crear_header_top()
        self.crear_barra_kpis()
        self.crear_zona_contenido()

        self.mostrar_materiales()
        # Modo rendimiento: sin bucles de animación continuos al iniciar.

    def configurar_estilos_tabla(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Fondo oscuro para las filas y texto blanco
        style.configure(
            "Treeview",
            background="#0B0F19",
            foreground="#F8FAFC",
            fieldbackground="#0B0F19",
            borderwidth=0,
            rowheight=28,
            font=("Segoe UI", 9)
        )

        # Resaltado azul neón para la fila seleccionada
        style.map(
            "Treeview",
            background=[("selected", "#2563EB")],
            foreground=[("selected", "#FFFFFF")]
        )

        # Encabezado de la tabla oscuro
        style.configure(
            "Treeview.Heading",
            background="#111827",
            foreground="#94A3B8",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            borderwidth=0
        )

        style.map("Treeview.Heading", background=[("active", "#142B4A")])

        # Combobox oscuro para que los campos desplegables no rompan el tema.
        style.configure(
            "TCombobox",
            fieldbackground="#071326",
            background="#0B1B31",
            foreground="#DCEBFF",
            arrowcolor="#60A5FA",
            bordercolor="#17416C",
            lightcolor="#17416C",
            darkcolor="#17416C",
            padding=5
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#071326"), ("focus", "#0A1A30")],
            foreground=[("readonly", "#DCEBFF")],
            selectbackground=[("readonly", "#174A8B")],
            selectforeground=[("readonly", "#FFFFFF")]
        )

        # Scrollbar oscura
        style.configure(
            "Vertical.TScrollbar",
            background="#111827",
            troughcolor="#030712",
            borderwidth=0,
            arrowcolor="#F8FAFC"
        )

    def crear_sidebar_lateral(self):
        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#0B0F19")
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        box_logo = ctk.CTkFrame(sidebar, fg_color="transparent")
        box_logo.pack(fill="x", padx=15, pady=(20, 25))

        lbl_logo_icon = ctk.CTkLabel(box_logo, text="📦", font=("Segoe UI", 24))
        lbl_logo_icon.pack(side="left", padx=(0, 8))

        lbl_logo_text = ctk.CTkLabel(box_logo, text="Sistema Integrado AZ\nGestión de Almacén y Rastreo", 
                                     font=("Roboto", 11, "bold"), text_color="#F8FAFC", justify="left")
        lbl_logo_text.pack(side="left")

        def btn_nav(texto, icono, activo=False, comando=None):
            btn = ctk.CTkButton(
                sidebar, text=f"{icono}  {texto}", anchor="w", height=40, corner_radius=8,
                font=("Roboto", 11, "bold" if activo else "normal"),
                fg_color="#1D4ED8" if activo else "transparent",
                text_color="#FFFFFF" if activo else "#94A3B8",
                hover_color="#1E40AF" if activo else "#1E293B",
                command=comando
            )
            btn.pack(fill="x", padx=10, pady=4)
            return btn

        self.btn_nav_inicio = btn_nav("Inicio", "🏠", activo=True, comando=self.mostrar_materiales)
        btn_nav("Registro de Material", "📝", comando=self.mostrar_materiales)
        btn_nav("Rastreo de Cajas", "🔍", comando=self.mostrar_cajas)
        self.btn_nav_reportes = btn_nav("Reportes", "📊", comando=self.mostrar_reportes)
        self.btn_nav_configuracion = btn_nav("Configuración", "⚙️", comando=self.mostrar_configuracion)

        footer_sys = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer_sys.pack(side="bottom", fill="x", padx=15, pady=15)

        self.lbl_status_sistema = ctk.CTkLabel(
            footer_sys, text="● Sistema en línea",
            font=("Roboto", 10, "bold"), text_color="#10B981"
        )
        self.lbl_status_sistema.pack(anchor="w")

        fecha_str = datetime.now().strftime("%d %b %Y  %H:%M")
        lbl_time = ctk.CTkLabel(footer_sys, text=f"⏱ {fecha_str}", font=("Roboto", 9), text_color="#64748B")
        lbl_time.pack(anchor="w")

    def crear_header_top(self):
        header = ctk.CTkFrame(self.frame_derecho, height=35, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 5))

        box_icons = ctk.CTkFrame(header, fg_color="transparent")
        box_icons.pack(side="right")

        ctk.CTkLabel(box_icons, text="🔔", font=("Segoe UI", 14), text_color="#94A3B8").pack(side="left", padx=8)
        ctk.CTkLabel(box_icons, text="⚙️", font=("Segoe UI", 14), text_color="#94A3B8").pack(side="left", padx=8)

    def crear_barra_kpis(self):
        frame_kpis = ctk.CTkFrame(self.frame_derecho, fg_color="transparent", height=self._kpi_altura)
        self.frame_kpis = frame_kpis
        frame_kpis.grid_propagate(False)
        frame_kpis.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        frame_kpis.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="kpi_cards")
        frame_kpis.grid_rowconfigure(0, weight=1, minsize=self._kpi_altura - 6)

        def card_kpi(col, titulo, subtexto, color_borde, color_icono, icono):
            card = ctk.CTkFrame(
                frame_kpis, fg_color="#081426", corner_radius=14,
                border_width=1, border_color=color_borde
            )
            card.grid(row=0, column=col, padx=5, pady=3, sticky="nsew")
            self._kpi_cards.append(card)

            box_icon = ctk.CTkFrame(card, width=44, height=44, corner_radius=13, fg_color=color_icono,
                                    border_width=1, border_color=color_borde)
            box_icon.pack(side="left", padx=10, pady=8)
            box_icon.pack_propagate(False)

            ctk.CTkLabel(box_icon, text=icono, font=("Segoe UI", 18)).pack(expand=True)

            box_txt = ctk.CTkFrame(card, fg_color="transparent")
            box_txt.pack(side="left", fill="both", expand=True, pady=5, padx=(0, 7))

            ctk.CTkLabel(box_txt, text=titulo, font=("Roboto", 8, "bold"), text_color="#94A3B8", anchor="w").pack(anchor="w", fill="x")
            lbl_val = ctk.CTkLabel(box_txt, text="0", font=("Roboto", 17, "bold"), text_color="#F8FAFC", anchor="w")
            lbl_val.pack(anchor="w")

            ctk.CTkLabel(box_txt, text=subtexto, font=("Roboto", 7), text_color="#8CA8CB", anchor="w").pack(anchor="w", fill="x")
            return lbl_val

        self.kpi_mat = card_kpi(0, "TOTAL MATERIALES", "↑ +2 hoy", "#1E3A8A", "#1D4ED8", "📦")
        self.kpi_caj = card_kpi(1, "CAJAS EN RASTREO", "⚡ En movimiento", "#311B92", "#6D28D9", "🗳️")
        self.kpi_crit = card_kpi(2, "ALERTAS DE STOCK MÍN", "Requieren atención", "#7F1D1D", "#991B1B", "⚠️")
        self.kpi_ent = card_kpi(3, "ENTRADAS HOY", "↑ +1 vs. ayer", "#064E3B", "#047857", "📥")

        self.actualizar_kpis()
        # Los bordes permanecen estáticos para evitar repintados periódicos.

    @staticmethod
    def _mezclar_color(hex_a, hex_b, t):
        """Interpolación RGB para iluminar los bordes sin parpadeos bruscos."""
        a = tuple(int(hex_a[i:i + 2], 16) for i in (1, 3, 5))
        b = tuple(int(hex_b[i:i + 2], 16) for i in (1, 3, 5))
        rgb = tuple(round(x + (y - x) * t) for x, y in zip(a, b))
        return "#%02X%02X%02X" % rgb

    def _animar_bordes_kpi(self):
        """Iluminación ambiental ligera; se omite si los efectos están desactivados."""
        try:
            if not self.winfo_exists() or not self._kpi_cards:
                return
            if hasattr(self, "var_animaciones_suaves") and not self.var_animaciones_suaves.get():
                return
            indice = self._kpi_pulse_index % len(self._kpi_cards)
            card = self._kpi_cards[indice]
            base = self._kpi_bordes_base[indice]
            acento = self._kpi_accentos[indice]
            # Menos actualizaciones de widgets: reduce carga en Tk/CustomTkinter.
            pasos = 10
            duracion_fase = 900
            intervalo = max(35, duracion_fase // pasos)

            def fase(paso, hacia_acento):
                if not card.winfo_exists():
                    return
                t = paso / pasos
                # Ease-in-out suave, sin cambio repentino de luminosidad.
                t = t * t * (3 - 2 * t)
                color = self._mezclar_color(base, acento, t if hacia_acento else 1 - t)
                card.configure(border_color=color)
                if paso < pasos:
                    self.after(intervalo, lambda: fase(paso + 1, hacia_acento))
                elif hacia_acento:
                    self.after(180, lambda: fase(0, False))
                else:
                    card.configure(border_color=base)
                    self._kpi_pulse_index = (indice + 1) % len(self._kpi_cards)
                    self.after(1150, self._animar_bordes_kpi)

            fase(0, True)
        except tk.TclError:
            pass

    def actualizar_kpis(self):
        try:
            conn_m = sqlite3.connect(ruta_base_datos("almacen_materiales.db"))
            cm = conn_m.cursor()
            cm.execute("SELECT COUNT(*) FROM materiales")
            tot_m = cm.fetchone()[0]
            cm.execute("SELECT COUNT(*) FROM materiales WHERE cantidad <= stock_minimo")
            crit_m = cm.fetchone()[0]
            conn_m.close()

            conn_c = sqlite3.connect(ruta_base_datos("rastreo_cajas_almacen.db"))
            cc = conn_c.cursor()
            cc.execute("SELECT COUNT(*) FROM materiales")
            tot_c = cc.fetchone()[0]
            cc.execute("SELECT COUNT(*) FROM movimientos WHERE tipo = 'INGRESO'")
            ent_c = cc.fetchone()[0]
            conn_c.close()

            self.animar_kpi(self.kpi_mat, tot_m)
            self.animar_kpi(self.kpi_caj, tot_c)
            self.animar_kpi(self.kpi_crit, crit_m)
            self.animar_kpi(self.kpi_ent, ent_c)
        except Exception:
            # Mantiene la interfaz disponible aunque una base de datos no esté lista.
            pass

    def animar_kpi(self, etiqueta, destino, duracion=950):
        """Cuenta suavemente hasta el valor real del KPI sin bloquear Tkinter."""
        try:
            clave = str(etiqueta)
            if clave in self._animaciones_kpi:
                self.after_cancel(self._animaciones_kpi[clave])
            texto_actual = etiqueta.cget("text")
            actual = int(texto_actual) if str(texto_actual).isdigit() else 0
            destino = int(destino)

            if actual == destino:
                etiqueta.configure(text=str(destino))
                return

            pasos = max(8, min(24, abs(destino - actual) * 2))
            intervalo = max(12, duracion // pasos)
            estado = {"paso": 0}

            def avanzar():
                estado["paso"] += 1
                progreso = min(1.0, estado["paso"] / pasos)
                # Easing out: rápido al inicio y suave al llegar al valor.
                suavizado = 1 - (1 - progreso) ** 3
                valor = round(actual + (destino - actual) * suavizado)
                etiqueta.configure(text=str(valor))
                if progreso < 1:
                    self._animaciones_kpi[clave] = self.after(intervalo, avanzar)
                else:
                    etiqueta.configure(text=str(destino))
                    self._animaciones_kpi.pop(clave, None)

            avanzar()
        except (tk.TclError, ValueError, TypeError):
            try:
                etiqueta.configure(text=str(destino))
            except tk.TclError:
                pass

    def _animar_cambio_vista(self, nueva_vista):
        """Cambio de vista inmediato: evita repintar el panel en múltiples fotogramas."""
        if self._vista_actual is nueva_vista:
            return
        anterior = self._vista_actual
        self._vista_actual = nueva_vista
        try:
            if anterior is not None:
                try:
                    anterior.place_forget()
                    anterior.pack_forget()
                except tk.TclError:
                    pass
            nueva_vista.place_forget()
            nueva_vista.pack(fill="both", expand=True)
        except tk.TclError:
            try:
                nueva_vista.place_forget()
                nueva_vista.pack(fill="both", expand=True)
            except tk.TclError:
                pass

    def _pulso_sistema(self):
        """Desactivado en modo rendimiento para evitar actualizaciones periódicas."""
        return

    def crear_zona_contenido(self):
        box_content = ctk.CTkFrame(self.frame_derecho, fg_color="transparent")
        box_content.grid(row=2, column=0, sticky="nsew")
        box_content.grid_rowconfigure(1, weight=1)
        box_content.grid_columnconfigure(0, weight=1)

        box_pills = ctk.CTkFrame(box_content, fg_color="transparent")
        box_pills.grid(row=0, column=0, sticky="w", pady=(0, 8))

        self.btn_pill_m = ctk.CTkButton(
            box_pills, text="📦  1. Gestión de Materiales", width=190, height=36, corner_radius=11,
            font=("Roboto", 11, "bold"), fg_color="#2563EB", hover_color="#1D4ED8",
            command=self.mostrar_materiales
        )
        self.btn_pill_m.pack(side="left", padx=(0, 8))

        self.btn_pill_c = ctk.CTkButton(
            box_pills, text="🔍  2. Rastreo de Cajas", width=170, height=36, corner_radius=11,
            font=("Roboto", 11, "bold"), fg_color="transparent", text_color="#94A3B8", hover_color="#1E293B",
            command=self.mostrar_cajas
        )
        self.btn_pill_c.pack(side="left")

        self.contenedor_vistas = ctk.CTkFrame(box_content, fg_color="transparent")
        self.contenedor_vistas.grid(row=1, column=0, sticky="nsew")

        self.vista_materiales = ModuloMaterialesNeon(self.contenedor_vistas)
        self.vista_cajas = ModuloCajasNeon(self.contenedor_vistas)
        self.vista_reportes = self._crear_dashboard_reportes(self.contenedor_vistas)
        self.vista_configuracion = self._crear_vista_configuracion(self.contenedor_vistas)

    def _crear_dashboard_reportes(self, parent):
        """Dashboard de almacén con métricas reales y gráficas animadas suavemente."""
        vista = ctk.CTkFrame(parent, fg_color="#050C18", corner_radius=14,
                             border_width=1, border_color="#102A49")

        vista.grid_columnconfigure(0, weight=1)
        vista.grid_rowconfigure(0, weight=1)

        # Contenedor desplazable: permite ver KPIs, las tres gráficas y los paneles inferiores
        # incluso en ventanas con poca altura.
        contenido = ctk.CTkScrollableFrame(
            vista, fg_color="#050C18", corner_radius=12,
            scrollbar_fg_color="#071321", scrollbar_button_color="#1D4ED8",
            scrollbar_button_hover_color="#38BDF8"
        )
        contenido.grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
        contenido.grid_columnconfigure((0, 1), weight=1, uniform="reportes")
        contenido.grid_rowconfigure(2, weight=1)

        encabezado = ctk.CTkFrame(contenido, fg_color="transparent")
        encabezado.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(14, 8))
        bloque_titulo = ctk.CTkFrame(encabezado, fg_color="transparent")
        bloque_titulo.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            bloque_titulo, text="CENTRO DE ANALÍTICA",
            font=("Segoe UI", 10, "bold"), text_color="#38BDF8", anchor="w"
        ).pack(anchor="w")
        ctk.CTkLabel(
            bloque_titulo, text="Dashboard de almacén",
            font=("Segoe UI", 22, "bold"), text_color="#EAF3FF", anchor="w"
        ).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(
            bloque_titulo, text="Indicadores, movimientos y estado del inventario",
            font=("Segoe UI", 10), text_color="#7895B8", anchor="w"
        ).pack(anchor="w", pady=(2, 0))
        self.lbl_reportes_actualizado = ctk.CTkLabel(
            encabezado, text="ACTUALIZANDO…", font=("Segoe UI", 9, "bold"),
            text_color="#6F91B8"
        )
        self.lbl_reportes_actualizado.pack(side="right", padx=(8, 10))
        ctk.CTkButton(
            encabezado, text="↻  Actualizar", width=112, height=32, corner_radius=9,
            fg_color="#0D2340", hover_color="#12365D", border_width=1,
            border_color="#1C4772", text_color="#CBE4FF",
            command=self.actualizar_dashboard_reportes
        ).pack(side="right")

        # Se eliminaron las tarjetas KPI superiores: sus datos se reflejan en gráficas y recomendaciones.

        # Gráficas: Canvas nativo, sin dependencias adicionales.
        graficas = ctk.CTkFrame(contenido, fg_color="transparent")
        graficas.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=12, pady=(0, 8))
        graficas.grid_columnconfigure((0, 1, 2), weight=1, uniform="reportes_chart")
        graficas.grid_rowconfigure(0, weight=1)

        panel_mov = ctk.CTkFrame(
            graficas, fg_color="#071321", corner_radius=12,
            border_width=1, border_color="#132E4E"
        )
        panel_mov.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        ctk.CTkLabel(
            panel_mov, text="MOVIMIENTOS POR DÍA",
            font=("Segoe UI", 10, "bold"), text_color="#C8DDF7"
        ).pack(anchor="w", padx=14, pady=(10, 0))
        ctk.CTkLabel(
            panel_mov, text="Entradas y salidas · últimos 7 días",
            font=("Segoe UI", 9), text_color="#6F8EAF"
        ).pack(anchor="w", padx=14, pady=(2, 4))
        self.canvas_movimientos = tk.Canvas(
            panel_mov, bg="#071321", highlightthickness=0, height=205
        )
        self.canvas_movimientos.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.canvas_movimientos.bind(
            "<Configure>", lambda _e: self.after(90, self._dibujar_grafica_movimientos)
        )

        panel_cat = ctk.CTkFrame(
            graficas, fg_color="#071321", corner_radius=12,
            border_width=1, border_color="#132E4E"
        )
        panel_cat.grid(row=0, column=1, sticky="nsew", padx=5)
        ctk.CTkLabel(
            panel_cat, text="INVENTARIO POR CATEGORÍA",
            font=("Segoe UI", 10, "bold"), text_color="#C8DDF7"
        ).pack(anchor="w", padx=14, pady=(10, 0))
        ctk.CTkLabel(
            panel_cat, text="Distribución de materiales registrados",
            font=("Segoe UI", 9), text_color="#6F8EAF"
        ).pack(anchor="w", padx=14, pady=(2, 4))
        self.canvas_categorias = tk.Canvas(
            panel_cat, bg="#071321", highlightthickness=0, height=205
        )
        self.canvas_categorias.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.canvas_categorias.bind(
            "<Configure>", lambda _e: self.after(100, self._dibujar_grafica_categorias)
        )

        # Tercera gráfica: composición del inventario, dibujada sin dependencias extra.
        panel_balance = ctk.CTkFrame(
            graficas, fg_color="#071321", corner_radius=12,
            border_width=1, border_color="#132E4E"
        )
        panel_balance.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        ctk.CTkLabel(
            panel_balance, text="BALANCE DEL SISTEMA",
            font=("Segoe UI", 10, "bold"), text_color="#C8DDF7"
        ).pack(anchor="w", padx=14, pady=(10, 0))
        ctk.CTkLabel(
            panel_balance, text="Materiales · cajas · stock crítico",
            font=("Segoe UI", 9), text_color="#6F8EAF"
        ).pack(anchor="w", padx=14, pady=(2, 4))
        self.canvas_balance = tk.Canvas(
            panel_balance, bg="#071321", highlightthickness=0, height=205
        )
        self.canvas_balance.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.canvas_balance.bind(
            "<Configure>", lambda _e: self.after(100, self._dibujar_grafica_balance)
        )
        self._reportes_resumen = {"materiales": 0, "cajas": 0, "criticos": 0}

        # Pie de dashboard: alertas y actividad reciente.
        inferior = ctk.CTkFrame(contenido, fg_color="transparent")
        inferior.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))
        inferior.grid_columnconfigure((0, 1), weight=1, uniform="reportes_bottom")
        self.panel_alertas = ctk.CTkFrame(
            inferior, fg_color="#091625", corner_radius=11,
            border_width=1, border_color="#3A2437"
        )
        self.panel_alertas.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        ctk.CTkLabel(
            self.panel_alertas, text="⚠  ALERTAS DE INVENTARIO",
            font=("Segoe UI", 9, "bold"), text_color="#FDA4AF"
        ).pack(anchor="w", padx=12, pady=(8, 2))
        self.lbl_reportes_alertas = ctk.CTkLabel(
            self.panel_alertas, text="Cargando alertas…", font=("Segoe UI", 9),
            text_color="#B8CBE2", justify="left", anchor="w"
        )
        self.lbl_reportes_alertas.pack(fill="x", padx=12, pady=(0, 8))

        self.panel_actividad = ctk.CTkFrame(
            inferior, fg_color="#091625", corner_radius=11,
            border_width=1, border_color="#173354"
        )
        self.panel_actividad.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        ctk.CTkLabel(
            self.panel_actividad, text="◷  ACTIVIDAD RECIENTE",
            font=("Segoe UI", 9, "bold"), text_color="#7DD3FC"
        ).pack(anchor="w", padx=12, pady=(8, 2))
        self.lbl_reportes_actividad = ctk.CTkLabel(
            self.panel_actividad, text="Cargando movimientos…", font=("Segoe UI", 9),
            text_color="#B8CBE2", justify="left", anchor="w"
        )
        self.lbl_reportes_actividad.pack(fill="x", padx=12, pady=(0, 8))

        # Módulo predictivo: estima consumo reciente y posible agotamiento.
        panel_prediccion = ctk.CTkFrame(
            contenido, fg_color="#081629", corner_radius=12,
            border_width=1, border_color="#17466A"
        )
        panel_prediccion.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 16))
        panel_prediccion.grid_columnconfigure(0, weight=1)
        cab_pred = ctk.CTkFrame(panel_prediccion, fg_color="transparent")
        cab_pred.pack(fill="x", padx=14, pady=(11, 3))
        ctk.CTkLabel(
            cab_pred, text="◈  PRONÓSTICO INTELIGENTE DE INVENTARIO",
            font=("Segoe UI", 11, "bold"), text_color="#67E8F9"
        ).pack(side="left")
        ctk.CTkButton(
            cab_pred, text="↻ Recalcular", width=105, height=28, corner_radius=8,
            fg_color="#12345A", hover_color="#194777", border_width=1,
            border_color="#245482", text_color="#DCEBFF",
            command=self.actualizar_prediccion_inventario
        ).pack(side="right")
        ctk.CTkLabel(
            panel_prediccion,
            text="Estimación basada en las salidas registradas durante los últimos 30 días; no es una garantía de demanda futura.",
            font=("Segoe UI", 9), text_color="#7795B8", anchor="w", justify="left", wraplength=1100
        ).pack(fill="x", padx=14, pady=(0, 7))
        self.lbl_prediccion_inventario = ctk.CTkLabel(
            panel_prediccion, text="Calculando tendencias…", font=("Segoe UI", 10),
            text_color="#C8DDF7", anchor="w", justify="left"
        )
        self.lbl_prediccion_inventario.pack(fill="x", padx=14, pady=(0, 13))

        # Recomendaciones de compra: horizonte configurable y cantidades sugeridas.
        panel_compras = ctk.CTkFrame(
            contenido, fg_color="#081629", corner_radius=12,
            border_width=1, border_color="#245482"
        )
        panel_compras.grid(row=4, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 16))
        panel_compras.grid_columnconfigure(0, weight=1)
        cab_compras = ctk.CTkFrame(panel_compras, fg_color="transparent")
        cab_compras.pack(fill="x", padx=14, pady=(11, 5))
        ctk.CTkLabel(
            cab_compras, text="🛒  RECOMENDACIONES INTELIGENTES DE COMPRA",
            font=("Segoe UI", 11, "bold"), text_color="#67E8F9"
        ).pack(side="left")
        controles_compra = ctk.CTkFrame(cab_compras, fg_color="transparent")
        controles_compra.pack(side="right")
        ctk.CTkLabel(controles_compra, text="Entrega (días)", font=("Segoe UI", 9),
                     text_color="#9BB5D2").pack(side="left", padx=(0, 5))
        self.entry_plazo_proveedor = ctk.CTkEntry(
            controles_compra, width=55, height=28, corner_radius=7,
            fg_color="#06101E", border_color="#245482", text_color="#EAF3FF"
        )
        self.entry_plazo_proveedor.insert(0, "7")
        self.entry_plazo_proveedor.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(controles_compra, text="Reserva (días)", font=("Segoe UI", 9),
                     text_color="#9BB5D2").pack(side="left", padx=(0, 5))
        self.entry_reserva_compra = ctk.CTkEntry(
            controles_compra, width=55, height=28, corner_radius=7,
            fg_color="#06101E", border_color="#245482", text_color="#EAF3FF"
        )
        self.entry_reserva_compra.insert(0, "7")
        self.entry_reserva_compra.pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            controles_compra, text="↻ Calcular", width=95, height=28, corner_radius=8,
            fg_color="#12345A", hover_color="#194777", border_width=1,
            border_color="#245482", text_color="#DCEBFF",
            command=self.calcular_recomendaciones_compra
        ).pack(side="left")
        ctk.CTkLabel(
            panel_compras,
            text="Sugiere cantidades para cubrir el plazo de entrega más una reserva. No genera órdenes ni modifica el inventario.",
            font=("Segoe UI", 9), text_color="#7795B8", anchor="w", justify="left",
            wraplength=1100
        ).pack(fill="x", padx=14, pady=(0, 7))
        self.lbl_recomendaciones_compra = ctk.CTkLabel(
            panel_compras, text="Calculando recomendaciones…", font=("Consolas", 10),
            text_color="#C8DDF7", anchor="w", justify="left"
        )
        self.lbl_recomendaciones_compra.pack(fill="x", padx=14, pady=(0, 13))

        self._reportes_mov_dias = []
        self._reportes_categorias = []
        self._reportes_anim_job = None
        self._reportes_anim_frame = 0
        self._reportes_animando = False
        self.after(250, self.actualizar_dashboard_reportes)
        return vista


    def _crear_vista_configuracion(self, parent):
        """Centro de control con diagnóstico, respaldo de datos y preferencias visuales."""
        vista = ctk.CTkFrame(parent, fg_color="#050C18", corner_radius=14,
                             border_width=1, border_color="#102A49")
        vista.grid_columnconfigure((0, 1), weight=1, uniform="config")

        header = ctk.CTkFrame(vista, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(18, 12))
        ctk.CTkLabel(header, text="CENTRO DE CONTROL", font=("Segoe UI", 10, "bold"),
                     text_color="#38BDF8", anchor="w").pack(anchor="w")
        ctk.CTkLabel(header, text="Configuración inteligente", font=("Segoe UI", 24, "bold"),
                     text_color="#EAF3FF", anchor="w").pack(anchor="w", pady=(3, 2))
        ctk.CTkLabel(header, text="Mantenimiento, preferencias y protección de la información.",
                     font=("Segoe UI", 11), text_color="#7895B8", anchor="w").pack(anchor="w")

        estado = ctk.CTkFrame(vista, fg_color="#081629", corner_radius=13,
                              border_width=1, border_color="#173354")
        estado.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 10))
        ctk.CTkLabel(estado, text="◉  ESTADO DEL SISTEMA", font=("Segoe UI", 10, "bold"),
                     text_color="#C8DDF7").pack(anchor="w", padx=15, pady=(12, 7))
        fila = ctk.CTkFrame(estado, fg_color="transparent")
        fila.pack(fill="x", padx=12, pady=(0, 12))
        self.lbl_estado_db_materiales = ctk.CTkLabel(
            fila, text="● Materiales: comprobando…", font=("Segoe UI", 10), text_color="#94A3B8")
        self.lbl_estado_db_materiales.pack(side="left", padx=(2, 18))
        self.lbl_estado_db_cajas = ctk.CTkLabel(
            fila, text="● Rastreo de cajas: comprobando…", font=("Segoe UI", 10), text_color="#94A3B8")
        self.lbl_estado_db_cajas.pack(side="left", padx=2)
        ctk.CTkButton(fila, text="Ejecutar diagnóstico", width=145, height=30, corner_radius=8,
                      fg_color="#12345A", hover_color="#194777", border_width=1,
                      border_color="#245482", text_color="#DCEBFF",
                      command=self.ejecutar_diagnostico).pack(side="right")

        backup = ctk.CTkFrame(vista, fg_color="#081629", corner_radius=13,
                              border_width=1, border_color="#173354")
        backup.grid(row=2, column=0, sticky="nsew", padx=(16, 6), pady=5)
        ctk.CTkLabel(backup, text="◈  PROTECCIÓN DE DATOS", font=("Segoe UI", 10, "bold"),
                     text_color="#7DD3FC").pack(anchor="w", padx=15, pady=(14, 6))
        ctk.CTkLabel(backup, text="Crea una copia fechada de las bases de datos para recuperar tu información si algo sale mal.",
                     font=("Segoe UI", 10), text_color="#9AB6D5", wraplength=360,
                     justify="left").pack(anchor="w", padx=15, pady=(0, 12))
        ctk.CTkButton(backup, text="▣  Crear copia de seguridad", height=38, corner_radius=9,
                      fg_color="#0F766E", hover_color="#115E59", text_color="#ECFEFF",
                      command=self.crear_copia_seguridad).pack(fill="x", padx=15, pady=(0, 10))
        self.lbl_backup_resultado = ctk.CTkLabel(
            backup, text="Seleccionarás la carpeta de destino al crear el respaldo.",
            font=("Segoe UI", 9), text_color="#6F91B8", wraplength=350, justify="left")
        self.lbl_backup_resultado.pack(anchor="w", padx=15, pady=(0, 14))

        prefs = ctk.CTkFrame(vista, fg_color="#081629", corner_radius=13,
                             border_width=1, border_color="#173354")
        prefs.grid(row=2, column=1, sticky="nsew", padx=(6, 16), pady=5)
        ctk.CTkLabel(prefs, text="✧  EXPERIENCIA DE USO", font=("Segoe UI", 10, "bold"),
                     text_color="#C4B5FD").pack(anchor="w", padx=15, pady=(14, 6))
        ctk.CTkLabel(prefs, text="Ajusta el movimiento ambiental y actualiza los indicadores sin salir de esta sección.",
                     font=("Segoe UI", 10), text_color="#9AB6D5", wraplength=360,
                     justify="left").pack(anchor="w", padx=15, pady=(0, 10))
        self.var_animaciones_suaves = tk.BooleanVar(value=True)
        ctk.CTkSwitch(prefs, text="Animaciones ambientales suaves",
                      variable=self.var_animaciones_suaves, onvalue=True, offvalue=False,
                      progress_color="#2563EB", button_color="#DCEBFF",
                      command=self.cambiar_animaciones_suaves).pack(anchor="w", padx=15, pady=(0, 10))
        ctk.CTkButton(prefs, text="↻  Actualizar métricas y dashboard", height=36, corner_radius=9,
                      fg_color="#12345A", hover_color="#194777", border_width=1,
                      border_color="#245482", text_color="#DCEBFF",
                      command=self.actualizar_desde_configuracion).pack(fill="x", padx=15, pady=(0, 10))
        ctk.CTkLabel(prefs, text="Las preferencias visuales se aplican durante esta sesión.",
                     font=("Segoe UI", 9), text_color="#6F91B8", wraplength=350,
                     justify="left").pack(anchor="w", padx=15, pady=(0, 14))

        ctk.CTkLabel(vista, text="AZ SYSTEMS  /  CONTROL CENTER",
                     font=("Consolas", 9, "bold"), text_color="#315779").grid(
            row=3, column=0, sticky="w", padx=20, pady=(12, 16))
        ctk.CTkLabel(vista, text="Modo local · SQLite", font=("Segoe UI", 9),
                     text_color="#56799B").grid(row=3, column=1, sticky="e", padx=20, pady=(12, 16))
        self.after(500, self.ejecutar_diagnostico)
        return vista

    def mostrar_configuracion(self):
        self._animar_barra_kpis(False)
        self._animar_cambio_vista(self.vista_configuracion)
        self.btn_pill_m.configure(fg_color="transparent", text_color="#94A3B8")
        self.btn_pill_c.configure(fg_color="transparent", text_color="#94A3B8")
        self.ejecutar_diagnostico()
        self.actualizar_kpis()

    def ejecutar_diagnostico(self):
        """Comprueba acceso y consistencia básica de las bases de datos locales."""
        if not hasattr(self, "lbl_estado_db_materiales"):
            return
        for nombre, etiqueta, titulo in (
            ("almacen_materiales.db", self.lbl_estado_db_materiales, "Materiales"),
            ("rastreo_cajas_almacen.db", self.lbl_estado_db_cajas, "Rastreo de cajas"),
        ):
            ruta = ruta_base_datos(nombre)
            try:
                if not os.path.exists(ruta):
                    etiqueta.configure(text=f"● {titulo}: archivo no encontrado", text_color="#FBBF24")
                    continue
                with sqlite3.connect(ruta, timeout=2) as conn:
                    resultado = conn.execute("PRAGMA quick_check").fetchone()
                if resultado and resultado[0] == "ok":
                    etiqueta.configure(text=f"● {titulo}: disponible", text_color="#34D399")
                else:
                    etiqueta.configure(text=f"● {titulo}: revisar base de datos", text_color="#FB7185")
            except sqlite3.Error:
                etiqueta.configure(text=f"● {titulo}: revisar base de datos", text_color="#FB7185")

    def crear_copia_seguridad(self):
        """Genera respaldos con marca de tiempo usando la API de copia de SQLite."""
        carpeta = filedialog.askdirectory(title="Selecciona dónde guardar la copia de seguridad")
        if not carpeta:
            return
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        copiados = []
        for nombre in ("almacen_materiales.db", "rastreo_cajas_almacen.db"):
            origen = ruta_base_datos(nombre)
            if not os.path.isfile(origen):
                continue
            destino = os.path.join(carpeta, f"{os.path.splitext(nombre)[0]}_{marca}.db")
            try:
                with sqlite3.connect(origen, timeout=5) as db_origen:
                    with sqlite3.connect(destino) as db_destino:
                        db_origen.backup(db_destino)
                copiados.append(os.path.basename(destino))
            except sqlite3.Error as exc:
                messagebox.showerror("Error de copia de seguridad", f"No se pudo copiar {nombre}:\\n{exc}")
                return
        if copiados:
            self.lbl_backup_resultado.configure(
                text=f"✓ Copia creada: {len(copiados)} base(s)\\n" + "\\n".join(copiados),
                text_color="#34D399")
            messagebox.showinfo("Copia de seguridad completada",
                                "Se guardaron las bases detectadas en:\\n" + carpeta)
        else:
            self.lbl_backup_resultado.configure(
                text="No se encontraron bases de datos para copiar.", text_color="#FBBF24")
            messagebox.showwarning("Sin bases de datos",
                                   "No se encontraron archivos de base de datos en la carpeta del programa.")

    def cambiar_animaciones_suaves(self):
        activas = bool(self.var_animaciones_suaves.get())
        if not activas:
            for card, color in zip(self._kpi_cards, self._kpi_bordes_base):
                try:
                    card.configure(border_color=color)
                except tk.TclError:
                    pass
        self.lbl_status_sistema.configure(
            text="● Sistema en línea" if activas else "● Sistema en línea · efectos reducidos",
            text_color="#10B981")

    def actualizar_desde_configuracion(self):
        self.actualizar_kpis()
        if hasattr(self, "vista_reportes"):
            self.actualizar_dashboard_reportes()
        self.ejecutar_diagnostico()
        messagebox.showinfo("Sistema actualizado", "Se actualizaron las métricas y el diagnóstico del sistema.")

    def _consultar_datos_dashboard(self):
        """Lee datos reales de ambas bases; si una no existe, reporta ceros sin fallar."""
        datos = {
            "materiales": 0, "cajas": 0, "criticos": 0, "movimientos": 0,
            "dias": [], "categorias": [], "alertas": [], "actividad": []
        }
        hoy = datetime.now().date()
        fechas = [(hoy - timedelta(days=i)) for i in range(6, -1, -1)]
        conteo_dias = {f.strftime("%Y-%m-%d"): {"INGRESO": 0, "SALIDA": 0} for f in fechas}
        categorias = {}

        # Inventario de materiales y movimientos de su base de datos.
        try:
            conn = sqlite3.connect(ruta_base_datos("almacen_materiales.db"))
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), SUM(CASE WHEN cantidad <= stock_minimo THEN 1 ELSE 0 END) FROM materiales")
            row = cur.fetchone() or (0, 0)
            datos["materiales"] = int(row[0] or 0)
            datos["criticos"] = int(row[1] or 0)
            cur.execute("SELECT COALESCE(NULLIF(TRIM(categoria), ''), 'Sin categoría'), COUNT(*) FROM materiales GROUP BY COALESCE(NULLIF(TRIM(categoria), ''), 'Sin categoría') ORDER BY COUNT(*) DESC LIMIT 6")
            categorias.update({str(r[0]): int(r[1] or 0) for r in cur.fetchall()})
            cur.execute("SELECT codigo, descripcion, cantidad, stock_minimo, unidad FROM materiales WHERE cantidad <= stock_minimo ORDER BY cantidad ASC LIMIT 3")
            datos["alertas"] = [("MATERIAL", *r) for r in cur.fetchall()]
            cur.execute("SELECT codigo, tipo, cantidad, unidad, fecha FROM movimientos ORDER BY fecha DESC LIMIT 5")
            movimientos = cur.fetchall()
            for codigo, tipo, cantidad, unidad, fecha in movimientos:
                if fecha:
                    clave = str(fecha)[:10]
                    if clave in conteo_dias and tipo in conteo_dias[clave]:
                        conteo_dias[clave][tipo] += 1
                datos["actividad"].append((str(fecha or "")[-8:-3], str(tipo), str(codigo), float(cantidad or 0), str(unidad or "")))
            cur.execute("SELECT COUNT(*) FROM movimientos WHERE substr(fecha, 1, 10) >= ?", ((hoy - timedelta(days=6)).strftime("%Y-%m-%d"),))
            datos["movimientos"] += int(cur.fetchone()[0] or 0)
            conn.close()
        except (sqlite3.Error, OSError):
            try:
                conn.close()
            except Exception:
                pass

        # Rastreo de cajas usa el mismo esquema general, pero se resume como cajas.
        try:
            conn = sqlite3.connect(ruta_base_datos("rastreo_cajas_almacen.db"))
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*), SUM(CASE WHEN cantidad <= stock_minimo THEN 1 ELSE 0 END) FROM materiales")
            row = cur.fetchone() or (0, 0)
            datos["cajas"] = int(row[0] or 0)
            datos["criticos"] += int(row[1] or 0)
            cur.execute("SELECT COALESCE(NULLIF(TRIM(categoria), ''), 'Sin categoría'), COUNT(*) FROM materiales GROUP BY COALESCE(NULLIF(TRIM(categoria), ''), 'Sin categoría') ORDER BY COUNT(*) DESC LIMIT 6")
            for cat, cantidad in cur.fetchall():
                nombre = "Cajas · " + str(cat)
                categorias[nombre] = int(cantidad or 0)
            cur.execute("SELECT codigo, tipo, cantidad, unidad, fecha FROM movimientos ORDER BY fecha DESC LIMIT 5")
            for codigo, tipo, cantidad, unidad, fecha in cur.fetchall():
                if fecha:
                    clave = str(fecha)[:10]
                    if clave in conteo_dias and tipo in conteo_dias[clave]:
                        conteo_dias[clave][tipo] += 1
                datos["actividad"].append((str(fecha or "")[-8:-3], str(tipo), str(codigo), float(cantidad or 0), str(unidad or "")))
            cur.execute("SELECT COUNT(*) FROM movimientos WHERE substr(fecha, 1, 10) >= ?", ((hoy - timedelta(days=6)).strftime("%Y-%m-%d"),))
            datos["movimientos"] += int(cur.fetchone()[0] or 0)
            conn.close()
        except (sqlite3.Error, OSError):
            try:
                conn.close()
            except Exception:
                pass

        datos["dias"] = [(fecha, valores["INGRESO"], valores["SALIDA"]) for fecha, valores in conteo_dias.items()]
        datos["categorias"] = sorted(categorias.items(), key=lambda item: item[1], reverse=True)[:6]
        datos["actividad"] = sorted(datos["actividad"], reverse=True)[:4]
        return datos

    def actualizar_dashboard_reportes(self):
        if not hasattr(self, "canvas_movimientos"):
            return
        datos = self._consultar_datos_dashboard()
        self._reportes_mov_dias = datos["dias"]
        self._reportes_categorias = datos["categorias"]
        self._reportes_resumen = {k: int(datos.get(k, 0) or 0) for k in ("materiales", "cajas", "criticos")}
        alertas = datos["alertas"]
        if alertas:
            lineas = [f"• {tipo}  {codigo}  ·  stock {cantidad:g} {unidad} / mín. {minimo:g}"
                      for tipo, codigo, descripcion, cantidad, minimo, unidad in alertas]
            self.lbl_reportes_alertas.configure(text="\n".join(lineas))
        else:
            self.lbl_reportes_alertas.configure(text="✓  Sin alertas de stock mínimo")
        actividad = datos["actividad"]
        if actividad:
            lineas = [f"{hora or '--:--'}  {tipo:<7}  {codigo}  ·  {cantidad:g} {unidad}"
                      for hora, tipo, codigo, cantidad, unidad in actividad]
            self.lbl_reportes_actividad.configure(text="\n".join(lineas))
        else:
            self.lbl_reportes_actividad.configure(text="Sin movimientos recientes")
        self.lbl_reportes_actualizado.configure(text="ACTUALIZADO · " + datetime.now().strftime("%H:%M:%S"))
        self.actualizar_prediccion_inventario()
        self.calcular_recomendaciones_compra()
        self._iniciar_animacion_graficas()

    def actualizar_prediccion_inventario(self):
        """Pronóstico heurístico transparente: consumo medio y días estimados hasta agotamiento."""
        etiqueta = getattr(self, "lbl_prediccion_inventario", None)
        if etiqueta is None or not etiqueta.winfo_exists():
            return
        fecha_limite = (datetime.now().date() - timedelta(days=29)).strftime("%Y-%m-%d")
        predicciones = []
        bases = [
            ("almacen_materiales.db", "MATERIAL"),
            ("rastreo_cajas_almacen.db", "CAJA"),
        ]
        for archivo, tipo_item in bases:
            conn = None
            try:
                conn = sqlite3.connect(ruta_base_datos(archivo), timeout=2)
                cur = conn.cursor()
                cur.execute("""
                    SELECT m.codigo, COALESCE(m.descripcion, m.codigo),
                           COALESCE(m.cantidad, 0), COALESCE(m.stock_minimo, 0),
                           COALESCE(m.unidad, ''), COALESCE(SUM(CASE
                               WHEN UPPER(mov.tipo) IN ('SALIDA', 'EGRESO')
                               THEN ABS(mov.cantidad) ELSE 0 END), 0)
                    FROM materiales m
                    LEFT JOIN movimientos mov
                      ON mov.material_id = m.id
                     AND substr(mov.fecha, 1, 10) >= ?
                    GROUP BY m.id, m.codigo, m.descripcion, m.cantidad, m.stock_minimo, m.unidad
                """, (fecha_limite,))
                for codigo, descripcion, stock, minimo, unidad, salida_30d in cur.fetchall():
                    stock = float(stock or 0)
                    minimo = float(minimo or 0)
                    consumo_diario = float(salida_30d or 0) / 30.0
                    if consumo_diario <= 0:
                        continue
                    dias = max(0.0, stock) / consumo_diario
                    predicciones.append({
                        "tipo": tipo_item, "codigo": str(codigo), "descripcion": str(descripcion),
                        "stock": stock, "minimo": minimo, "unidad": str(unidad),
                        "diario": consumo_diario, "semana": consumo_diario * 7,
                        "dias": dias, "salida30": float(salida_30d or 0)
                    })
            except (sqlite3.Error, OSError):
                # Una base ausente o con esquema incompatible no impide analizar la otra.
                pass
            finally:
                if conn is not None:
                    conn.close()

        predicciones.sort(key=lambda x: (x["dias"], -x["diario"]))
        cercanas = [p for p in predicciones if p["dias"] <= 60][:6]
        if not predicciones:
            etiqueta.configure(text="Aún no hay salidas registradas suficientes en los últimos 30 días para estimar el consumo. Registra movimientos y vuelve a calcular.", text_color="#A7BED8")
            return
        if not cercanas:
            top = predicciones[:3]
            lineas = ["✓ No se estima agotamiento en los próximos 60 días para los artículos con consumo registrado."]
        else:
            top = cercanas
            lineas = ["ARTÍCULO                         STOCK       CONSUMO/7 DÍAS       AGOTAMIENTO ESTIMADO"]
        for p in top:
            plazo = "agotado / sin stock" if p["dias"] <= 0 else f"~{p['dias']:.0f} días"
            lineas.append(f"• {p['tipo']} · {p['codigo']} — {p['descripcion'][:28]}  |  {p['stock']:g} {p['unidad']}  |  {p['semana']:.1f} {p['unidad']}  |  {plazo}")
        lineas.append("Modelo simple de tendencia: promedio de salidas de 30 días; no contempla compras futuras ni cambios estacionales.")
        etiqueta.configure(text="\n".join(lineas), text_color="#C8DDF7")

    def calcular_recomendaciones_compra(self):
        """Sugiere reposición con consumo de 30 días, plazo de entrega y reserva configurable."""
        etiqueta = getattr(self, "lbl_recomendaciones_compra", None)
        if etiqueta is None or not etiqueta.winfo_exists():
            return

        try:
            plazo_entrega = int((self.entry_plazo_proveedor.get() or "7").strip())
            reserva_dias = int((self.entry_reserva_compra.get() or "7").strip())
            if plazo_entrega < 0 or reserva_dias < 0:
                raise ValueError
        except (ValueError, AttributeError):
            etiqueta.configure(
                text="Introduce números enteros válidos (0 o más) para el plazo de entrega y la reserva.",
                text_color="#FDA4AF"
            )
            return

        fecha_limite = (datetime.now().date() - timedelta(days=29)).strftime("%Y-%m-%d")
        recomendaciones = []
        errores = []
        for archivo, tipo_item in (
            ("almacen_materiales.db", "MATERIAL"),
            ("rastreo_cajas_almacen.db", "CAJA"),
        ):
            conn = None
            try:
                conn = sqlite3.connect(ruta_base_datos(archivo), timeout=2)
                cur = conn.cursor()
                cur.execute("""
                    SELECT m.codigo, COALESCE(m.descripcion, m.codigo),
                           COALESCE(m.cantidad, 0), COALESCE(m.stock_minimo, 0),
                           COALESCE(m.unidad, ''),
                           COALESCE(SUM(CASE
                               WHEN UPPER(mov.tipo) IN ('SALIDA', 'EGRESO')
                               THEN ABS(mov.cantidad) ELSE 0 END), 0)
                    FROM materiales m
                    LEFT JOIN movimientos mov
                      ON mov.material_id = m.id
                     AND substr(mov.fecha, 1, 10) >= ?
                    GROUP BY m.id, m.codigo, m.descripcion, m.cantidad, m.stock_minimo, m.unidad
                """, (fecha_limite,))
                for codigo, descripcion, stock, minimo, unidad, salidas in cur.fetchall():
                    stock = max(0.0, float(stock or 0))
                    minimo = max(0.0, float(minimo or 0))
                    diario = max(0.0, float(salidas or 0)) / 30.0
                    # El objetivo cubre plazo + reserva, pero nunca queda por debajo del stock mínimo.
                    objetivo = max(minimo, diario * (plazo_entrega + reserva_dias))
                    cantidad_compra = max(0.0, objetivo - stock)
                    if cantidad_compra > 0:
                        recomendaciones.append({
                            "tipo": tipo_item, "codigo": str(codigo),
                            "descripcion": str(descripcion), "stock": stock,
                            "minimo": minimo, "unidad": str(unidad),
                            "diario": diario, "objetivo": objetivo,
                            "compra": cantidad_compra, "salidas": float(salidas or 0)
                        })
            except (sqlite3.Error, OSError) as exc:
                errores.append(f"{tipo_item}: no se pudo consultar ({exc.__class__.__name__})")
            finally:
                if conn is not None:
                    conn.close()

        recomendaciones.sort(key=lambda x: (x["diario"] <= 0, -x["compra"], x["stock"]))
        if not recomendaciones:
            msg = "✓ No se detectan reposiciones necesarias con los parámetros actuales."
            if errores:
                msg += "\nVerifica que las bases de datos existan y tengan las tablas materiales y movimientos."
            else:
                msg += "\nSi faltan artículos, registra salidas históricas o revisa sus stocks mínimos."
            etiqueta.configure(text=msg, text_color="#86EFAC")
            return

        encabezado = (
            f"{'TIPO':<8} {'CÓDIGO':<15} {'STOCK':>9} {'OBJETIVO':>10} "
            f"{'SUGERIDO':>10}  {'MOTIVO'}"
        )
        lineas = [encabezado, "─" * 82]
        for item in recomendaciones[:12]:
            if item["diario"] > 0:
                motivo = f"consumo {item['diario']:.2f}/{item['unidad'] or 'u'} al día"
            elif item["stock"] <= item["minimo"]:
                motivo = "stock en/por debajo del mínimo"
            else:
                motivo = "ajuste al mínimo configurado"
            lineas.append(
                f"{item['tipo']:<8} {item['codigo'][:14]:<15} {item['stock']:>9.1f} "
                f"{item['objetivo']:>10.1f} {item['compra']:>10.1f}  {motivo}"
            )
        if len(recomendaciones) > 12:
            lineas.append(f"… y {len(recomendaciones) - 12} artículo(s) más.")
        lineas.append(
            f"Artículos a reponer: {len(recomendaciones)} · "
            f"plazo {plazo_entrega} días · reserva {reserva_dias} días."
        )
        lineas.append("Cantidades estimadas; redondea según presentación de compra y valida con el proveedor.")
        if errores:
            lineas.append("Aviso: " + "; ".join(errores))
        etiqueta.configure(text="\n".join(lineas), text_color="#C8DDF7")

    def _iniciar_animacion_graficas(self):
        """Inicia una entrada suave de las gráficas sin bloquear la interfaz."""
        job = getattr(self, "_reportes_anim_job", None)
        if job:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
        self._reportes_anim_job = None
        self._reportes_anim_frame = 0
        self._reportes_animando = True
        self._paso_animacion_graficas()

    def _paso_animacion_graficas(self):
        """Avanza la animación con pasos cortos y curva ease-in-out."""
        if not getattr(self, "_reportes_animando", False):
            self._reportes_anim_job = None
            return
        if not self.winfo_exists():
            self._reportes_animando = False
            self._reportes_anim_job = None
            return

        self._reportes_anim_frame = min(24, self._reportes_anim_frame + 1)
        self._dibujar_grafica_movimientos()
        self._dibujar_grafica_categorias()
        self._dibujar_grafica_balance()

        if self._reportes_anim_frame < 24:
            self._reportes_anim_job = self.after(16, self._paso_animacion_graficas)
        else:
            self._reportes_animando = False
            self._reportes_anim_job = None

    def _dibujar_grafica_movimientos(self):
        canvas = getattr(self, "canvas_movimientos", None)
        if not canvas or not canvas.winfo_exists():
            return
        canvas.delete("all")
        w, h = max(canvas.winfo_width(), 260), max(canvas.winfo_height(), 150)
        datos = getattr(self, "_reportes_mov_dias", [])
        maximo = max([max(ingreso, salida) for _, ingreso, salida in datos] + [1])
        margen_izq, margen_der, margen_sup, margen_inf = 30, 14, 10, 28
        ancho_util = w - margen_izq - margen_der
        alto_util = h - margen_sup - margen_inf
        for nivel in range(4):
            y = margen_sup + alto_util * nivel / 3
            canvas.create_line(margen_izq, y, w - margen_der, y, fill="#122943", dash=(2, 4))
        paso = ancho_util / max(len(datos), 1)
        factor = min(1.0, getattr(self, "_reportes_anim_frame", 24) / 24)
        factor = factor * factor * (3 - 2 * factor)
        for i, (fecha, ingreso, salida) in enumerate(datos):
            centro = margen_izq + paso * (i + 0.5)
            bar_w = max(5, min(16, paso * 0.22))
            for desplazamiento, valor, color in [(-bar_w * 0.65, ingreso, "#38BDF8"), (bar_w * 0.65, salida, "#8B5CF6")]:
                alto = (valor / maximo) * alto_util * factor
                x0 = centro + desplazamiento - bar_w / 2
                x1 = x0 + bar_w
                y0 = margen_sup + alto_util - alto
                canvas.create_rectangle(x0, y0, x1, margen_sup + alto_util, fill=color, outline="")
                if valor and alto > 5:
                    canvas.create_line(x0 + 1, y0 + 1, x1 - 1, y0 + 1, fill="#DDF5FF", width=1)
                if valor and factor > 0.75:
                    canvas.create_text((x0 + x1) / 2, y0 - 8, text=str(valor), fill="#B9D7F5", font=("Segoe UI", 8))
            etiqueta = fecha[5:] if len(fecha) >= 10 else fecha
            canvas.create_text(centro, h - 12, text=etiqueta, fill="#7795B8", font=("Segoe UI", 8))
        canvas.create_rectangle(w - 145, 5, w - 135, 15, fill="#38BDF8", outline="")
        canvas.create_text(w - 129, 10, text="Entradas", anchor="w", fill="#9AB6D5", font=("Segoe UI", 8))
        canvas.create_rectangle(w - 75, 5, w - 65, 15, fill="#8B5CF6", outline="")
        canvas.create_text(w - 59, 10, text="Salidas", anchor="w", fill="#9AB6D5", font=("Segoe UI", 8))

    def _dibujar_grafica_categorias(self):
        canvas = getattr(self, "canvas_categorias", None)
        if not canvas or not canvas.winfo_exists():
            return
        canvas.delete("all")
        w, h = max(canvas.winfo_width(), 260), max(canvas.winfo_height(), 150)
        datos = getattr(self, "_reportes_categorias", [])
        if not datos:
            canvas.create_text(w / 2, h / 2, text="Sin categorías para mostrar",
                               fill="#6F8EAF", font=("Segoe UI", 10))
            return
        maximo = max([v for _, v in datos] + [1])
        margen_izq, margen_der, margen_sup, alto_fila = 12, 35, 8, 27
        factor = min(1.0, getattr(self, "_reportes_anim_frame", 24) / 24)
        factor = factor * factor * (3 - 2 * factor)
        for i, (nombre, valor) in enumerate(datos):
            y = margen_sup + i * alto_fila
            if y + alto_fila > h - 4:
                break
            texto = nombre if len(nombre) < 24 else nombre[:21] + "…"
            canvas.create_text(margen_izq, y + 6, text=texto, anchor="w",
                               fill="#9AB6D5", font=("Segoe UI", 8))
            x0, x1 = margen_izq, w - margen_der
            largo = (x1 - x0) * valor / maximo * factor
            canvas.create_rectangle(x0, y + 13, x1, y + 22,
                                    fill="#10263E", outline="")
            if largo > 2:
                canvas.create_rectangle(x0, y + 13, x0 + largo, y + 22,
                                        fill="#0EA5E9", outline="")
                canvas.create_line(x0 + 1, y + 14, max(x0 + 1, x0 + largo - 1), y + 14,
                                   fill="#7DD3FC", width=1)
            canvas.create_text(w - 12, y + 17, text=str(valor), anchor="e",
                               fill="#D6E8FC", font=("Segoe UI", 8, "bold"))

    def _dibujar_grafica_balance(self):
        """Gráfica compacta tipo anillo con proporciones reales del sistema."""
        canvas = getattr(self, "canvas_balance", None)
        if not canvas or not canvas.winfo_exists():
            return
        canvas.delete("all")
        w, h = max(canvas.winfo_width(), 220), max(canvas.winfo_height(), 150)
        resumen = getattr(self, "_reportes_resumen", {})
        materiales = max(0, int(resumen.get("materiales", 0)))
        cajas = max(0, int(resumen.get("cajas", 0)))
        criticos = max(0, int(resumen.get("criticos", 0)))
        total = materiales + cajas
        cx, cy = w * 0.5, h * 0.39
        radio = min(w * 0.28, h * 0.29, 58)
        colores = ["#38BDF8", "#8B5CF6"]
        if total:
            inicio = 90
            for valor, color in zip((materiales, cajas), colores):
                if valor <= 0:
                    continue
                extension = 360 * valor / total
                canvas.create_arc(cx-radio, cy-radio, cx+radio, cy+radio,
                                  start=inicio, extent=-extension, style="arc",
                                  outline="#142B45", width=15)
                canvas.create_arc(cx-radio, cy-radio, cx+radio, cy+radio,
                                  start=inicio, extent=-extension, style="arc",
                                  outline=color, width=10)
                inicio -= extension
            canvas.create_text(cx, cy-5, text=str(total), fill="#F1F7FF",
                               font=("Segoe UI", 18, "bold"))
            canvas.create_text(cx, cy+15, text="REGISTROS", fill="#7695B8",
                               font=("Segoe UI", 7, "bold"))
        else:
            canvas.create_oval(cx-radio, cy-radio, cx+radio, cy+radio,
                               outline="#18324F", width=10)
            canvas.create_text(cx, cy, text="—", fill="#7895B8", font=("Segoe UI", 18, "bold"))
        leyenda_y = h * 0.77
        for i, (label, valor, color) in enumerate([
            ("Materiales", materiales, colores[0]), ("Cajas", cajas, colores[1]),
            ("Stock crítico", criticos, "#FB7185")
        ]):
            y = leyenda_y + i * 17
            canvas.create_oval(12, y-4, 20, y+4, fill=color, outline="")
            canvas.create_text(27, y, text=label, anchor="w", fill="#9AB6D5",
                               font=("Segoe UI", 8))
            canvas.create_text(w-12, y, text=str(valor), anchor="e", fill="#E0EEFF",
                               font=("Segoe UI", 8, "bold"))

    def _animar_barra_kpis(self, mostrar):
        """Oculta los KPI redundantes en Dashboard y los restaura al salir, con animación."""
        if not hasattr(self, "frame_kpis"):
            return
        if self._kpi_animacion_id is not None:
            try:
                self.after_cancel(self._kpi_animacion_id)
            except tk.TclError:
                pass
            self._kpi_animacion_id = None

        barra = self.frame_kpis
        if mostrar:
            if self._kpi_barra_visible and barra.winfo_manager():
                return
            barra.grid(row=1, column=0, sticky="ew", pady=(0, 10))
            inicio, fin = 0, self._kpi_altura
        else:
            if not self._kpi_barra_visible:
                return
            inicio, fin = self._kpi_altura, 0

        pasos = 12
        estado = {"paso": 0}
        self._kpi_barra_visible = mostrar
        barra.configure(height=inicio)

        def avanzar():
            if not barra.winfo_exists():
                return
            estado["paso"] += 1
            t = min(1.0, estado["paso"] / pasos)
            suave = t * t * (3 - 2 * t)
            alto = round(inicio + (fin - inicio) * suave)
            barra.configure(height=max(1, alto))
            if estado["paso"] < pasos:
                self._kpi_animacion_id = self.after(16, avanzar)
            else:
                self._kpi_animacion_id = None
                if mostrar:
                    barra.configure(height=self._kpi_altura)
                else:
                    barra.grid_remove()
                    barra.configure(height=self._kpi_altura)

        avanzar()

    def mostrar_reportes(self):
        self._animar_barra_kpis(False)
        self._animar_cambio_vista(self.vista_reportes)
        self.btn_pill_m.configure(fg_color="transparent", text_color="#94A3B8")
        self.btn_pill_c.configure(fg_color="transparent", text_color="#94A3B8")
        self.actualizar_dashboard_reportes()
        self.actualizar_kpis()

    def mostrar_materiales(self):
        self._animar_barra_kpis(True)
        self._animar_cambio_vista(self.vista_materiales)
        self.btn_pill_m.configure(fg_color="#2563EB", text_color="#FFFFFF")
        self.btn_pill_c.configure(fg_color="transparent", text_color="#94A3B8")
        self.actualizar_kpis()

    def mostrar_cajas(self):
        self._animar_barra_kpis(True)
        self._animar_cambio_vista(self.vista_cajas)
        self.btn_pill_c.configure(fg_color="#2563EB", text_color="#FFFFFF")
        self.btn_pill_m.configure(fg_color="transparent", text_color="#94A3B8")
        self.actualizar_kpis()


class ModuloMaterialesNeon(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        self.DB = ruta_base_datos("almacen_materiales.db")
        self.CARPETA_FOTOS = "fotos_materiales"
        os.makedirs(self.CARPETA_FOTOS, exist_ok=True)

        self.COLOR_PANEL = "#07111F"
        self.COLOR_CARD_HEADER = "#0B1A2D"
        self.COLOR_PRIMARIO = "#2563EB"
        self.COLOR_TEXTO = "#EAF3FF"
        self.COLOR_SECUNDARIO = "#91ACCD"
        self.COLOR_BORDE = "#12345A"

        self.foto_seleccionada = None
        self.imagen_detalle = None

        self.crear_base_datos()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        self.crear_formulario()
        self.crear_panel_derecho()

        self.cargar_materiales()

    def conectar(self):
        return sqlite3.connect(self.DB)

    def crear_base_datos(self):
        conexion = self.conectar()
        cursor = conexion.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS materiales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                descripcion TEXT NOT NULL,
                categoria TEXT,
                especificacion TEXT,
                materia_prima TEXT,
                cantidad REAL DEFAULT 0,
                unidad TEXT DEFAULT 'KG',
                stock_minimo REAL DEFAULT 0,
                ubicacion TEXT,
                observaciones TEXT,
                foto TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER NOT NULL,
                codigo TEXT NOT NULL,
                tipo TEXT NOT NULL,
                cantidad REAL NOT NULL,
                unidad TEXT NOT NULL,
                fecha TEXT NOT NULL,
                solicitante TEXT,
                area_proyecto TEXT,
                observaciones TEXT,
                FOREIGN KEY(material_id) REFERENCES materiales(id) ON DELETE CASCADE
            )
        """)
        conexion.commit()
        conexion.close()

    def crear_card(self, parent, **kwargs):
        return tk.Frame(parent, bg=self.COLOR_PANEL, highlightbackground=self.COLOR_BORDE, highlightthickness=1, bd=0, **kwargs)

    def crear_boton(self, parent, texto, comando, color, hover_color=None, ancho=None):
        if not hover_color: hover_color = color
        btn = tk.Button(parent, text=texto, command=comando, bg=color, fg="white", activebackground=hover_color,
                        activeforeground="white", font=("Segoe UI", 9, "bold"), relief="flat", bd=0, cursor="hand2", padx=12, pady=7)
        if ancho: btn.config(width=ancho)
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_color, relief="flat"))
        btn.bind("<Leave>", lambda e: btn.config(bg=color))
        return btn

    def crear_entry(self, parent, width=22):
        """Campo redondeado, oscuro y con borde azul al recibir el foco."""
        entry = ctk.CTkEntry(
            parent,
            width=max(110, int(width * 9.2)),
            height=30,
            corner_radius=9,
            border_width=1,
            fg_color="#061121",
            text_color="#E5F0FF",
            placeholder_text_color="#6382A8",
            border_color="#16385E",
            font=("Segoe UI", 10)
        )
        entry.bind("<FocusIn>", lambda _e: entry.configure(border_color="#168BFF"))
        entry.bind("<FocusOut>", lambda _e: entry.configure(border_color="#16385E"))
        return entry

    def crear_formulario(self):
        panel_form = self.crear_card(self)
        panel_form.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)

        header_form = tk.Frame(panel_form, bg=self.COLOR_CARD_HEADER)
        header_form.pack(fill="x")
        tk.Label(header_form, text="🌪  Registrar Material", font=("Segoe UI", 10, "bold"), bg=self.COLOR_CARD_HEADER, fg=self.COLOR_TEXTO, pady=10).pack(anchor="w", padx=12)

        # El botón de guardar queda fijo abajo; los campos pueden desplazarse
        # dentro de esta zona cuando la pantalla no tiene suficiente altura.
        footer_guardar = tk.Frame(panel_form, bg=self.COLOR_PANEL)
        footer_guardar.pack(side="bottom", fill="x", padx=12, pady=(4, 10))

        self.boton_guardar_material = self.crear_boton(
            footer_guardar, "📥  REGISTRAR MATERIAL", self.agregar_material,
            "#0759E8", hover_color="#1677FF", ancho=24
        )
        self.boton_guardar_material.configure(
            font=("Segoe UI", 10, "bold"), pady=10,
            highlightthickness=1, highlightbackground="#287DFF",
            activeforeground="white"
        )
        self.boton_guardar_material.pack(fill="x", ipady=1)

        form_campos = ctk.CTkScrollableFrame(
            panel_form, fg_color=self.COLOR_PANEL, corner_radius=0,
            scrollbar_button_color="#16385E",
            scrollbar_button_hover_color="#168BFF"
        )
        form_campos.pack(padx=6, pady=(6, 2), fill="both", expand=True)

        def agregar_etiqueta(texto):
            tk.Label(form_campos, text=texto, font=("Segoe UI", 8, "bold"), bg=self.COLOR_PANEL, fg=self.COLOR_SECUNDARIO).pack(anchor="w", pady=(3, 0))

        agregar_etiqueta("CÓDIGO *")
        self.entrada_codigo = self.crear_entry(form_campos, width=28)
        self.entrada_codigo.pack(anchor="w", pady=(0, 2))

        agregar_etiqueta("DESCRIPCIÓN / NOMBRE *")
        self.entrada_descripcion = self.crear_entry(form_campos, width=28)
        self.entrada_descripcion.pack(anchor="w", pady=(0, 2))

        agregar_etiqueta("CATEGORÍA")
        categorias = ["Componentes / Revestimiento", "Tubería / Valvulería", "Metales / Perfiles", "Fluidos / Químicos", "Otros"]
        self.combo_categoria = ttk.Combobox(form_campos, values=categorias, width=26, state="readonly")
        self.combo_categoria.pack(anchor="w", pady=(0, 2))

        agregar_etiqueta("ESPECIFICACIÓN / DIMENSIÓN")
        self.entrada_especificacion = self.crear_entry(form_campos, width=28)
        self.entrada_especificacion.pack(anchor="w", pady=(0, 2))

        agregar_etiqueta("MATERIA PRIMA / ALEACIÓN")
        self.entrada_materia_prima = self.crear_entry(form_campos, width=28)
        self.entrada_materia_prima.pack(anchor="w", pady=(0, 2))

        frame_cant_unid = tk.Frame(form_campos, bg=self.COLOR_PANEL)
        frame_cant_unid.pack(fill="x", pady=2)

        f_cant = tk.Frame(frame_cant_unid, bg=self.COLOR_PANEL)
        f_cant.pack(side="left", fill="x", expand=True)
        tk.Label(f_cant, text="STOCK INICIAL", font=("Segoe UI", 8, "bold"), bg=self.COLOR_PANEL, fg=self.COLOR_SECUNDARIO).pack(anchor="w")
        self.entrada_cantidad = self.crear_entry(f_cant, width=11)
        self.entrada_cantidad.pack(anchor="w")

        f_unid = tk.Frame(frame_cant_unid, bg=self.COLOR_PANEL)
        f_unid.pack(side="right", fill="x")
        tk.Label(f_unid, text="UNIDAD *", font=("Segoe UI", 8, "bold"), bg=self.COLOR_PANEL, fg=self.COLOR_SECUNDARIO).pack(anchor="w")
        unidades = ["PZA", "KG", "LTS", "MTS", "TON", "CAJA"]
        self.combo_unidad = ttk.Combobox(f_unid, values=unidades, width=10, state="readonly")
        self.combo_unidad.set("KG")
        self.combo_unidad.pack(anchor="w")

        agregar_etiqueta("STOCK MÍNIMO (ALERTA)")
        self.entrada_stock_min = self.crear_entry(form_campos, width=28)
        self.entrada_stock_min.pack(anchor="w", pady=(0, 2))

        agregar_etiqueta("UBICACIÓN EN ALMACÉN")
        self.entrada_ubicacion = self.crear_entry(form_campos, width=28)
        self.entrada_ubicacion.pack(anchor="w", pady=(0, 2))

        agregar_etiqueta("OBSERVACIONES")
        self.entrada_observaciones = self.crear_entry(form_campos, width=28)
        self.entrada_observaciones.pack(anchor="w", pady=(0, 4))

        self.etiqueta_foto = tk.Label(form_campos, text="📷 Sin fotografías seleccionada", font=("Segoe UI", 8), bg=self.COLOR_PANEL, fg=self.COLOR_SECUNDARIO)
        self.etiqueta_foto.pack(anchor="w", pady=2)

        self.crear_boton(form_campos, "📷 Seleccionar Foto", self.seleccionar_foto, "#1E293B", hover_color="#334155", ancho=24).pack(pady=3)

    def crear_panel_derecho(self):
        panel_derecho = tk.Frame(self, bg="#030712")
        panel_derecho.grid(row=0, column=1, sticky="nsew")
        panel_derecho.grid_rowconfigure(1, weight=2)
        panel_derecho.grid_rowconfigure(2, weight=1)
        panel_derecho.grid_columnconfigure(0, weight=1)

        frame_busqueda = self.crear_card(panel_derecho)
        frame_busqueda.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        search_inner = tk.Frame(frame_busqueda, bg=self.COLOR_PANEL)
        search_inner.pack(padx=10, pady=8, fill="x")

        tk.Label(search_inner, text="🔍", font=("Segoe UI", 11), bg=self.COLOR_PANEL, fg=self.COLOR_PRIMARIO).pack(side="left", padx=(0, 6))
        self.entrada_buscar = self.crear_entry(search_inner, width=40)
        self.entrada_buscar.pack(side="left", padx=5)
        self.entrada_buscar.bind("<KeyRelease>", lambda e: self.cargar_materiales(self.entrada_buscar.get().strip()))

        self.crear_boton(search_inner, "🔄 Limpiar Buscador", lambda: (self.entrada_buscar.delete(0, tk.END), self.cargar_materiales()), "#1E293B", hover_color="#334155").pack(side="right")

        frame_tabla = self.crear_card(panel_derecho)
        frame_tabla.grid(row=1, column=0, sticky="nsew", pady=(0, 8))

        columnas_tabla = ("Código", "Descripción", "Categoría", "Stock", "Unidad", "Mínimo", "Ubicación")
        self.tabla = ttk.Treeview(frame_tabla, columns=columnas_tabla, show="headings", height=10)

        for col in columnas_tabla:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=95, anchor="center")
        self.tabla.column("Descripción", width=220, anchor="w")
        self.tabla.column("Categoría", width=140, anchor="w")

        scrollbar_tabla = ttk.Scrollbar(frame_tabla, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scrollbar_tabla.set)
        self.tabla.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar_tabla.pack(side="right", fill="y")
        self.tabla.tag_configure("hover", background="#102747")
        self._fila_hover = None
        self.tabla.bind("<Motion>", self._resaltar_fila_hover)
        self.tabla.bind("<Leave>", self._limpiar_fila_hover)
        self.tabla.bind("<<TreeviewSelect>>", self.seleccionar_elemento_tabla)

        panel_inferior = self.crear_card(panel_derecho)
        panel_inferior.grid(row=2, column=0, sticky="nsew")

        frame_detalles = tk.Frame(panel_inferior, bg=self.COLOR_PANEL)
        frame_detalles.pack(side="left", fill="y", padx=12, pady=12)

        self.contenedor_foto = tk.Frame(frame_detalles, width=180, height=150, bg="#030712", highlightbackground=self.COLOR_BORDE, highlightthickness=1)
        self.contenedor_foto.pack(side="left", padx=(0, 12))
        self.contenedor_foto.pack_propagate(False)

        self.detalle_foto = tk.Label(self.contenedor_foto, text="📷\n\nSIN FOTOGRAFÍA", font=("Segoe UI", 8), bg="#030712", fg=self.COLOR_SECUNDARIO)
        self.detalle_foto.pack(fill="both", expand=True)
        self.detalle_foto.configure(cursor="hand2")
        self.detalle_foto.bind("<Button-1>", self.mostrar_detalle_ampliado)
        self.contenedor_foto.bind("<Button-1>", self.mostrar_detalle_ampliado)

        info_detalles = tk.Frame(frame_detalles, bg=self.COLOR_PANEL)
        info_detalles.pack(side="left", fill="y")

        self.detalle_codigo = tk.Label(info_detalles, text="CÓDIGO: -", font=("Segoe UI", 9, "bold"), bg=self.COLOR_PANEL, fg=self.COLOR_PRIMARIO)
        self.detalle_codigo.pack(anchor="w")

        self.detalle_descripcion = tk.Label(info_detalles, text="Seleccione un material", font=("Segoe UI", 11, "bold"), bg=self.COLOR_PANEL, fg=self.COLOR_TEXTO, wraplength=260, justify="left")
        self.detalle_descripcion.pack(anchor="w", pady=2)

        self.detalle_categoria = tk.Label(info_detalles, text="🏷️ Categoría: -", font=("Segoe UI", 8), bg=self.COLOR_PANEL, fg=self.COLOR_SECUNDARIO)
        self.detalle_categoria.pack(anchor="w")

        self.detalle_cantidad = tk.Label(info_detalles, text="📦 Stock Actual: 0.0", font=("Segoe UI", 9, "bold"), bg=self.COLOR_PANEL, fg=self.COLOR_TEXTO)
        self.detalle_cantidad.pack(anchor="w", pady=1)

        self.detalle_ubicacion = tk.Label(info_detalles, text="📍 Ubicación: Sin ubicación", font=("Segoe UI", 8), bg=self.COLOR_PANEL, fg=self.COLOR_SECUNDARIO)
        self.detalle_ubicacion.pack(anchor="w")

        self.detalle_estado = tk.Label(info_detalles, text="● SELECCIONAR", font=("Segoe UI", 8, "bold"), bg=self.COLOR_PANEL, fg=self.COLOR_SECUNDARIO)
        self.detalle_estado.pack(anchor="w", pady=(4, 0))

        frame_botones_accion = tk.Frame(panel_inferior, bg=self.COLOR_PANEL)
        frame_botones_accion.pack(side="right", fill="y", padx=15, pady=12)

        self.crear_boton(frame_botones_accion, "🚚 Registrar Despacho / Salida", self.registrar_despacho, "#F43F5E", hover_color="#E11D48", ancho=25).pack(pady=3)
        self.crear_boton(frame_botones_accion, "📥 Reabastecer / Entrada", self.reabastecer_material, "#10B981", hover_color="#059669", ancho=25).pack(pady=3)
        fila_acciones_final = tk.Frame(frame_botones_accion, bg=self.COLOR_PANEL)
        fila_acciones_final.pack(fill="x", pady=3)
        self.crear_boton(
            fila_acciones_final, "⚡ Ver Kardex / Movimientos",
            self.ver_historial, "#3B82F6", hover_color="#2563EB", ancho=20
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.crear_boton(
            fila_acciones_final, "🗑 Eliminar",
            self.eliminar_material, "#7F1D2D", hover_color="#BE123C", ancho=11
        ).pack(side="left", padx=(2, 0), ipady=2)

    def _resaltar_fila_hover(self, event):
        try:
            fila = self.tabla.identify_row(event.y)
            if fila == self._fila_hover:
                return
            if self._fila_hover and self.tabla.exists(self._fila_hover):
                tags = tuple(t for t in self.tabla.item(self._fila_hover, "tags") if t != "hover")
                self.tabla.item(self._fila_hover, tags=tags)
            self._fila_hover = fila or None
            if fila:
                tags = tuple(t for t in self.tabla.item(fila, "tags") if t != "hover") + ("hover",)
                self.tabla.item(fila, tags=tags)
        except tk.TclError:
            pass

    def _limpiar_fila_hover(self, _event=None):
        try:
            if self._fila_hover and self.tabla.exists(self._fila_hover):
                tags = tuple(t for t in self.tabla.item(self._fila_hover, "tags") if t != "hover")
                self.tabla.item(self._fila_hover, tags=tags)
            self._fila_hover = None
        except tk.TclError:
            pass

    def seleccionar_foto(self):
        archivo = filedialog.askopenfilename(title="Seleccionar foto", filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.webp *.bmp"), ("Todos", "*.*")])
        if archivo:
            self.foto_seleccionada = archivo
            self.etiqueta_foto.config(text=f"✓ {os.path.basename(archivo)[:22]}", fg="#10B981")

    def guardar_foto(self, codigo):
        if not self.foto_seleccionada: return None
        ext = os.path.splitext(self.foto_seleccionada)[1].lower()
        nombre = f"{codigo}_{int(datetime.now().timestamp())}{ext}"
        destino = os.path.abspath(os.path.join(self.CARPETA_FOTOS, nombre))
        try:
            shutil.copy2(self.foto_seleccionada, destino)
            return destino
        except Exception: return None

    def agregar_material(self):
        codigo = self.entrada_codigo.get().strip()
        descripcion = self.entrada_descripcion.get().strip()
        categoria = self.combo_categoria.get().strip()
        especificacion = self.entrada_especificacion.get().strip()
        materia_prima = self.entrada_materia_prima.get().strip()
        cantidad = self.entrada_cantidad.get().strip()
        unidad = self.combo_unidad.get().strip()
        stock_min = self.entrada_stock_min.get().strip()
        ubicacion = self.entrada_ubicacion.get().strip()
        observaciones = self.entrada_observaciones.get().strip()

        if not codigo or not descripcion or not unidad:
            messagebox.showwarning("Campos Requeridos", "Código, descripción y unidad son obligatorios.")
            return
        try:
            cant_num = float(cantidad) if cantidad else 0.0
            stock_min_num = float(stock_min) if stock_min else 0.0
        except ValueError:
            messagebox.showerror("Valor Inválido", "Cantidad y stock mínimo deben ser numéricos.")
            return

        conexion = self.conectar()
        cursor = conexion.cursor()
        try:
            foto_ruta = self.guardar_foto(codigo)
            cursor.execute("""
                INSERT INTO materiales (codigo, descripcion, categoria, especificacion, materia_prima, cantidad, unidad, stock_minimo, ubicacion, observaciones, foto)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (codigo, descripcion, categoria, especificacion, materia_prima, cant_num, unidad, stock_min_num, ubicacion, observaciones, foto_ruta))

            material_id = cursor.lastrowid
            if cant_num > 0:
                fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO movimientos (material_id, codigo, tipo, cantidad, unidad, fecha, solicitante, area_proyecto, observaciones)
                    VALUES (?, ?, 'INGRESO', ?, ?, ?, 'Sistema', 'Alta de Material', 'Registro inicial')
                """, (material_id, codigo, cant_num, unidad, fecha))

            conexion.commit()
            messagebox.showinfo("Éxito", "El material fue registrado correctamente.")
            self.limpiar_formulario()
            self.cargar_materiales()
            self.master.master.master.actualizar_kpis()
        except sqlite3.IntegrityError:
            messagebox.showerror("Código Duplicado", "Ya existe un material con este código.")
        except Exception as error:
            messagebox.showerror("Error", str(error))
        finally:
            conexion.close()

    def obtener_material_seleccionado(self):
        try:
            seleccion = self.tabla.selection()
            if not seleccion: return None
            codigo_sel = self.tabla.item(seleccion[0], "values")[0]
            conexion = self.conectar()
            cursor = conexion.cursor()
            cursor.execute("SELECT id, codigo, descripcion, categoria, especificacion, materia_prima, cantidad, unidad, stock_minimo, ubicacion, observaciones, foto FROM materiales WHERE codigo = ?", (codigo_sel,))
            mat = cursor.fetchone()
            conexion.close()
            return mat
        except Exception: return None

    def cargar_materiales(self, filtro=""):
        for row in self.tabla.get_children(): self.tabla.delete(row)
        conexion = self.conectar()
        cursor = conexion.cursor()
        if filtro:
            cursor.execute("SELECT codigo, descripcion, categoria, cantidad, unidad, stock_minimo, ubicacion FROM materiales WHERE codigo LIKE ? OR descripcion LIKE ? OR categoria LIKE ?", (f"%{filtro}%", f"%{filtro}%", f"%{filtro}%"))
        else:
            cursor.execute("SELECT codigo, descripcion, categoria, cantidad, unidad, stock_minimo, ubicacion FROM materiales")
        for fila in cursor.fetchall(): self.tabla.insert("", "end", values=fila)
        conexion.close()

    def mostrar_detalle_ampliado(self, event=None):
        """Abre una ficha amplia con fotografía y todos los datos del registro."""
        material = self.obtener_material_seleccionado()
        if not material:
            return

        es_caja = hasattr(self, "CARD")
        bg = "#050D1A"
        card_bg = "#09182B"
        accent = "#38BDF8" if not es_caja else "#818CF8"
        top = tk.Toplevel(self)
        top.title(f"Ficha de {'caja' if es_caja else 'material'} · {material[1]}")
        top.configure(bg=bg)
        top.resizable(True, True)
        top.transient(self.winfo_toplevel())

        # La ficha aparece casi a tamaño completo: sin crecer lentamente.
        # Solo tiene un desplazamiento vertical mínimo y un fundido muy breve.
        sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
        final_w, final_h = min(1160, sw - 80), min(760, sh - 100)
        final_x, final_y = (sw - final_w) // 2, (sh - final_h) // 2
        top.geometry(f"{final_w}x{final_h}+{final_x}+{final_y + 7}")
        top.minsize(850, 560)
        try:
            top.attributes("-alpha", 0.96)
        except tk.TclError:
            pass

        header = tk.Frame(top, bg=bg, padx=24, pady=18)
        header.pack(fill="x")
        tk.Label(header, text=("RASTREO DE CAJA" if es_caja else "DETALLE DE MATERIAL"),
                 bg=bg, fg=accent, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(header, text=str(material[2] or "Registro sin descripción"),
                 bg=bg, fg="#F0F6FF", font=("Segoe UI", 19, "bold"),
                 wraplength=final_w - 70, justify="left").pack(anchor="w", pady=(5, 0))
        tk.Frame(top, bg="#15385B", height=1).pack(fill="x", padx=24)

        body = tk.Frame(top, bg=bg, padx=24, pady=20)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=5)
        body.grid_columnconfigure(1, weight=6)
        body.grid_rowconfigure(0, weight=1)

        photo_card = tk.Frame(body, bg=card_bg, highlightbackground="#16385E", highlightthickness=1)
        photo_card.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        photo_card.grid_rowconfigure(0, weight=1)
        photo_card.grid_columnconfigure(0, weight=1)
        photo_label = tk.Label(photo_card, text="📷\n\nSIN FOTOGRAFÍA", bg=card_bg, fg="#7895B8",
                               font=("Segoe UI", 12, "bold"))
        photo_label.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        ruta = material[11] if len(material) > 11 else None
        if ruta and os.path.exists(ruta):
            try:
                with Image.open(ruta) as original:
                    img = ImageOps.contain(original.copy(), (final_w // 2 - 70, final_h - 190), Image.Resampling.LANCZOS)
                top._foto_ampliada = ImageTk.PhotoImage(img)
                photo_label.configure(image=top._foto_ampliada, text="")
            except Exception:
                photo_label.configure(text="📷\n\nNO SE PUDO CARGAR LA FOTO")

        details_card = tk.Frame(body, bg=card_bg, highlightbackground="#16385E", highlightthickness=1)
        details_card.grid(row=0, column=1, sticky="nsew")
        tk.Label(details_card, text="INFORMACIÓN DEL REGISTRO", bg=card_bg, fg=accent,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=18, pady=(16, 10))
        fields = [
            ("ID", material[0]), ("Package / Código", material[1]), ("Descripción / Proyecto", material[2]),
            ("Categoría", material[3]), ("Especificación", material[4]), ("Materia prima", material[5]),
            ("Stock / Cantidad", material[6]), ("Unidad", material[7]), ("Stock mínimo", material[8]),
            ("Ubicación", material[9]), ("Observaciones", material[10]),
            ("Fotografía", os.path.basename(ruta) if ruta else "Sin fotografía"),
        ]
        for i, (label, value) in enumerate(fields):
            row = tk.Frame(details_card, bg=card_bg)
            row.pack(fill="x", padx=18, pady=4)
            tk.Label(row, text=label.upper(), bg=card_bg, fg="#7293B9", width=20,
                     anchor="w", font=("Segoe UI", 8, "bold")).pack(side="left", anchor="nw")
            tk.Label(row, text=(str(value) if value not in (None, "") else "—"), bg=card_bg,
                     fg="#E6F0FF", anchor="w", justify="left", wraplength=final_w // 2 - 100,
                     font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True)
            if i < len(fields) - 1:
                tk.Frame(details_card, bg="#102A46", height=1).pack(fill="x", padx=18, pady=(2, 0))

        footer = tk.Frame(top, bg=bg, padx=24, pady=14)
        footer.pack(fill="x")
        tk.Button(footer, text="Cerrar ficha", command=top.destroy, bg="#102746", fg="#E6F0FF",
                  activebackground="#1A3C62", activeforeground="white", relief="flat", bd=0,
                  padx=22, pady=9, cursor="hand2", font=("Segoe UI", 9, "bold")).pack(side="right")

        def entrada_sutil(paso=0):
            if not top.winfo_exists():
                return
            pasos = 5
            progreso = min(1.0, paso / pasos)
            # Ease-out rápido: movimiento de 7 px y fundido de solo 120 ms.
            suavizado = 1 - (1 - progreso) ** 3
            y = int(final_y + 7 * (1 - suavizado))
            top.geometry(f"{final_w}x{final_h}+{final_x}+{y}")
            try:
                top.attributes("-alpha", min(1.0, 0.96 + 0.04 * progreso))
            except tk.TclError:
                pass
            if paso < pasos:
                top.after(24, lambda: entrada_sutil(paso + 1))
        entrada_sutil()

    def seleccionar_elemento_tabla(self, event):
        material = self.obtener_material_seleccionado()
        if not material: return
        codigo, descripcion, categoria, cantidad, unidad, stock_min, ubicacion, foto_ruta = material[1], material[2], material[3] or "S/C", material[6], material[7], material[8], material[9] or "Sin ubicación", material[11]

        self.detalle_codigo.config(text=f"CÓDIGO: {codigo}")
        self.detalle_descripcion.config(text=descripcion)
        self.detalle_categoria.config(text=f"🏷️ Categoría: {categoria}")
        self.detalle_cantidad.config(text=f"📦 Stock Actual: {cantidad} {unidad}")
        self.detalle_ubicacion.config(text=f"📍 Ubicación: {ubicacion}")

        if cantidad <= 0:
            self.detalle_estado.config(text="● AGOTADO / REABASTECER", fg="#EF4444")
        elif cantidad <= stock_min:
            self.detalle_estado.config(text="● STOCK CRÍTICO", fg="#F59E0B")
        else:
            self.detalle_estado.config(text="● STOCK DISPONIBLE", fg="#10B981")

        if foto_ruta and os.path.exists(foto_ruta):
            try:
                img = Image.open(foto_ruta)
                img = ImageOps.contain(img, (170, 140), Image.Resampling.LANCZOS)
                self.imagen_detalle = ImageTk.PhotoImage(img)
                self.detalle_foto.config(image=self.imagen_detalle, text="")
            except Exception:
                self.detalle_foto.config(image="", text="📷\n\nERROR IMAGEN")
        else:
            self.detalle_foto.config(image="", text="📷\n\nSIN FOTOGRAFÍA")

    def registrar_despacho(self):
        material = self.obtener_material_seleccionado()
        if not material:
            messagebox.showwarning("Atención", "Seleccione un material de la lista.")
            return
        material_id, codigo, descripcion, _, _, _, stock_actual, unidad, stock_min, _, _, _ = material

        top = tk.Toplevel(self)
        top.title(f"Despachar Material - {codigo}")
        top.geometry("400x420")
        top.config(bg="#0B0F19")
        top.grab_set()

        tk.Label(top, text="REGISTRAR SALIDA / DESPACHO", font=("Segoe UI", 11, "bold"), bg="#0B0F19", fg=self.COLOR_TEXTO).pack(pady=15)
        form_frame = tk.Frame(top, bg="#0B0F19")
        form_frame.pack(padx=25, fill="x")

        tk.Label(form_frame, text=f"Material: {descripcion}", font=("Segoe UI", 9, "bold"), bg="#0B0F19", fg=self.COLOR_PRIMARIO, wraplength=340, justify="left").pack(anchor="w")
        tk.Label(form_frame, text=f"Stock Actual: {stock_actual} {unidad}", font=("Segoe UI", 9, "bold"), bg="#0B0F19", fg="#10B981" if stock_actual > stock_min else "#F59E0B").pack(anchor="w", pady=4)

        tk.Label(form_frame, text=f"Cantidad a Despachar ({unidad}):", font=("Segoe UI", 8, "bold"), bg="#0B0F19", fg=self.COLOR_SECUNDARIO).pack(anchor="w", pady=(10,0))
        entry_cant = self.crear_entry(form_frame, width=30)
        entry_cant.pack(anchor="w", pady=4)

        tk.Label(form_frame, text="Solicitante / Operario:", font=("Segoe UI", 8, "bold"), bg="#0B0F19", fg=self.COLOR_SECUNDARIO).pack(anchor="w", pady=(8,0))
        entry_solicitante = self.crear_entry(form_frame, width=30)
        entry_solicitante.pack(anchor="w", pady=4)

        tk.Label(form_frame, text="Área / Proyecto:", font=("Segoe UI", 8, "bold"), bg="#0B0F19", fg=self.COLOR_SECUNDARIO).pack(anchor="w", pady=(8,0))
        entry_area = self.crear_entry(form_frame, width=30)
        entry_area.pack(anchor="w", pady=4)

        def confirmar_salida():
            try:
                cantidad = float(entry_cant.get().strip())
                if cantidad <= 0 or cantidad > stock_actual:
                    messagebox.showerror("Error", "Cantidad inválida o superior al stock.", parent=top)
                    return
                solicitante = entry_solicitante.get().strip() or "No especificado"
                area = entry_area.get().strip() or "General"
                fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                conexion = self.conectar()
                cursor = conexion.cursor()
                cursor.execute("UPDATE materiales SET cantidad = ? WHERE id = ?", (stock_actual - cantidad, material_id))
                cursor.execute("INSERT INTO movimientos (material_id, codigo, tipo, cantidad, unidad, fecha, solicitante, area_proyecto, observaciones) VALUES (?, ?, 'SALIDA', ?, ?, ?, ?, ?, 'Despacho')", (material_id, codigo, cantidad, unidad, fecha, solicitante, area))
                conexion.commit()
                conexion.close()

                messagebox.showinfo("Éxito", "Despacho registrado correctamente.", parent=top)
                top.destroy()
                self.cargar_materiales()
                self.seleccionar_elemento_tabla(None)
                self.master.master.master.actualizar_kpis()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=top)

        self.crear_boton(top, "Confirmar Despacho", confirmar_salida, "#F43F5E", ancho=22).pack(pady=20)

    def reabastecer_material(self):
        material = self.obtener_material_seleccionado()
        if not material:
            messagebox.showwarning("Atención", "Seleccione un material de la lista.")
            return
        material_id, codigo, descripcion, _, _, _, stock_actual, unidad, _, _, _, _ = material

        top = tk.Toplevel(self)
        top.title(f"Reabastecer Material - {codigo}")
        top.geometry("400x360")
        top.config(bg="#0B0F19")
        top.grab_set()

        tk.Label(top, text="REGISTRAR ENTRADA", font=("Segoe UI", 10, "bold"), bg="#0B0F19", fg=self.COLOR_TEXTO).pack(pady=15)
        form_frame = tk.Frame(top, bg="#0B0F19")
        form_frame.pack(padx=25, fill="x")

        tk.Label(form_frame, text=f"Material: {descripcion}", font=("Segoe UI", 9, "bold"), bg="#0B0F19", fg=self.COLOR_PRIMARIO, wraplength=340, justify="left").pack(anchor="w")
        tk.Label(form_frame, text=f"Stock Actual: {stock_actual} {unidad}", font=("Segoe UI", 9), bg="#0B0F19", fg=self.COLOR_SECUNDARIO).pack(anchor="w", pady=4)

        tk.Label(form_frame, text=f"Cantidad a Ingresar ({unidad}):", font=("Segoe UI", 8, "bold"), bg="#0B0F19", fg=self.COLOR_SECUNDARIO).pack(anchor="w", pady=(10,0))
        entry_cant = self.crear_entry(form_frame, width=30)
        entry_cant.pack(anchor="w", pady=4)

        tk.Label(form_frame, text="Proveedor / Remisión:", font=("Segoe UI", 8, "bold"), bg="#0B0F19", fg=self.COLOR_SECUNDARIO).pack(anchor="w", pady=(8,0))
        entry_origen = self.crear_entry(form_frame, width=30)
        entry_origen.pack(anchor="w", pady=4)

        def confirmar_ingreso():
            try:
                cantidad = float(entry_cant.get().strip())
                if cantidad <= 0:
                    messagebox.showerror("Error", "Cantidad errónea.", parent=top)
                    return
                origen = entry_origen.get().strip() or "Reabastecimiento General"
                fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                conexion = self.conectar()
                cursor = conexion.cursor()
                cursor.execute("UPDATE materiales SET cantidad = ? WHERE id = ?", (stock_actual + cantidad, material_id))
                cursor.execute("INSERT INTO movimientos (material_id, codigo, tipo, cantidad, unidad, fecha, solicitante, area_proyecto, observaciones) VALUES (?, ?, 'INGRESO', ?, ?, ?, 'Almacén', ?, 'Entrada')", (material_id, codigo, cantidad, unidad, fecha, origen))
                conexion.commit()
                conexion.close()

                messagebox.showinfo("Éxito", "Entrada registrada correctamente.", parent=top)
                top.destroy()
                self.cargar_materiales()
                self.seleccionar_elemento_tabla(None)
                self.master.master.master.actualizar_kpis()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=top)

        self.crear_boton(top, "Guardar Entrada", confirmar_ingreso, "#10B981", ancho=22).pack(pady=20)

    def eliminar_material(self):
        material = self.obtener_material_seleccionado()
        if not material:
            messagebox.showwarning("Selección requerida", "Seleccione un material de la tabla.")
            return
        material_id, codigo, descripcion, _, _, _, _, _, _, _, _, ruta_foto = material

        if messagebox.askyesno("Confirmar", f"¿Eliminar permanentemente {codigo} - {descripcion}?"):
            conexion = self.conectar()
            cursor = conexion.cursor()
            try:
                cursor.execute("DELETE FROM movimientos WHERE material_id = ?", (material_id,))
                cursor.execute("DELETE FROM materiales WHERE id = ?", (material_id,))
                conexion.commit()
                if ruta_foto and os.path.exists(ruta_foto):
                    try: os.remove(ruta_foto)
                    except Exception: pass
                messagebox.showinfo("Éxito", "Registro eliminado.")
                self.limpiar_formulario()
                self.cargar_materiales()
                self.master.master.master.actualizar_kpis()
            except Exception as error:
                conexion.rollback()
                messagebox.showerror("Error", str(error))
            finally:
                conexion.close()

    def ver_historial(self):
        material = self.obtener_material_seleccionado()
        if not material:
            messagebox.showwarning("Selección requerida", "Seleccione un material de la tabla.")
            return
        material_id, codigo, descripcion = material[0], material[1], material[2]

        top = tk.Toplevel(self)
        top.title(f"Kardex / Historial - {codigo}")
        top.geometry("750x400")
        top.config(bg="#0B0F19")
        top.grab_set()

        tk.Label(top, text=f"HISTORIAL: {codigo} - {descripcion}", font=("Segoe UI", 10, "bold"), bg="#0B0F19", fg=self.COLOR_TEXTO).pack(pady=15)
        frame_tabla = tk.Frame(top, bg=self.COLOR_PANEL)
        frame_tabla.pack(fill="both", expand=True, padx=20, pady=10)

        columnas = ("Tipo", "Cantidad", "Unidad", "Fecha", "Responsable", "Área / Destino")
        tree_hist = ttk.Treeview(frame_tabla, columns=columnas, show="headings", height=10)
        for col in columnas:
            tree_hist.heading(col, text=col)
            tree_hist.column(col, width=110, anchor="center")

        scrollbar = ttk.Scrollbar(frame_tabla, orient="vertical", command=tree_hist.yview)
        tree_hist.configure(yscrollcommand=scrollbar.set)
        tree_hist.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        conexion = self.conectar()
        cursor = conexion.cursor()
        cursor.execute("SELECT tipo, cantidad, unidad, fecha, solicitante, area_proyecto FROM movimientos WHERE material_id = ? ORDER BY id DESC", (material_id,))
        for mov in cursor.fetchall(): tree_hist.insert("", "end", values=mov)
        conexion.close()

    def limpiar_formulario(self):
        self.foto_seleccionada = None
        self.entrada_codigo.delete(0, tk.END)
        self.entrada_descripcion.delete(0, tk.END)
        self.combo_categoria.set('')
        self.entrada_especificacion.delete(0, tk.END)
        self.entrada_materia_prima.delete(0, tk.END)
        self.entrada_cantidad.delete(0, tk.END)
        self.combo_unidad.set('KG')
        self.entrada_stock_min.delete(0, tk.END)
        self.entrada_ubicacion.delete(0, tk.END)
        self.entrada_observaciones.delete(0, tk.END)
        self.etiqueta_foto.config(text="📷 Sin fotografías seleccionada", fg=self.COLOR_SECUNDARIO)


class ModuloCajasNeon(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        self.DB = ruta_base_datos("rastreo_cajas_almacen.db")
        self.CARPETA_FOTOS = "fotos_cajas"
        os.makedirs(self.CARPETA_FOTOS, exist_ok=True)

        self.BG = "#07111F"
        self.CARD = "#07111F"
        self.INPUT = "#061121"
        self.BLUE = "#2563EB"
        self.TEXT = "#EAF3FF"
        self.MUTED = "#91ACCD"
        self.BORDER = "#12345A"

        self.foto_seleccionada = None
        self.imagen_detalle = None

        self.crear_base_datos()

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        self.crear_formulario()
        self.crear_panel_derecho()

        self.cargar_materiales()

    def conectar(self):
        conexion = sqlite3.connect(self.DB)
        conexion.execute("PRAGMA foreign_keys = ON")
        return conexion

    def crear_base_datos(self):
        conexion = self.conectar()
        cursor = conexion.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS materiales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                descripcion TEXT NOT NULL,
                categoria TEXT,
                especificacion TEXT,
                materia_prima TEXT,
                cantidad REAL DEFAULT 0,
                unidad TEXT DEFAULT 'CAJA',
                stock_minimo REAL DEFAULT 0,
                ubicacion TEXT,
                observaciones TEXT,
                foto TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_id INTEGER NOT NULL,
                codigo TEXT NOT NULL,
                tipo TEXT NOT NULL,
                cantidad REAL NOT NULL,
                unidad TEXT NOT NULL,
                fecha TEXT NOT NULL,
                solicitante TEXT,
                area_proyecto TEXT,
                observaciones TEXT,
                FOREIGN KEY(material_id) REFERENCES materiales(id) ON DELETE CASCADE
            )
        """)
        conexion.commit()
        conexion.close()

    def crear_card(self, parent, **kwargs):
        return tk.Frame(parent, bg=self.CARD, highlightbackground=self.BORDER, highlightthickness=1, bd=0, **kwargs)

    def boton(self, parent, texto, comando, color=None, width=None):
        if color is None: color = self.BLUE
        b = tk.Button(parent, text=texto, command=comando, bg=color, fg="white", font=("Segoe UI", 9, "bold"), relief="flat", bd=0, cursor="hand2", padx=14, pady=8)
        if width: b.config(width=width)
        return b

    def entry_moderno(self, parent, width=25):
        """Entrada de caja con esquinas suaves y brillo al enfocarse."""
        entry = ctk.CTkEntry(
            parent,
            width=max(110, int(width * 9.2)),
            height=31,
            corner_radius=9,
            border_width=1,
            fg_color="#061121",
            text_color="#E5F0FF",
            placeholder_text_color="#6382A8",
            border_color="#16385E",
            font=("Segoe UI", 10)
        )
        entry.bind("<FocusIn>", lambda _e: entry.configure(border_color="#168BFF"))
        entry.bind("<FocusOut>", lambda _e: entry.configure(border_color="#16385E"))
        return entry

    def crear_formulario(self):
        panel_form = self.crear_card(self)
        panel_form.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)

        tk.Label(panel_form, text="＋  NUEVA CAJA", bg="#111827", fg=self.TEXT, font=("Segoe UI", 11, "bold"), pady=11).pack(fill="x")

        form_campos = tk.Frame(panel_form, bg=self.CARD)
        form_campos.pack(fill="both", expand=True, padx=15, pady=10)

        def agregar_etiqueta(texto):
            tk.Label(form_campos, text=texto, bg=self.CARD, fg=self.MUTED, font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(5, 2))

        agregar_etiqueta("PACKAGE *")
        self.entrada_codigo = self.entry_moderno(form_campos, 28)
        self.entrada_codigo.pack(fill="x")

        agregar_etiqueta("PROYECTO *")
        self.entrada_descripcion = self.entry_moderno(form_campos, 28)
        self.entrada_descripcion.pack(fill="x")

        agregar_etiqueta("UBICACIÓN")
        self.entrada_ubicacion = self.entry_moderno(form_campos, 28)
        self.entrada_ubicacion.pack(fill="x")

        self.etiqueta_foto = tk.Label(form_campos, text="📷 Sin fotografía seleccionada", bg=self.CARD, fg=self.MUTED, font=("Segoe UI", 8), anchor="w")
        self.etiqueta_foto.pack(fill="x", pady=(10, 5))

        self.boton(form_campos, "📷 Seleccionar Foto", self.seleccionar_foto, "#1E293B").pack(fill="x", pady=3)
        self.boton(form_campos, "✓ Guardar Caja", self.agregar_material, "#059669").pack(fill="x", pady=(5, 3))

    def crear_panel_derecho(self):
        panel_derecho = tk.Frame(self, bg="#030712")
        panel_derecho.grid(row=0, column=1, sticky="nsew")
        panel_derecho.grid_rowconfigure(1, weight=2)
        panel_derecho.grid_rowconfigure(2, weight=1)
        panel_derecho.grid_columnconfigure(0, weight=1)

        busqueda = self.crear_card(panel_derecho)
        busqueda.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        search_inner = tk.Frame(busqueda, bg=self.CARD)
        search_inner.pack(fill="x", padx=12, pady=10)

        tk.Label(search_inner, text="🔍", bg=self.CARD, fg=self.BLUE, font=("Segoe UI", 11)).pack(side="left")
        self.entrada_buscar = self.entry_moderno(search_inner, 35)
        self.entrada_buscar.pack(side="left", padx=8)
        self.entrada_buscar.bind("<KeyRelease>", lambda e: self.cargar_materiales(self.entrada_buscar.get().strip()))

        self.boton(search_inner, "Limpiar Buscador", lambda: (self.entrada_buscar.delete(0, tk.END), self.cargar_materiales()), "#1E293B").pack(side="right")

        frame_tabla = self.crear_card(panel_derecho)
        frame_tabla.grid(row=1, column=0, sticky="nsew", pady=(0, 8))

        columnas_tabla = ("Package", "Proyecto", "Ubicación")
        self.tabla = ttk.Treeview(frame_tabla, columns=columnas_tabla, show="headings")
        for col in columnas_tabla:
            self.tabla.heading(col, text=col)
            self.tabla.column(col, width=150, anchor="w")

        scrollbar_tabla = ttk.Scrollbar(frame_tabla, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scrollbar_tabla.set)
        self.tabla.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar_tabla.pack(side="right", fill="y", pady=5)
        self.tabla.tag_configure("hover", background="#102747")
        self._fila_hover = None
        self.tabla.bind("<Motion>", self._resaltar_fila_hover)
        self.tabla.bind("<Leave>", self._limpiar_fila_hover)
        self.tabla.bind("<<TreeviewSelect>>", self.seleccionar_elemento_tabla)

        panel_inferior = self.crear_card(panel_derecho)
        panel_inferior.grid(row=2, column=0, sticky="nsew")

        contenedor_foto = tk.Frame(panel_inferior, width=180, height=140, bg=self.INPUT, highlightbackground=self.BORDER, highlightthickness=1)
        contenedor_foto.pack(side="left", padx=10, pady=10)
        contenedor_foto.pack_propagate(False)

        self.detalle_foto = tk.Label(contenedor_foto, text="📷\n\nSIN FOTOGRAFÍA", bg=self.INPUT, fg=self.MUTED, font=("Segoe UI", 8, "bold"))
        self.detalle_foto.pack(fill="both", expand=True)
        self.detalle_foto.configure(cursor="hand2")
        self.detalle_foto.bind("<Button-1>", self.mostrar_detalle_ampliado)
        contenedor_foto.bind("<Button-1>", self.mostrar_detalle_ampliado)

        info_detalles = tk.Frame(panel_inferior, bg=self.CARD)
        info_detalles.pack(side="left", fill="both", expand=True, pady=10)

        self.detalle_codigo = tk.Label(info_detalles, text="PACKAGE: -", bg=self.CARD, fg=self.BLUE, font=("Segoe UI", 9, "bold"))
        self.detalle_codigo.pack(anchor="w")

        self.detalle_descripcion = tk.Label(info_detalles, text="Seleccione una caja", bg=self.CARD, fg=self.TEXT, font=("Segoe UI", 12, "bold"), wraplength=260, justify="left")
        self.detalle_descripcion.pack(anchor="w", pady=(2, 5))

        self.detalle_cantidad = tk.Label(info_detalles, text="📦 Cantidad registrada: 0", bg=self.CARD, fg=self.TEXT, font=("Segoe UI", 9, "bold"))
        self.detalle_cantidad.pack(anchor="w", pady=2)

        self.detalle_ubicacion = tk.Label(info_detalles, text="📍 Ubicación: Sin ubicación", bg=self.CARD, fg=self.MUTED, font=("Segoe UI", 8))
        self.detalle_ubicacion.pack(anchor="w")

        self.detalle_estado = tk.Label(info_detalles, text="● SELECCIONAR", bg=self.CARD, fg=self.MUTED, font=("Segoe UI", 8, "bold"))
        self.detalle_estado.pack(anchor="w", pady=(6, 0))

        acciones = tk.Frame(panel_inferior, bg=self.CARD)
        acciones.pack(side="right", padx=12, pady=10)

        self.boton(acciones, "📤 Registrar Salida", self.registrar_despacho, "#DC2626").pack(fill="x", pady=2)
        self.boton(acciones, "📥 Reabastecer / Entrada", self.reabastecer_material, "#059669").pack(fill="x", pady=2)
        fila_acciones_final = tk.Frame(acciones, bg=self.CARD)
        fila_acciones_final.pack(fill="x", pady=2)
        self.boton(fila_acciones_final, "⚡ Ver Historial", self.ver_historial, "#2563EB").pack(
            side="left", fill="x", expand=True, padx=(0, 5)
        )
        self.boton(fila_acciones_final, "🗑 Eliminar", self.eliminar_material, "#7F1D2D").pack(
            side="left", padx=(2, 0), ipady=2
        )

    def _resaltar_fila_hover(self, event):
        try:
            fila = self.tabla.identify_row(event.y)
            if fila == self._fila_hover:
                return
            if self._fila_hover and self.tabla.exists(self._fila_hover):
                tags = tuple(t for t in self.tabla.item(self._fila_hover, "tags") if t != "hover")
                self.tabla.item(self._fila_hover, tags=tags)
            self._fila_hover = fila or None
            if fila:
                tags = tuple(t for t in self.tabla.item(fila, "tags") if t != "hover") + ("hover",)
                self.tabla.item(fila, tags=tags)
        except tk.TclError:
            pass

    def _limpiar_fila_hover(self, _event=None):
        try:
            if self._fila_hover and self.tabla.exists(self._fila_hover):
                tags = tuple(t for t in self.tabla.item(self._fila_hover, "tags") if t != "hover")
                self.tabla.item(self._fila_hover, tags=tags)
            self._fila_hover = None
        except tk.TclError:
            pass

    def seleccionar_foto(self):
        archivo = filedialog.askopenfilename(title="Seleccionar foto de caja", filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.webp *.bmp"), ("Todos", "*.*")])
        if archivo:
            self.foto_seleccionada = archivo
            self.etiqueta_foto.config(text=f"✓ {os.path.basename(archivo)[:22]}", fg="#10B981")

    def guardar_foto(self, codigo):
        if not self.foto_seleccionada: return None
        ext = os.path.splitext(self.foto_seleccionada)[1].lower()
        nombre = f"{codigo}_{int(datetime.now().timestamp())}{ext}"
        destino = os.path.abspath(os.path.join(self.CARPETA_FOTOS, nombre))
        try:
            shutil.copy2(self.foto_seleccionada, destino)
            return destino
        except Exception: return None

    def agregar_material(self):
        codigo = self.entrada_codigo.get().strip()
        descripcion = self.entrada_descripcion.get().strip()
        ubicacion = self.entrada_ubicacion.get().strip()

        if not codigo or not descripcion:
            messagebox.showwarning("Campos Requeridos", "Package y Proyecto son obligatorios.")
            return

        conexion = self.conectar()
        cursor = conexion.cursor()
        try:
            foto_ruta = self.guardar_foto(codigo)
            cursor.execute("INSERT INTO materiales (codigo, descripcion, cantidad, unidad, ubicacion, foto) VALUES (?, ?, 1, 'CAJA', ?, ?)", (codigo, descripcion, ubicacion, foto_ruta))
            material_id = cursor.lastrowid
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("INSERT INTO movimientos (material_id, codigo, tipo, cantidad, unidad, fecha, solicitante, area_proyecto, observaciones) VALUES (?, ?, 'INGRESO', 1, 'CAJA', ?, 'Sistema', 'Alta de caja', 'Registro inicial')", (material_id, codigo, fecha))
            conexion.commit()

            messagebox.showinfo("Caja registrada", "La caja fue registrada correctamente.")
            self.limpiar_formulario()
            self.cargar_materiales()
            self.master.master.master.actualizar_kpis()
        except sqlite3.IntegrityError:
            messagebox.showerror("Código duplicado", "Ya existe una caja con ese código.")
        except Exception as error:
            messagebox.showerror("Error", str(error))
        finally:
            conexion.close()

    def obtener_material_seleccionado(self):
        try:
            seleccion = self.tabla.selection()
            if not seleccion: return None
            codigo = self.tabla.item(seleccion[0], "values")[0]
            conexion = self.conectar()
            cursor = conexion.cursor()
            cursor.execute("SELECT id, codigo, descripcion, categoria, especificacion, materia_prima, cantidad, unidad, stock_minimo, ubicacion, observaciones, foto FROM materiales WHERE codigo = ?", (codigo,))
            mat = cursor.fetchone()
            conexion.close()
            return mat
        except Exception: return None

    def cargar_materiales(self, filtro=""):
        for row in self.tabla.get_children(): self.tabla.delete(row)
        conexion = self.conectar()
        cursor = conexion.cursor()
        if filtro:
            cursor.execute("SELECT codigo, descripcion, ubicacion FROM materiales WHERE codigo LIKE ? OR descripcion LIKE ? OR ubicacion LIKE ?", (f"%{filtro}%", f"%{filtro}%", f"%{filtro}%"))
        else:
            cursor.execute("SELECT codigo, descripcion, ubicacion FROM materiales ORDER BY id DESC")
        for fila in cursor.fetchall(): self.tabla.insert("", "end", values=fila)
        conexion.close()

    def mostrar_detalle_ampliado(self, event=None):
        """Abre una ficha amplia con fotografía y todos los datos del registro."""
        material = self.obtener_material_seleccionado()
        if not material:
            return

        es_caja = hasattr(self, "CARD")
        bg = "#050D1A"
        card_bg = "#09182B"
        accent = "#38BDF8" if not es_caja else "#818CF8"
        top = tk.Toplevel(self)
        top.title(f"Ficha de {'caja' if es_caja else 'material'} · {material[1]}")
        top.configure(bg=bg)
        top.resizable(True, True)
        top.transient(self.winfo_toplevel())

        # La ficha aparece casi a tamaño completo: sin crecer lentamente.
        # Solo tiene un desplazamiento vertical mínimo y un fundido muy breve.
        sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
        final_w, final_h = min(1160, sw - 80), min(760, sh - 100)
        final_x, final_y = (sw - final_w) // 2, (sh - final_h) // 2
        top.geometry(f"{final_w}x{final_h}+{final_x}+{final_y + 7}")
        top.minsize(850, 560)
        try:
            top.attributes("-alpha", 0.96)
        except tk.TclError:
            pass

        header = tk.Frame(top, bg=bg, padx=24, pady=18)
        header.pack(fill="x")
        tk.Label(header, text=("RASTREO DE CAJA" if es_caja else "DETALLE DE MATERIAL"),
                 bg=bg, fg=accent, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(header, text=str(material[2] or "Registro sin descripción"),
                 bg=bg, fg="#F0F6FF", font=("Segoe UI", 19, "bold"),
                 wraplength=final_w - 70, justify="left").pack(anchor="w", pady=(5, 0))
        tk.Frame(top, bg="#15385B", height=1).pack(fill="x", padx=24)

        body = tk.Frame(top, bg=bg, padx=24, pady=20)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=5)
        body.grid_columnconfigure(1, weight=6)
        body.grid_rowconfigure(0, weight=1)

        photo_card = tk.Frame(body, bg=card_bg, highlightbackground="#16385E", highlightthickness=1)
        photo_card.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        photo_card.grid_rowconfigure(0, weight=1)
        photo_card.grid_columnconfigure(0, weight=1)
        photo_label = tk.Label(photo_card, text="📷\n\nSIN FOTOGRAFÍA", bg=card_bg, fg="#7895B8",
                               font=("Segoe UI", 12, "bold"))
        photo_label.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        ruta = material[11] if len(material) > 11 else None
        if ruta and os.path.exists(ruta):
            try:
                with Image.open(ruta) as original:
                    img = ImageOps.contain(original.copy(), (final_w // 2 - 70, final_h - 190), Image.Resampling.LANCZOS)
                top._foto_ampliada = ImageTk.PhotoImage(img)
                photo_label.configure(image=top._foto_ampliada, text="")
            except Exception:
                photo_label.configure(text="📷\n\nNO SE PUDO CARGAR LA FOTO")

        details_card = tk.Frame(body, bg=card_bg, highlightbackground="#16385E", highlightthickness=1)
        details_card.grid(row=0, column=1, sticky="nsew")
        tk.Label(details_card, text="INFORMACIÓN DEL REGISTRO", bg=card_bg, fg=accent,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=18, pady=(16, 10))
        fields = [
            ("ID", material[0]), ("Package / Código", material[1]), ("Descripción / Proyecto", material[2]),
            ("Categoría", material[3]), ("Especificación", material[4]), ("Materia prima", material[5]),
            ("Stock / Cantidad", material[6]), ("Unidad", material[7]), ("Stock mínimo", material[8]),
            ("Ubicación", material[9]), ("Observaciones", material[10]),
            ("Fotografía", os.path.basename(ruta) if ruta else "Sin fotografía"),
        ]
        for i, (label, value) in enumerate(fields):
            row = tk.Frame(details_card, bg=card_bg)
            row.pack(fill="x", padx=18, pady=4)
            tk.Label(row, text=label.upper(), bg=card_bg, fg="#7293B9", width=20,
                     anchor="w", font=("Segoe UI", 8, "bold")).pack(side="left", anchor="nw")
            tk.Label(row, text=(str(value) if value not in (None, "") else "—"), bg=card_bg,
                     fg="#E6F0FF", anchor="w", justify="left", wraplength=final_w // 2 - 100,
                     font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True)
            if i < len(fields) - 1:
                tk.Frame(details_card, bg="#102A46", height=1).pack(fill="x", padx=18, pady=(2, 0))

        footer = tk.Frame(top, bg=bg, padx=24, pady=14)
        footer.pack(fill="x")
        tk.Button(footer, text="Cerrar ficha", command=top.destroy, bg="#102746", fg="#E6F0FF",
                  activebackground="#1A3C62", activeforeground="white", relief="flat", bd=0,
                  padx=22, pady=9, cursor="hand2", font=("Segoe UI", 9, "bold")).pack(side="right")

        def entrada_sutil(paso=0):
            if not top.winfo_exists():
                return
            pasos = 5
            progreso = min(1.0, paso / pasos)
            # Ease-out rápido: movimiento de 7 px y fundido de solo 120 ms.
            suavizado = 1 - (1 - progreso) ** 3
            y = int(final_y + 7 * (1 - suavizado))
            top.geometry(f"{final_w}x{final_h}+{final_x}+{y}")
            try:
                top.attributes("-alpha", min(1.0, 0.96 + 0.04 * progreso))
            except tk.TclError:
                pass
            if paso < pasos:
                top.after(24, lambda: entrada_sutil(paso + 1))
        entrada_sutil()

    def seleccionar_elemento_tabla(self, event):
        material = self.obtener_material_seleccionado()
        if not material: return
        codigo, descripcion, cantidad, unidad, ubicacion, foto = material[1], material[2], material[6], material[7], material[9] or "Sin ubicación", material[11]

        self.detalle_codigo.config(text=f"PACKAGE {codigo}")
        self.detalle_descripcion.config(text=descripcion)
        self.detalle_cantidad.config(text=f"📊 {cantidad:g} {unidad}")
        self.detalle_ubicacion.config(text=f"📍 {ubicacion}")

        if cantidad <= 0:
            self.detalle_estado.config(text="● AGOTADO / REABASTECER", fg="#DC2626")
        else:
            self.detalle_estado.config(text="● STOCK DISPONIBLE", fg="#059669")

        if foto and os.path.exists(foto):
            try:
                img = Image.open(foto)
                img = ImageOps.contain(img, (170, 130), Image.Resampling.LANCZOS)
                self.imagen_detalle = ImageTk.PhotoImage(img)
                self.detalle_foto.config(image=self.imagen_detalle, text="")
            except Exception:
                self.detalle_foto.config(image="", text="📷\n\nERROR FOTO")
        else:
            self.detalle_foto.config(image="", text="📷\n\nSIN FOTOGRAFÍA")

    def registrar_despacho(self):
        material = self.obtener_material_seleccionado()
        if not material:
            messagebox.showwarning("Atención", "Seleccione una caja de la tabla.")
            return
        material_id, codigo, descripcion, _, _, _, stock_actual, unidad, _, _, _, _ = material

        top = tk.Toplevel(self)
        top.title(f"Salida de caja - {codigo}")
        top.geometry("400x320")
        top.configure(bg="#0B0F19")
        top.grab_set()

        tk.Label(top, text="REGISTRAR SALIDA DE CAJA", bg="#DC2626", fg="white", font=("Segoe UI", 11, "bold"), pady=8).pack(fill="x")
        form = tk.Frame(top, bg="#0B0F19")
        form.pack(padx=20, pady=12, fill="both", expand=True)

        tk.Label(form, text=f"{codigo} - {descripcion}", bg="#0B0F19", fg=self.TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(form, text="SOLICITANTE / OPERARIO", bg="#0B0F19", fg=self.MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(8, 0))
        e_sol = self.entry_moderno(form, 30)
        e_sol.pack(fill="x", pady=2)

        tk.Label(form, text="DESTINO / ÁREA", bg="#0B0F19", fg=self.MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(5, 0))
        e_area = self.entry_moderno(form, 30)
        e_area.pack(fill="x", pady=2)

        def confirmar():
            sol = e_sol.get().strip() or "General"
            area = e_area.get().strip() or "General"
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            conexion = self.conectar()
            cursor = conexion.cursor()
            cursor.execute("UPDATE materiales SET cantidad = ?, ubicacion = ? WHERE id = ?", (max(0, stock_actual - 1), area, material_id))
            cursor.execute("INSERT INTO movimientos (material_id, codigo, tipo, cantidad, unidad, fecha, solicitante, area_proyecto, observaciones) VALUES (?, ?, 'SALIDA', 1, ?, ?, ?, ?, 'Despacho')", (material_id, codigo, unidad, fecha, sol, area))
            conexion.commit()
            conexion.close()

            messagebox.showinfo("Éxito", "Salida registrada.", parent=top)
            top.destroy()
            self.cargar_materiales()
            self.master.master.master.actualizar_kpis()

        self.boton(top, "Confirmar Despacho", confirmar, "#DC2626").pack(pady=12)

    def reabastecer_material(self):
        material = self.obtener_material_seleccionado()
        if not material:
            messagebox.showwarning("Atención", "Seleccione una caja de la tabla.")
            return
        material_id, codigo, descripcion, _, _, _, stock_actual, unidad, _, _, _, _ = material

        top = tk.Toplevel(self)
        top.title(f"Entrada de caja - {codigo}")
        top.geometry("400x280")
        top.configure(bg="#0B0F19")
        top.grab_set()

        tk.Label(top, text="REGISTRAR ENTRADA DE CAJA", bg="#059669", fg="white", font=("Segoe UI", 11, "bold"), pady=8).pack(fill="x")
        form = tk.Frame(top, bg="#0B0F19")
        form.pack(padx=20, pady=12, fill="both", expand=True)

        tk.Label(form, text=f"{codigo} - {descripcion}", bg="#0B0F19", fg=self.TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(form, text="UBICACIÓN / REMISIÓN", bg="#0B0F19", fg=self.MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(8, 0))
        e_orig = self.entry_moderno(form, 30)
        e_orig.pack(fill="x", pady=2)

        def confirmar():
            orig = e_orig.get().strip() or "Almacén"
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            conexion = self.conectar()
            cursor = conexion.cursor()
            cursor.execute("UPDATE materiales SET cantidad = ?, ubicacion = ? WHERE id = ?", (stock_actual + 1, orig, material_id))
            cursor.execute("INSERT INTO movimientos (material_id, codigo, tipo, cantidad, unidad, fecha, solicitante, area_proyecto, observaciones) VALUES (?, ?, 'INGRESO', 1, ?, ?, 'Almacén', ?, 'Entrada')", (material_id, codigo, unidad, fecha, orig))
            conexion.commit()
            conexion.close()

            messagebox.showinfo("Éxito", "Entrada registrada.", parent=top)
            top.destroy()
            self.cargar_materiales()
            self.master.master.master.actualizar_kpis()

        self.boton(top, "Guardar Entrada", confirmar, "#059669").pack(pady=12)

    def eliminar_material(self):
        material = self.obtener_material_seleccionado()
        if not material:
            messagebox.showwarning("Atención", "Seleccione una caja.")
            return
        material_id, codigo, descripcion, *_, ruta_foto = material

        if messagebox.askyesno("Confirmar", f"¿Eliminar caja {codigo}?"):
            conexion = self.conectar()
            cursor = conexion.cursor()
            try:
                cursor.execute("DELETE FROM movimientos WHERE material_id = ?", (material_id,))
                cursor.execute("DELETE FROM materiales WHERE id = ?", (material_id,))
                conexion.commit()
                if ruta_foto and os.path.exists(ruta_foto):
                    try: os.remove(ruta_foto)
                    except Exception: pass
                messagebox.showinfo("Éxito", "Caja eliminada.")
                self.limpiar_formulario()
                self.cargar_materiales()
                self.master.master.master.actualizar_kpis()
            except Exception as error:
                conexion.rollback()
                messagebox.showerror("Error", str(error))
            finally:
                conexion.close()

    def ver_historial(self):
        material = self.obtener_material_seleccionado()
        if not material:
            messagebox.showwarning("Atención", "Seleccione una caja.")
            return
        material_id, codigo, descripcion = material[0], material[1], material[2]

        top = tk.Toplevel(self)
        top.title(f"Historial - {codigo}")
        top.geometry("700x380")
        top.configure(bg="#0B0F19")
        top.grab_set()

        tk.Label(top, text=f"HISTORIAL: {codigo} - {descripcion}", bg="#0B0F19", fg=self.TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=15, pady=12)
        frame = self.crear_card(top)
        frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columnas = ("Tipo", "Cantidad", "Unidad", "Fecha", "Responsable", "Área / Destino")
        tree = ttk.Treeview(frame, columns=columnas, show="headings")
        for col in columnas:
            tree.heading(col, text=col)
            tree.column(col, width=100, anchor="center")

        tree.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        conexion = self.conectar()
        cursor = conexion.cursor()
        cursor.execute("SELECT tipo, cantidad, unidad, fecha, solicitante, area_proyecto FROM movimientos WHERE material_id = ? ORDER BY id DESC", (material_id,))
        for mov in cursor.fetchall(): tree.insert("", "end", values=mov)
        conexion.close()

    def limpiar_formulario(self):
        self.foto_seleccionada = None
        self.entrada_codigo.delete(0, tk.END)
        self.entrada_descripcion.delete(0, tk.END)
        self.entrada_ubicacion.delete(0, tk.END)
        self.etiqueta_foto.config(text="📷 Sin fotografía seleccionada", fg=self.MUTED)


if __name__ == "__main__":
    app = AppUnificadaNeon()
    app.mainloop()