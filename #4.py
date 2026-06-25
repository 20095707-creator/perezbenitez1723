"""
RAE - Registro de Asistencia Estudiantil
Sistema completo con Tkinter + SQLite + Reconocimiento Facial
VERSIÓN MEJORADA: manejo correcto de cámara, threading seguro, errores robustos
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
import pickle
import threading
import time

# ─────────────────────────────────────────
#  IMPORTACIONES OPCIONALES (con manejo de error)
# ─────────────────────────────────────────
try:
    import cv2
    CV2_DISPONIBLE = True
except ImportError:
    CV2_DISPONIBLE = False
    print("⚠ OpenCV no instalado. La cámara no estará disponible.")
    print("  Instala con: pip install opencv-python")

try:
    import face_recognition
    FACE_DISPONIBLE = True
except ImportError:
    FACE_DISPONIBLE = False
    print("⚠ face_recognition no instalado.")
    print("  1. pip install cmake")
    print("  2. pip install dlib")
    print("  3. pip install face_recognition")
    print("  4. pip install git+https://github.com/ageitgey/face_recognition_models")

try:
    import numpy as np
    NUMPY_DISPONIBLE = True
except ImportError:
    NUMPY_DISPONIBLE = False

try:
    from PIL import Image, ImageTk
    PIL_DISPONIBLE = True
except ImportError:
    PIL_DISPONIBLE = False
    print("⚠ Pillow no instalado. Instala con: pip install Pillow")

CAMARA_DISPONIBLE = CV2_DISPONIBLE and FACE_DISPONIBLE and PIL_DISPONIBLE

# ─────────────────────────────────────────
#  COLORES Y FUENTES
# ─────────────────────────────────────────
BG_MAIN    = "#f0f2f5"
BG_HEADER  = "#d9dde3"
BG_WHITE   = "#ffffff"
BG_CARD    = "#ffffff"
COLOR_BLUE = "#1a73e8"
COLOR_RED  = "#e53935"
COLOR_GREEN= "#43a047"
COLOR_GRAY = "#5f6368"
COLOR_LIGHT= "#e8eaf6"
COLOR_WARN = "#f57c00"

FONT_TITLE  = ("Segoe UI", 18, "bold")
FONT_HEADER = ("Segoe UI", 11, "bold")
FONT_NORMAL = ("Segoe UI", 10)
FONT_SMALL  = ("Segoe UI", 9)
FONT_BTN    = ("Segoe UI", 10, "bold")

# ─────────────────────────────────────────
#  BASE DE DATOS
# ─────────────────────────────────────────
DB_FILE = "rae.db"

def get_connection():
    return sqlite3.connect(DB_FILE)

def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS estudiantes (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre   TEXT NOT NULL,
            apellido TEXT NOT NULL,
            grado    TEXT NOT NULL,
            password TEXT NOT NULL DEFAULT '1234'
        )
    """)
    try:
        c.execute("ALTER TABLE estudiantes ADD COLUMN password TEXT NOT NULL DEFAULT '1234'")
    except sqlite3.OperationalError:
        pass

    c.execute("""
        CREATE TABLE IF NOT EXISTS registros (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            estudiante_id   INTEGER NOT NULL,
            tipo            TEXT NOT NULL,
            fecha           TEXT NOT NULL,
            hora            TEXT NOT NULL,
            observaciones   TEXT,
            registrado_por  TEXT DEFAULT 'Sistema',
            FOREIGN KEY (estudiante_id) REFERENCES estudiantes(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario  TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol      TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS estudiantes_faces (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            estudiante_id INTEGER NOT NULL,
            encoding      BLOB NOT NULL,
            FOREIGN KEY (estudiante_id) REFERENCES estudiantes(id) ON DELETE CASCADE
        )
    """)

    c.execute("SELECT COUNT(*) FROM estudiantes")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO estudiantes (nombre, apellido, grado, password) VALUES (?,?,?,?)",
            [("Juan","Pérez","5to","1234"),
             ("María","García","6to","1234"),
             ("Carlos","Rodríguez","5to","1234")]
        )

    c.execute("SELECT COUNT(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO usuarios (usuario, password, rol) VALUES (?,?,?)",
            [("porteria","1234","porteria"),("admin","admin","admin")]
        )

    conn.commit()
    conn.close()


# ─────────────────────────────────────────
#  UTILIDADES DE UI
# ─────────────────────────────────────────
def make_btn(parent, text, command, color=COLOR_BLUE, fg="white", width=18):
    btn = tk.Button(
        parent, text=text, command=command,
        bg=color, fg=fg, font=FONT_BTN,
        relief="flat", cursor="hand2",
        padx=10, pady=6, width=width
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=_darken(color)))
    btn.bind("<Leave>", lambda e: btn.config(bg=color))
    return btn

def _darken(hex_color):
    return {
        COLOR_BLUE:  "#1558b0",
        COLOR_RED:   "#b71c1c",
        COLOR_GREEN: "#2e7d32",
        COLOR_GRAY:  "#424242",
        COLOR_WARN:  "#e65100",
    }.get(hex_color, hex_color)

def make_header(parent, title):
    hdr = tk.Frame(parent, bg=BG_HEADER, height=50)
    hdr.pack(fill="x")
    tk.Label(hdr, text=title, bg=BG_HEADER,
             font=("Segoe UI", 13, "bold"), padx=14).pack(side="left", pady=10)
    return hdr

def make_navbar(parent, items):
    nav = tk.Frame(parent, bg=BG_HEADER, height=34)
    nav.pack(fill="x")
    for label, cmd in items:
        tk.Button(nav, text=label, command=cmd,
                  bg=BG_HEADER, fg="#333", font=FONT_NORMAL,
                  relief="flat", cursor="hand2", padx=12, pady=5).pack(side="left")
    return nav


# ─────────────────────────────────────────
#  VENTANA BASE
# ─────────────────────────────────────────
class BaseWindow(tk.Toplevel):
    def __init__(self, master, title="RAE", size="900x620"):
        super().__init__(master)
        self.title(title)
        self.geometry(size)
        self.configure(bg=BG_MAIN)
        self.resizable(True, True)


# ═══════════════════════════════════════════════════════════════
#  PANTALLA INICIO
# ═══════════════════════════════════════════════════════════════
class PantallaInicio(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG_MAIN)
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=BG_HEADER)
        hdr.pack(fill="x")
        tk.Label(hdr, text='· "RAE" : REGISTRO DE ASISTENCIA ESTUDIANTIL.',
                 bg=BG_HEADER, font=("Segoe UI", 11, "bold"), padx=16).pack(side="left", pady=12)

        # Indicador de estado de cámara
        estado_color = COLOR_GREEN if CAMARA_DISPONIBLE else COLOR_WARN
        estado_texto = "✔ Cámara disponible" if CAMARA_DISPONIBLE else "⚠ Cámara no disponible (ver consola)"
        tk.Label(hdr, text=estado_texto, bg=BG_HEADER,
                 font=FONT_SMALL, fg=estado_color, padx=10).pack(side="right", pady=12)

        tk.Label(self, text="Registro de Ingreso / Salida",
                 bg=BG_MAIN, font=FONT_TITLE).pack(pady=(40, 20))

        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=40, pady=30)
        card.pack(ipadx=20)

        tk.Label(card, text="Ingresar Datos Manualmente",
                 bg=BG_CARD, font=FONT_HEADER).pack(pady=(0, 14))

        self.entry_id = tk.Entry(card, font=FONT_NORMAL, width=32,
                                 bd=1, relief="solid", fg=COLOR_GRAY)
        self.entry_id.insert(0, "Número de Identificación")
        self.entry_id.bind("<FocusIn>",  self._clear_placeholder)
        self.entry_id.bind("<FocusOut>", self._restore_placeholder)
        self.entry_id.bind("<Return>",   lambda e: self._registrar())
        self.entry_id.pack(pady=(0, 16), ipady=8)

        make_btn(card, "Registrar", self._registrar, width=30).pack()

        # Botón cámara (deshabilitado si no está disponible)
        btn_camara = make_btn(
            card,
            "🔍 Identificación por cámara",
            self._abrir_camara if CAMARA_DISPONIBLE else self._mostrar_error_camara,
            color=COLOR_GREEN if CAMARA_DISPONIBLE else COLOR_GRAY,
            width=30
        )
        btn_camara.pack(pady=10)
        if not CAMARA_DISPONIBLE:
            btn_camara.config(text="🔍 Cámara no disponible (clic para info)")

        icons_frame = tk.Frame(self, bg=BG_MAIN)
        icons_frame.pack(pady=40)
        self._make_icon(icons_frame, "✔", "Registro\nexitoso", COLOR_BLUE, self._ver_exitoso)
        self._make_icon(icons_frame, "👤", "Acceso personal\nportería", COLOR_GREEN, self._login_porteria)
        self._make_icon(icons_frame, "👥", "Acceso\nadministrador", "#7c4dff", self._login_admin)

    def _make_icon(self, parent, symbol, label, color, command):
        frame = tk.Frame(parent, bg=BG_MAIN)
        frame.pack(side="left", padx=24)
        tk.Button(frame, text=symbol, font=("Segoe UI", 22),
                  bg=color, fg="white", width=3, height=1,
                  relief="flat", cursor="hand2", command=command).pack()
        tk.Label(frame, text=label, bg=BG_MAIN,
                 font=FONT_SMALL, fg=COLOR_GRAY, justify="center").pack(pady=4)

    def _clear_placeholder(self, e):
        if self.entry_id.get() == "Número de Identificación":
            self.entry_id.delete(0, "end")
            self.entry_id.config(fg="black")

    def _restore_placeholder(self, e):
        if not self.entry_id.get():
            self.entry_id.insert(0, "Número de Identificación")
            self.entry_id.config(fg=COLOR_GRAY)

    def _registrar(self):
        num_id = self.entry_id.get().strip()
        if not num_id or num_id == "Número de Identificación":
            messagebox.showwarning("Campo requerido", "Ingrese un número de identificación.")
            return

        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, nombre, apellido FROM estudiantes WHERE id=?", (num_id,))
        row = c.fetchone()
        conn.close()

        if not row:
            messagebox.showerror("No encontrado", f"No se encontró el estudiante con ID {num_id}.")
            return

        self._realizar_registro(row[0], row[1], row[2])

    def _realizar_registro(self, est_id, nombre, apellido):
        now   = datetime.now()
        fecha = now.strftime("%Y-%m-%d")
        hora  = now.strftime("%I:%M %p")

        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT tipo FROM registros
            WHERE estudiante_id=? AND fecha=?
            ORDER BY id DESC LIMIT 1
        """, (est_id, fecha))
        ultimo = c.fetchone()
        tipo = "Salida" if ultimo and ultimo[0] == "Ingreso" else "Ingreso"

        c.execute("""
            INSERT INTO registros (estudiante_id, tipo, fecha, hora, observaciones)
            VALUES (?,?,?,?,?)
        """, (est_id, tipo, fecha, hora, "Registrado automáticamente"))
        conn.commit()
        conn.close()

        PantallaRegistroExitoso(self.winfo_toplevel(), nombre, apellido, tipo)

    def _mostrar_error_camara(self):
        msg = (
            "La cámara no está disponible.\n\n"
            "Para activarla, instala las dependencias desde la consola:\n\n"
            "  pip install opencv-python\n"
            "  pip install cmake\n"
            "  pip install dlib\n"
            "  pip install face_recognition\n"
            "  pip install git+https://github.com/ageitgey/face_recognition_models\n"
            "  pip install Pillow\n\n"
            "Luego reinicia el programa."
        )
        messagebox.showinfo("Cámara no disponible", msg)

    def _abrir_camara(self):
        try:
            VentanaCamaraReconocimiento(self.winfo_toplevel(), self._realizar_registro)
        except Exception as e:
            messagebox.showerror("Error de cámara", f"No se pudo iniciar la cámara:\n{e}")

    def _ver_exitoso(self):
        PantallaRegistroExitoso(self.winfo_toplevel(), "Demo", "Usuario", "Ingreso")

    def _login_porteria(self):
        LoginWindow(self.winfo_toplevel(), "porteria")

    def _login_admin(self):
        LoginWindow(self.winfo_toplevel(), "admin")


# ═══════════════════════════════════════════════════════════════
#  VENTANA DE RECONOCIMIENTO FACIAL — MEJORADA
# ═══════════════════════════════════════════════════════════════
class VentanaCamaraReconocimiento(BaseWindow):
    """
    Ventana de reconocimiento facial con:
    - Inicialización de cámara FUERA del bucle (correcta)
    - Threading con daemon=True para no bloquear el cierre
    - Actualización de UI via after() (thread-safe)
    - Liberación garantizada de recursos
    - Reconocimiento cada N frames para mejor rendimiento
    """
    RECONOCER_CADA_N_FRAMES = 3   # procesar reconocimiento cada 3 frames
    ANCHO_VIDEO = 640
    ALTO_VIDEO  = 480

    def __init__(self, master, callback_registro):
        super().__init__(master, "Reconocimiento Facial", "750x600")
        self.callback_registro = callback_registro

        # Estado del hilo
        self._activo         = False
        self._cap            = None       # objeto VideoCapture — se inicializa UNA VEZ
        self._frame_actual   = None       # frame más reciente (compartido entre hilos)
        self._lock           = threading.Lock()
        self._rostro_reconocido = None    # (est_id, nombre) o None
        self._contador_frames   = 0

        self._build()

    # ── Construcción de la UI ──────────────────────────────────
    def _build(self):
        make_header(self, "RAE – Identificación por Cámara")

        # Canvas para video (640×480)
        self.canvas_video = tk.Canvas(
            self, width=self.ANCHO_VIDEO, height=self.ALTO_VIDEO,
            bg="black", bd=0, highlightthickness=0
        )
        self.canvas_video.pack(padx=10, pady=8)

        # Etiqueta de estado
        self.lbl_info = tk.Label(
            self, text="⏳ Iniciando cámara...",
            bg=BG_MAIN, font=FONT_HEADER, fg=COLOR_GRAY
        )
        self.lbl_info.pack(pady=4)

        # Botón confirmar
        self.btn_confirmar = make_btn(
            self, "✔ Confirmar Registro", self._confirmar,
            color=COLOR_GREEN, width=24
        )
        self.btn_confirmar.pack(pady=6)
        self.btn_confirmar.config(state="disabled")

        # Cargar codificaciones
        self._encodings_conocidos, self._ids_conocidos, self._nombres_conocidos = \
            self._cargar_codificaciones()

        # Inicializar cámara
        self._inicializar_camara()

        # Cerrar limpiamente
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    # ── Inicialización de la cámara (FUERA del bucle) ─────────
    def _inicializar_camara(self):
        """
        Abre VideoCapture UNA SOLA VEZ antes de iniciar el hilo.
        Intentamos varios índices de cámara (0, 1, 2) por si la
        integrada no es la 0 en este equipo.
        """
        for indice in (0, 1, 2):
            cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)  # CAP_DSHOW = más rápido en Windows
            if cap.isOpened():
                # Configurar resolución para mejor rendimiento
                cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.ANCHO_VIDEO)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.ALTO_VIDEO)
                cap.set(cv2.CAP_PROP_FPS, 30)
                self._cap = cap
                break

        if self._cap is None or not self._cap.isOpened():
            self.lbl_info.config(
                text="❌ No se pudo abrir la cámara",
                fg=COLOR_RED
            )
            messagebox.showerror(
                "Cámara no disponible",
                "No se encontró ninguna cámara.\n"
                "Verifica que esté conectada y no esté en uso por otro programa."
            )
            return

        # Cámara abierta → arrancar hilo de captura
        self._activo = True
        hilo = threading.Thread(target=self._bucle_captura, daemon=True)
        hilo.start()

        # Iniciar actualización de UI
        self._actualizar_ui()

    # ── Bucle de captura (hilo secundario) ────────────────────
    def _bucle_captura(self):
        """
        Lee frames de la cámara de forma continua.
        El reconocimiento solo se ejecuta cada N frames para no
        saturar la CPU en equipos lentos.
        IMPORTANTE: nunca modifica widgets de Tkinter desde aquí.
        """
        while self._activo:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            # Voltear horizontalmente (efecto espejo)
            frame = cv2.flip(frame, 1)
            self._contador_frames += 1

            # Reconocimiento facial cada N frames
            if self._contador_frames % self.RECONOCER_CADA_N_FRAMES == 0:
                self._procesar_reconocimiento(frame)

            # Guardar frame para la UI (con lock para seguridad de hilo)
            with self._lock:
                self._frame_actual = frame.copy()

    # ── Reconocimiento facial ──────────────────────────────────
    def _procesar_reconocimiento(self, frame):
        """
        Detecta caras y las compara con los encodings conocidos.
        Se ejecuta en el hilo secundario.
        """
        # Reducir resolución para reconocimiento (más rápido)
        pequeno = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb     = cv2.cvtColor(pequeno, cv2.COLOR_BGR2RGB)

        ubicaciones = face_recognition.face_locations(rgb, model="hog")
        encodings   = face_recognition.face_encodings(rgb, ubicaciones)

        reconocido = None
        for encoding in encodings:
            if self._encodings_conocidos:
                coincidencias = face_recognition.compare_faces(
                    self._encodings_conocidos, encoding, tolerance=0.5
                )
                distancias = face_recognition.face_distance(
                    self._encodings_conocidos, encoding
                )
                if True in coincidencias:
                    mejor_idx = int(np.argmin(distancias))
                    if coincidencias[mejor_idx]:
                        reconocido = (
                            self._ids_conocidos[mejor_idx],
                            self._nombres_conocidos[mejor_idx]
                        )
                        break

        with self._lock:
            self._rostro_reconocido = reconocido

    # ── Actualización de la UI (hilo principal, via after) ────
    def _actualizar_ui(self):
        """
        Método llamado cada ~30 ms desde el hilo principal de Tkinter.
        Lee el frame actual y lo muestra en el canvas.
        """
        if not self._activo:
            return

        with self._lock:
            frame = self._frame_actual
            reconocido = self._rostro_reconocido

        if frame is not None:
            # Dibujar resultado sobre el frame
            frame_mostrar = frame.copy()
            self._dibujar_resultado(frame_mostrar, reconocido)

            # Convertir BGR → RGB → PIL → ImageTk
            rgb_frame = cv2.cvtColor(frame_mostrar, cv2.COLOR_BGR2RGB)
            img_pil   = Image.fromarray(rgb_frame)
            img_pil   = img_pil.resize((self.ANCHO_VIDEO, self.ALTO_VIDEO))
            imgtk     = ImageTk.PhotoImage(image=img_pil)

            self.canvas_video.imgtk = imgtk  # evitar garbage collection
            self.canvas_video.create_image(0, 0, anchor="nw", image=imgtk)

            # Actualizar etiqueta de estado
            if reconocido:
                self.lbl_info.config(
                    text=f"✅ Reconocido: {reconocido[1]}",
                    fg=COLOR_GREEN
                )
                self.btn_confirmar.config(state="normal")
            else:
                self.lbl_info.config(text="🔍 Buscando rostro...", fg=COLOR_GRAY)
                self.btn_confirmar.config(state="disabled")

        # Llamar de nuevo en ~33 ms (~30 fps)
        if self._activo:
            self.after(33, self._actualizar_ui)

    def _dibujar_resultado(self, frame, reconocido):
        """Dibuja rectángulos y texto sobre el frame."""
        rgb_temp      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        ubicaciones   = face_recognition.face_locations(
            cv2.resize(rgb_temp, (0, 0), fx=0.5, fy=0.5), model="hog"
        )

        for (top, right, bottom, left) in ubicaciones:
            # Escalar de vuelta al tamaño original
            top, right, bottom, left = top*2, right*2, bottom*2, left*2
            if reconocido:
                color  = (67, 160, 71)   # verde
                nombre = reconocido[1]
            else:
                color  = (229, 57, 53)   # rojo
                nombre = "Desconocido"

            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            # Fondo del texto
            cv2.rectangle(frame, (left, top - 28), (right, top), color, -1)
            cv2.putText(frame, nombre, (left + 4, top - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1,
                        cv2.LINE_AA)

    # ── Cargar encodings de la BD ──────────────────────────────
    def _cargar_codificaciones(self):
        encodings, ids, nombres = [], [], []
        try:
            conn = get_connection()
            c    = conn.cursor()
            c.execute("""
                SELECT f.estudiante_id, f.encoding, e.nombre||' '||e.apellido
                FROM estudiantes_faces f
                JOIN estudiantes e ON f.estudiante_id = e.id
            """)
            for est_id, blob, nombre in c.fetchall():
                try:
                    enc = pickle.loads(blob)
                    encodings.append(enc)
                    ids.append(est_id)
                    nombres.append(nombre)
                except Exception:
                    pass
            conn.close()
        except Exception as e:
            print(f"Error cargando encodings: {e}")
        return encodings, ids, nombres

    # ── Confirmar registro ─────────────────────────────────────
    def _confirmar(self):
        with self._lock:
            reconocido = self._rostro_reconocido

        if reconocido:
            est_id, nombre = reconocido
            partes = nombre.split(" ", 1)
            nom = partes[0]
            ape = partes[1] if len(partes) > 1 else ""
            self._cerrar()
            self.callback_registro(est_id, nom, ape)
        else:
            messagebox.showwarning(
                "Sin reconocimiento",
                "No se reconoció ningún rostro.\nAcérquese a la cámara con buena iluminación."
            )

    # ── Cierre limpio ──────────────────────────────────────────
    def _cerrar(self):
        """Detiene el hilo y libera la cámara antes de destruir la ventana."""
        self._activo = False
        time.sleep(0.1)  # dar tiempo al hilo a detectar el flag

        if self._cap is not None and self._cap.isOpened():
            self._cap.release()
            self._cap = None

        try:
            self.destroy()
        except tk.TclError:
            pass  # ventana ya destruida


# ═══════════════════════════════════════════════════════════════
#  LOGIN
# ═══════════════════════════════════════════════════════════════
class LoginWindow(BaseWindow):
    def __init__(self, master, rol_esperado):
        super().__init__(master, "Iniciar sesión", "380x280")
        self.rol_esperado = rol_esperado
        self._build()

    def _build(self):
        tk.Label(self, text="Iniciar Sesión", bg=BG_MAIN, font=FONT_TITLE).pack(pady=(30, 20))

        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=30, pady=20)
        card.pack()

        tk.Label(card, text="Usuario:", bg=BG_CARD, font=FONT_NORMAL).pack(anchor="w")
        self.e_user = tk.Entry(card, font=FONT_NORMAL, width=28, bd=1, relief="solid")
        self.e_user.pack(pady=(2, 10), ipady=5)

        tk.Label(card, text="Contraseña:", bg=BG_CARD, font=FONT_NORMAL).pack(anchor="w")
        self.e_pass = tk.Entry(card, font=FONT_NORMAL, width=28, show="*", bd=1, relief="solid")
        self.e_pass.pack(pady=(2, 14), ipady=5)
        self.e_pass.bind("<Return>", lambda e: self._login())

        make_btn(card, "Entrar", self._login, width=28).pack()

    def _login(self):
        usuario  = self.e_user.get().strip()
        password = self.e_pass.get().strip()

        conn = get_connection()
        c    = conn.cursor()
        c.execute("SELECT rol FROM usuarios WHERE usuario=? AND password=?", (usuario, password))
        row  = c.fetchone()
        conn.close()

        if not row:
            messagebox.showerror("Error", "Usuario o contraseña incorrectos.")
            return

        rol = row[0]
        if rol != self.rol_esperado:
            messagebox.showerror("Error", f"No tiene permisos de '{self.rol_esperado}'.")
            return

        self.destroy()
        if rol == "porteria":
            _abrir_panel(self.master, PanelPorteria)
        else:
            _abrir_panel(self.master, PanelAdministracion)


def _abrir_panel(master, cls):
    win = tk.Toplevel(master)
    win.geometry("1000x660")
    win.configure(bg=BG_MAIN)
    win.title("RAE")
    cls(win)


# ═══════════════════════════════════════════════════════════════
#  REGISTRO EXITOSO
# ═══════════════════════════════════════════════════════════════
class PantallaRegistroExitoso(BaseWindow):
    def __init__(self, master, nombre, apellido, tipo):
        super().__init__(master, "Registro Exitoso", "540x380")
        self._build(nombre, apellido, tipo)

    def _build(self, nombre, apellido, tipo):
        make_header(self, "RAE")
        tk.Label(self, text="✔", font=("Segoe UI", 48), bg=BG_MAIN, fg=COLOR_GREEN).pack(pady=(40,6))
        tk.Label(self, text="¡Registro Exitoso!", bg=BG_MAIN, font=("Segoe UI",16,"bold")).pack()

        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=30, pady=20)
        card.pack(pady=20)
        tk.Label(card, text=f"Tu {tipo.lower()} ha sido registrado correctamente.",
                 bg=BG_CARD, font=FONT_NORMAL, fg=COLOR_GRAY).pack()
        tk.Label(card, text=f"Estudiante: {nombre} {apellido}",
                 bg=BG_CARD, font=FONT_HEADER).pack(pady=(8,0))
        hora = datetime.now().strftime("%I:%M %p")
        tk.Label(card, text=f"Hora: {hora}", bg=BG_CARD, font=FONT_NORMAL, fg=COLOR_GRAY).pack()

        make_btn(self, "Volver al Inicio", self.destroy, width=20).pack(pady=8)
        # Auto-cerrar después de 5 segundos
        self.after(5000, lambda: self.destroy() if self.winfo_exists() else None)


# ═══════════════════════════════════════════════════════════════
#  PANEL PORTERÍA
# ═══════════════════════════════════════════════════════════════
class PanelPorteria(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG_MAIN)
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        make_header(self, "RAE")
        make_navbar(self, [
            ("Inicio", lambda: None),
            ("Monitoreo", self._refresh),
            ("Administración", lambda: None),
        ])

        tk.Label(self, text="Panel de Monitoreo (Personal de Portería)",
                 bg=BG_MAIN, font=FONT_TITLE).pack(anchor="w", padx=20, pady=14)

        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=16, pady=16)
        card.pack(fill="both", expand=True, padx=20, pady=(0,20))

        tk.Label(card, text="Registros en Tiempo Real", bg=BG_CARD, font=FONT_HEADER).pack(anchor="w", pady=(0,10))

        cols = ("Estudiante", "Tipo de Registro", "Hora", "Acciones")
        self.tree = ttk.Treeview(card, columns=cols, show="headings", height=12)
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=200 if col != "Acciones" else 120)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._on_double_click)

        make_btn(card, "🔄 Actualizar", self._refresh, color=COLOR_GRAY, width=16).pack(anchor="e", pady=6)
        self._refresh()

    def _refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        conn = get_connection()
        c    = conn.cursor()
        c.execute("""
            SELECT r.id, e.nombre||' '||e.apellido, r.tipo, r.hora
            FROM registros r JOIN estudiantes e ON r.estudiante_id=e.id
            ORDER BY r.id DESC LIMIT 20
        """)
        for reg_id, nombre, tipo, hora in c.fetchall():
            self.tree.insert("", "end", iid=reg_id,
                             values=(nombre, tipo, hora, "Doble clic → detalles"))
        conn.close()

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if sel:
            DetallesRegistro(self.winfo_toplevel(), int(sel[0]))


# ═══════════════════════════════════════════════════════════════
#  DETALLES DE REGISTRO
# ═══════════════════════════════════════════════════════════════
class DetallesRegistro(BaseWindow):
    def __init__(self, master, reg_id):
        super().__init__(master, "Detalles de Registro", "700x420")
        self._build(reg_id)

    def _build(self, reg_id):
        make_header(self, "RAE")
        tk.Label(self, text="Detalles de Registro", bg=BG_MAIN, font=FONT_TITLE).pack(anchor="w", padx=20, pady=12)

        conn = get_connection()
        c    = conn.cursor()
        c.execute("""
            SELECT e.nombre||' '||e.apellido, e.id, r.tipo,
                   r.fecha||' '||r.hora, r.observaciones, r.registrado_por
            FROM registros r JOIN estudiantes e ON r.estudiante_id=e.id
            WHERE r.id=?
        """, (reg_id,))
        row  = c.fetchone()
        conn.close()

        if not row:
            tk.Label(self, text="Registro no encontrado.", bg=BG_MAIN, font=FONT_NORMAL).pack(pady=40)
            return

        nombre, est_id, tipo, fecha_hora, obs, reg_por = row
        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=30, pady=24)
        card.pack(fill="x", padx=20)

        def field(lbl, val, r, c_col):
            tk.Label(card, text=lbl+":", bg=BG_CARD, font=FONT_HEADER).grid(row=r,   column=c_col*2, sticky="w", pady=4, padx=(0,8))
            tk.Label(card, text=val,     bg=BG_CARD, font=FONT_NORMAL, fg=COLOR_GRAY).grid(row=r+1, column=c_col*2, sticky="w")

        field("Estudiante",       nombre,      0, 0)
        field("ID Estudiante",    str(est_id), 0, 1)
        field("Tipo de Registro", tipo,        2, 0)
        field("Fecha y Hora",     fecha_hora,  2, 1)

        tk.Label(card, text="Observaciones:", bg=BG_CARD, font=FONT_HEADER).grid(row=4, column=0, sticky="w", pady=(12,0))
        tk.Label(card, text=obs or "—",       bg=BG_CARD, font=FONT_NORMAL, fg=COLOR_GRAY).grid(row=5, column=0, sticky="w")
        tk.Label(card, text="Registrado por:", bg=BG_CARD, font=FONT_HEADER).grid(row=6, column=0, sticky="w", pady=(12,0))
        tk.Label(card, text=reg_por or "—",    bg=BG_CARD, font=FONT_NORMAL, fg=COLOR_GRAY).grid(row=7, column=0, sticky="w")

        make_btn(self, "Volver al Monitoreo", self.destroy, width=22).pack(anchor="w", padx=20, pady=16)


# ═══════════════════════════════════════════════════════════════
#  PANEL ADMINISTRACIÓN
# ═══════════════════════════════════════════════════════════════
class PanelAdministracion(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG_MAIN)
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        make_header(self, "RAE")
        make_navbar(self, [("Inicio", lambda: None), ("Monitoreo", lambda: None), ("Administración", lambda: None)])
        tk.Label(self, text="Panel de Administración", bg=BG_MAIN, font=FONT_TITLE).pack(pady=(30,20))

        cards_frame = tk.Frame(self, bg=BG_MAIN)
        cards_frame.pack()

        for icon, label, cmd in [
            ("👥", "Gestionar estudiantes", self._gestionar_estudiantes),
            ("🕐", "Consultar historial",   self._consultar_historial),
            ("📄", "Generar reportes",      self._generar_reportes),
        ]:
            f = tk.Frame(cards_frame, bg=BG_CARD, bd=1, relief="solid", padx=30, pady=30)
            f.pack(side="left", padx=16, ipadx=10)
            tk.Label(f, text=icon,  font=("Segoe UI",32), bg=BG_CARD, fg=COLOR_BLUE).pack(pady=(0,8))
            tk.Label(f, text=label, font=FONT_HEADER,     bg=BG_CARD).pack(pady=(0,14))
            make_btn(f, "Ir", cmd, width=8).pack()

    def _gestionar_estudiantes(self): _abrir_panel(self.winfo_toplevel(), GestionEstudiantes)
    def _consultar_historial(self):   _abrir_panel(self.winfo_toplevel(), ConsultaHistorial)
    def _generar_reportes(self):      _abrir_panel(self.winfo_toplevel(), GeneracionReportes)


# ═══════════════════════════════════════════════════════════════
#  GESTIÓN DE ESTUDIANTES (con captura facial mejorada)
# ═══════════════════════════════════════════════════════════════
class GestionEstudiantes(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG_MAIN)
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        make_header(self, "RAE")
        make_navbar(self, [("Inicio",lambda:None),("Monitoreo",lambda:None),("Administración",lambda:None)])

        top = tk.Frame(self, bg=BG_MAIN)
        top.pack(fill="x", padx=20, pady=10)
        tk.Label(top, text="Gestión de Estudiantes", bg=BG_MAIN, font=FONT_TITLE).pack(side="left")
        make_btn(top, "Volver al panel", self.winfo_toplevel().destroy, width=16).pack(side="right")

        btn_row = tk.Frame(self, bg=BG_MAIN)
        btn_row.pack(anchor="w", padx=20, pady=(0,10))
        make_btn(btn_row, "Añadir Estudiante",  self._añadir,   width=18).pack(side="left", padx=4)
        make_btn(btn_row, "Editar Estudiante",   self._editar,   color=COLOR_GRAY, width=18).pack(side="left", padx=4)
        make_btn(btn_row, "Eliminar Estudiante", self._eliminar, color=COLOR_RED,  width=18).pack(side="left", padx=4)

        sc = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=14, pady=10)
        sc.pack(fill="x", padx=20, pady=(0,10))
        tk.Label(sc, text="Buscar Estudiante", bg=BG_CARD, font=FONT_HEADER).pack(anchor="w")
        self.e_buscar = tk.Entry(sc, font=FONT_NORMAL, width=60, bd=1, relief="solid")
        self.e_buscar.pack(anchor="w", pady=(4,8), ipady=5)
        self.e_buscar.insert(0, "Buscar por nombre o ID")
        self.e_buscar.bind("<Return>", lambda e: self._buscar())
        make_btn(sc, "Buscar", self._buscar, width=10).pack(anchor="w")

        cols = ("ID","Nombre","Apellido","Grado","Acciones")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=10)
        widths = {"ID":70,"Nombre":200,"Apellido":200,"Grado":100,"Acciones":150}
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[col])
        self.tree.pack(fill="both", expand=True, padx=20, pady=(0,16))
        self._cargar_todos()

    def _cargar_todos(self, filtro=""):
        for row in self.tree.get_children():
            self.tree.delete(row)
        conn = get_connection()
        c    = conn.cursor()
        if filtro:
            c.execute("""
                SELECT id, nombre, apellido, grado FROM estudiantes
                WHERE nombre LIKE ? OR apellido LIKE ? OR CAST(id AS TEXT) LIKE ?
            """, (f"%{filtro}%",)*3)
        else:
            c.execute("SELECT id, nombre, apellido, grado FROM estudiantes")
        for row in c.fetchall():
            self.tree.insert("", "end", iid=row[0], values=(*row, "Editar | Eliminar"))
        conn.close()

    def _buscar(self):
        q = self.e_buscar.get().strip()
        self._cargar_todos("" if q == "Buscar por nombre o ID" else q)

    def _get_selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Seleccione", "Seleccione un estudiante.")
            return None
        return int(sel[0])

    def _añadir(self):
        FormEstudiante(self.winfo_toplevel(), None, self._cargar_todos)

    def _editar(self):
        est_id = self._get_selected_id()
        if est_id:
            FormEstudiante(self.winfo_toplevel(), est_id, self._cargar_todos)

    def _eliminar(self):
        est_id = self._get_selected_id()
        if not est_id:
            return
        if messagebox.askyesno("Confirmar", "¿Eliminar este estudiante y sus registros?"):
            conn = get_connection()
            c    = conn.cursor()
            c.execute("DELETE FROM registros WHERE estudiante_id=?", (est_id,))
            c.execute("DELETE FROM estudiantes WHERE id=?", (est_id,))
            conn.commit()
            conn.close()
            self._cargar_todos()
            messagebox.showinfo("Listo", "Estudiante eliminado.")


# ═══════════════════════════════════════════════════════════════
#  FORMULARIO ESTUDIANTE (captura facial mejorada)
# ═══════════════════════════════════════════════════════════════
class FormEstudiante(BaseWindow):
    def __init__(self, master, est_id, callback):
        super().__init__(master, "Formulario Estudiante", "440x520")
        self.est_id        = est_id
        self.callback      = callback
        self.face_encoding = None
        self._build()

    def _build(self):
        titulo = "Editar Estudiante" if self.est_id else "Añadir Estudiante"
        tk.Label(self, text=titulo, bg=BG_MAIN, font=FONT_TITLE).pack(pady=(20,10))

        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=24, pady=18)
        card.pack()

        def campo(label, row, show=None):
            tk.Label(card, text=label+":", bg=BG_CARD, font=FONT_NORMAL).grid(row=row, column=0, sticky="w", pady=4)
            e = tk.Entry(card, font=FONT_NORMAL, width=22, bd=1, relief="solid", show=show)
            e.grid(row=row, column=1, padx=(8,0), pady=4, ipady=4)
            return e

        self.e_nombre   = campo("Nombre",    0)
        self.e_apellido = campo("Apellido",  1)
        self.e_grado    = campo("Grado",     2)
        self.e_password = campo("Contraseña",3, show="*")

        # Botón captura de rostro
        cam_color = COLOR_GRAY if CAMARA_DISPONIBLE else COLOR_GRAY
        cam_texto = "📸 Capturar Rostro" if CAMARA_DISPONIBLE else "📸 Cámara no disponible"
        self.btn_cap = make_btn(card, cam_texto, self._capturar_rostro,
                                color=cam_color, width=28)
        self.btn_cap.grid(row=4, column=0, columnspan=2, pady=12)
        if not CAMARA_DISPONIBLE:
            self.btn_cap.config(state="disabled")

        if self.est_id:
            conn = get_connection()
            c    = conn.cursor()
            c.execute("SELECT nombre, apellido, grado, password FROM estudiantes WHERE id=?", (self.est_id,))
            row  = c.fetchone()
            conn.close()
            if row:
                self.e_nombre.insert(0, row[0])
                self.e_apellido.insert(0, row[1])
                self.e_grado.insert(0, row[2])
                self.e_password.insert(0, row[3])

        make_btn(self, "Guardar", self._guardar, width=20).pack(pady=12)

    def _capturar_rostro(self):
        """
        Captura el rostro usando VideoCapture de forma correcta:
        - Inicializa FUERA del bucle
        - Libera al terminar
        - Muestra ventana de OpenCV con instrucciones
        """
        if not CAMARA_DISPONIBLE:
            messagebox.showinfo("No disponible", "Instala las dependencias de cámara primero.")
            return

        cap = None
        for indice in (0, 1, 2):
            cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
            if cap.isOpened():
                break

        if cap is None or not cap.isOpened():
            messagebox.showerror("Error", "No se pudo acceder a la cámara.")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        capturado   = False
        ventana_nom = "Captura de Rostro — ESPACIO=capturar  ESC=cancelar"

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            ubicaciones = face_recognition.face_locations(rgb, model="hog")
            encodings   = face_recognition.face_encodings(rgb, ubicaciones)

            for (top, right, bottom, left) in ubicaciones:
                cv2.rectangle(frame, (left, top), (right, bottom), (67,160,71), 2)
                cv2.putText(frame, "Listo — presiona ESPACIO",
                            (left, top - 8), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (67, 160, 71), 1, cv2.LINE_AA)

            # Instrucciones en pantalla
            cv2.putText(frame, "ESPACIO = Capturar  |  ESC = Cancelar",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (255, 255, 255), 1, cv2.LINE_AA)

            cv2.imshow(ventana_nom, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == 32 and encodings:   # ESPACIO
                self.face_encoding = encodings[0]
                capturado = True
                break
            elif key == 27:               # ESC
                break

        cap.release()
        cv2.destroyAllWindows()

        if capturado:
            self.btn_cap.config(text="✅ Rostro capturado", bg=COLOR_GREEN)
            messagebox.showinfo("Éxito", "Rostro capturado correctamente.\nSe guardará al presionar 'Guardar'.")
        else:
            messagebox.showinfo("Cancelado", "No se capturó ningún rostro.")

    def _guardar(self):
        nombre   = self.e_nombre.get().strip()
        apellido = self.e_apellido.get().strip()
        grado    = self.e_grado.get().strip()
        password = self.e_password.get().strip()

        if not all([nombre, apellido, grado, password]):
            messagebox.showwarning("Campos vacíos", "Complete todos los campos.")
            return

        conn = get_connection()
        c    = conn.cursor()
        if self.est_id:
            c.execute("""
                UPDATE estudiantes SET nombre=?, apellido=?, grado=?, password=? WHERE id=?
            """, (nombre, apellido, grado, password, self.est_id))
        else:
            c.execute("""
                INSERT INTO estudiantes (nombre, apellido, grado, password) VALUES (?,?,?,?)
            """, (nombre, apellido, grado, password))
            self.est_id = c.lastrowid

        if self.face_encoding is not None:
            c.execute("DELETE FROM estudiantes_faces WHERE estudiante_id=?", (self.est_id,))
            c.execute("INSERT INTO estudiantes_faces (estudiante_id, encoding) VALUES (?,?)",
                      (self.est_id, pickle.dumps(self.face_encoding)))

        conn.commit()
        conn.close()
        self.callback()
        self.destroy()
        messagebox.showinfo("Guardado", "Estudiante guardado correctamente.")


# ═══════════════════════════════════════════════════════════════
#  HISTORIAL
# ═══════════════════════════════════════════════════════════════
class ConsultaHistorial(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG_MAIN)
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        make_header(self, "RAE")
        make_navbar(self, [("Inicio",lambda:None),("Monitoreo",lambda:None),("Administración",lambda:None)])

        top = tk.Frame(self, bg=BG_MAIN)
        top.pack(fill="x", padx=20, pady=10)
        tk.Label(top, text="Consulta de Historial", bg=BG_MAIN, font=FONT_TITLE).pack(side="left")
        make_btn(top, "Volver al panel", self.winfo_toplevel().destroy, width=16).pack(side="right")

        filt = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=16, pady=14)
        filt.pack(fill="x", padx=20, pady=(0,10))

        left  = tk.Frame(filt, bg=BG_CARD); left.pack(side="left", padx=(0,20))
        right = tk.Frame(filt, bg=BG_CARD); right.pack(side="left")

        tk.Label(left,  text="Buscar por Nombre:",             bg=BG_CARD, font=FONT_NORMAL).pack(anchor="w")
        tk.Label(right, text="Buscar por Fecha (AAAA-MM-DD):", bg=BG_CARD, font=FONT_NORMAL).pack(anchor="w")

        self.e_nombre = tk.Entry(left,  font=FONT_NORMAL, width=30, bd=1, relief="solid")
        self.e_fecha  = tk.Entry(right, font=FONT_NORMAL, width=22, bd=1, relief="solid")
        self.e_nombre.pack(pady=4, ipady=5)
        self.e_fecha.pack(pady=4,  ipady=5)

        make_btn(filt, "Buscar", self._buscar, width=10).pack(side="left", padx=20, pady=20)

        res = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=16, pady=14)
        res.pack(fill="both", expand=True, padx=20, pady=(0,16))
        tk.Label(res, text="Resultados", bg=BG_CARD, font=FONT_HEADER).pack(anchor="w", pady=(0,8))

        cols = ("Estudiante","Fecha","Hora Ingreso","Hora Salida")
        self.tree = ttk.Treeview(res, columns=cols, show="headings", height=10)
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=220)
        self.tree.pack(fill="both", expand=True)
        self._buscar()

    def _buscar(self):
        for row in self.tree.get_children(): self.tree.delete(row)
        nombre = self.e_nombre.get().strip()
        fecha  = self.e_fecha.get().strip()
        conn   = get_connection()
        c      = conn.cursor()
        q      = """
            SELECT e.nombre||' '||e.apellido, r.fecha,
                   MAX(CASE WHEN r.tipo='Ingreso' THEN r.hora END),
                   MAX(CASE WHEN r.tipo='Salida'  THEN r.hora END)
            FROM registros r JOIN estudiantes e ON r.estudiante_id=e.id WHERE 1=1
        """
        params = []
        if nombre: q += " AND (e.nombre LIKE ? OR e.apellido LIKE ?)"; params += [f"%{nombre}%"]*2
        if fecha:  q += " AND r.fecha=?"; params.append(fecha)
        q += " GROUP BY e.id, r.fecha ORDER BY r.fecha DESC"
        c.execute(q, params)
        for row in c.fetchall():
            self.tree.insert("","end", values=(row[0], row[1], row[2] or "—", row[3] or "—"))
        conn.close()


# ═══════════════════════════════════════════════════════════════
#  REPORTES
# ═══════════════════════════════════════════════════════════════
class GeneracionReportes(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG_MAIN)
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        make_header(self, "RAE")
        make_navbar(self, [("Inicio",lambda:None),("Monitoreo",lambda:None),("Administración",lambda:None)])
        tk.Label(self, text="Generación de Reportes", bg=BG_MAIN, font=FONT_TITLE).pack(anchor="w", padx=20, pady=12)

        filt = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=16, pady=16)
        filt.pack(fill="x", padx=20, pady=(0,10))
        tk.Label(filt, text="Filtros de Reporte", bg=BG_CARD, font=FONT_HEADER).grid(row=0,column=0,columnspan=4,sticky="w",pady=(0,10))

        tk.Label(filt, text="Nombre del Estudiante:", bg=BG_CARD, font=FONT_NORMAL).grid(row=1,column=0,sticky="w")
        self.e_nombre = tk.Entry(filt, font=FONT_NORMAL, width=28, bd=1, relief="solid")
        self.e_nombre.insert(0, "Ej. Juan Pérez")
        self.e_nombre.grid(row=1,column=1,padx=(6,20),ipady=5)

        tk.Label(filt, text="Rango de Fechas:", bg=BG_CARD, font=FONT_NORMAL).grid(row=1,column=2,sticky="w")
        self.e_rango = tk.Entry(filt, font=FONT_NORMAL, width=28, bd=1, relief="solid")
        self.e_rango.insert(0, "AAAA-MM-DD : AAAA-MM-DD")
        self.e_rango.grid(row=1,column=3,padx=(6,0),ipady=5)

        tk.Label(filt, text="Tipo de Reporte:", bg=BG_CARD, font=FONT_NORMAL).grid(row=2,column=0,sticky="w",pady=(10,0))
        self.combo = ttk.Combobox(filt, width=26, values=["Asistencia Diaria","Resumen Mensual","Ausencias"])
        self.combo.current(0)
        self.combo.grid(row=2,column=1,padx=(6,0),pady=(10,0),sticky="w")

        make_btn(filt, "Generar Reporte", self._generar, width=18).grid(row=3,column=0,columnspan=2,sticky="w",pady=14)

        res = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=16, pady=14)
        res.pack(fill="both", expand=True, padx=20, pady=(0,10))
        tk.Label(res, text="Reporte Generado", bg=BG_CARD, font=FONT_HEADER).pack(anchor="w", pady=(0,8))

        cols = ("Fecha","Estudiante","Hora Entrada","Hora Salida","Estado")
        self.tree = ttk.Treeview(res, columns=cols, show="headings", height=8)
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=160)
        self.tree.pack(fill="both", expand=True)

        make_btn(self, "Volver al panel", self.winfo_toplevel().destroy, width=18).pack(anchor="w", padx=20, pady=8)

    def _generar(self):
        for row in self.tree.get_children(): self.tree.delete(row)
        nombre = self.e_nombre.get().strip()
        if nombre == "Ej. Juan Pérez": nombre = ""
        rango = self.e_rango.get().strip()
        fi = ff = ""
        if ":" in rango:
            partes = [p.strip() for p in rango.split(":")]
            if len(partes) == 2: fi, ff = partes

        conn = get_connection(); c = conn.cursor()
        q = """
            SELECT r.fecha, e.nombre||' '||e.apellido,
                   MAX(CASE WHEN r.tipo='Ingreso' THEN r.hora END),
                   MAX(CASE WHEN r.tipo='Salida'  THEN r.hora END)
            FROM registros r JOIN estudiantes e ON r.estudiante_id=e.id WHERE 1=1
        """
        params = []
        if nombre: q += " AND (e.nombre LIKE ? OR e.apellido LIKE ?)"; params += [f"%{nombre}%"]*2
        if fi and ff: q += " AND r.fecha BETWEEN ? AND ?"; params += [fi, ff]
        q += " GROUP BY r.fecha, e.id ORDER BY r.fecha DESC"
        c.execute(q, params)
        rows = c.fetchall(); conn.close()

        for fecha, est, entrada, salida in rows:
            self.tree.insert("","end", values=(fecha, est, entrada or "—", salida or "—",
                                               "Presente" if entrada else "Ausente"))
        if not rows:
            messagebox.showinfo("Sin resultados", "No se encontraron registros con esos filtros.")


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    init_db()

    root = tk.Tk()
    root.title("RAE – Registro de Asistencia Estudiantil")
    root.geometry("900x620")
    root.configure(bg=BG_MAIN)
    root.resizable(True, True)

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Treeview", background=BG_WHITE, foreground="#333",
                    rowheight=28, fieldbackground=BG_WHITE, font=FONT_NORMAL)
    style.configure("Treeview.Heading", background=BG_HEADER, foreground="#333", font=FONT_HEADER)
    style.map("Treeview", background=[("selected", COLOR_LIGHT)])

    PantallaInicio(root)
    root.mainloop()


if __name__ == "__main__":
    main()