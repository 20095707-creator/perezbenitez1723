"""
RAE - Registro de Asistencia Estudiantil
VERSIÓN SIN RECONOCIMIENTO FACIAL (compatible con Python 3.14+)
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
import threading
import time

# ─── Librerías opcionales (cámara básica) ─────────────────────
try:
    import cv2
    CV2_DISPONIBLE = True
except ImportError:
    CV2_DISPONIBLE = False
    print("⚠ OpenCV no instalado. Instala con: pip install opencv-python")

try:
    from PIL import Image, ImageTk
    PIL_DISPONIBLE = True
except ImportError:
    PIL_DISPONIBLE = False
    print("⚠ Pillow no instalado. Instala con: pip install Pillow")

# La cámara estará disponible si OpenCV y Pillow están presentes
CAMARA_DISPONIBLE = CV2_DISPONIBLE and PIL_DISPONIBLE

# ─── Constantes (colores, fuentes, etc.) ──────────────────────
BG_MAIN    = "#f0f2f5"
BG_HEADER  = "#d9dde3"
BG_CARD    = "#ffffff"
COLOR_BLUE = "#1a73e8"
COLOR_RED  = "#e53935"
COLOR_GREEN= "#43a047"
COLOR_GRAY = "#5f6368"
COLOR_WARN = "#f57c00"
FONT_TITLE  = ("Segoe UI", 18, "bold")
FONT_HEADER = ("Segoe UI", 11, "bold")
FONT_NORMAL = ("Segoe UI", 10)
FONT_SMALL  = ("Segoe UI", 9)
FONT_BTN    = ("Segoe UI", 10, "bold")

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
    # Tabla para fotos (guardamos la imagen en formato BLOB)
    c.execute("""
        CREATE TABLE IF NOT EXISTS estudiantes_fotos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            estudiante_id INTEGER NOT NULL,
            foto          BLOB NOT NULL,
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

# ─── Utilidades de UI ─────────────────────────────────────────
def make_btn(parent, text, command, color=COLOR_BLUE, fg="white", width=18):
    btn = tk.Button(parent, text=text, command=command,
                    bg=color, fg=fg, font=FONT_BTN,
                    relief="flat", cursor="hand2", padx=10, pady=6, width=width)
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

        # Indicador de cámara
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

        # Botón de cámara (ahora solo muestra video en vivo)
        btn_camara = make_btn(
            card,
            "📹 Cámara en vivo",
            self._abrir_camara if CAMARA_DISPONIBLE else self._mostrar_error_camara,
            color=COLOR_GREEN if CAMARA_DISPONIBLE else COLOR_GRAY,
            width=30
        )
        btn_camara.pack(pady=10)
        if not CAMARA_DISPONIBLE:
            btn_camara.config(text="📹 Cámara no disponible (clic para info)")

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
        """, (est_id, tipo, fecha, hora, "Registrado manualmente"))
        conn.commit()
        conn.close()
        PantallaRegistroExitoso(self.winfo_toplevel(), nombre, apellido, tipo)

    def _mostrar_error_camara(self):
        msg = "La cámara no está disponible.\nInstala: pip install opencv-python pillow"
        messagebox.showinfo("Cámara no disponible", msg)

    def _abrir_camara(self):
        try:
            VentanaCamaraVivo(self.winfo_toplevel())
        except Exception as e:
            messagebox.showerror("Error de cámara", f"No se pudo iniciar la cámara:\n{e}")

    def _ver_exitoso(self):
        PantallaRegistroExitoso(self.winfo_toplevel(), "Demo", "Usuario", "Ingreso")

    def _login_porteria(self):
        LoginWindow(self.winfo_toplevel(), "porteria")

    def _login_admin(self):
        LoginWindow(self.winfo_toplevel(), "admin")


# ═══════════════════════════════════════════════════════════════
#  VENTANA DE CÁMARA EN VIVO (SIN RECONOCIMIENTO)
# ═══════════════════════════════════════════════════════════════
class VentanaCamaraVivo(BaseWindow):
    ANCHO_VIDEO = 640
    ALTO_VIDEO  = 480

    def __init__(self, master):
        super().__init__(master, "Cámara en vivo", "750x600")
        self._activo = False
        self._cap = None
        self._frame_actual = None
        self._lock = threading.Lock()
        self._build()

    def _build(self):
        make_header(self, "RAE – Cámara en vivo")
        self.canvas_video = tk.Canvas(self, width=self.ANCHO_VIDEO, height=self.ALTO_VIDEO,
                                      bg="black", bd=0, highlightthickness=0)
        self.canvas_video.pack(padx=10, pady=8)
        self.lbl_info = tk.Label(self, text="Iniciando...", bg=BG_MAIN,
                                 font=FONT_HEADER, fg=COLOR_GRAY)
        self.lbl_info.pack(pady=4)
        self._inicializar_camara()
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    def _inicializar_camara(self):
        backends = [
            (cv2.CAP_DSHOW, "CAP_DSHOW"),
            (cv2.CAP_MSMF,  "CAP_MSMF"),
            (cv2.CAP_ANY,   "CAP_ANY"),
        ]
        indices = list(range(5))
        for backend, nombre in backends:
            for indice in indices:
                print(f"Cámara vivo: probando índice {indice}, backend {nombre}...")
                cap = cv2.VideoCapture(indice, backend)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.ANCHO_VIDEO)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.ALTO_VIDEO)
                    cap.set(cv2.CAP_PROP_FPS, 30)
                    self._cap = cap
                    print(f"✔ Cámara abierta: índice {indice}, backend {nombre}")
                    break
                else:
                    cap.release()
                    print(f"✘ Falló: índice {indice}, backend {nombre}")
            if self._cap is not None:
                break
        if self._cap is None or not self._cap.isOpened():
            self.lbl_info.config(text="❌ No se pudo abrir la cámara", fg=COLOR_RED)
            return
        self._activo = True
        threading.Thread(target=self._bucle_captura, daemon=True).start()
        self._actualizar_ui()

    def _bucle_captura(self):
        while self._activo:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.05)
                continue
            frame = cv2.flip(frame, 1)
            with self._lock:
                self._frame_actual = frame.copy()

    def _actualizar_ui(self):
        if not self._activo:
            return
        with self._lock:
            frame = self._frame_actual
        if frame is not None:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(rgb_frame)
            img_pil = img_pil.resize((self.ANCHO_VIDEO, self.ALTO_VIDEO))
            imgtk = ImageTk.PhotoImage(image=img_pil)
            self.canvas_video.imgtk = imgtk
            self.canvas_video.create_image(0, 0, anchor="nw", image=imgtk)
            self.lbl_info.config(text="Cámara activa", fg=COLOR_GREEN)
        if self._activo:
            self.after(33, self._actualizar_ui)

    def _cerrar(self):
        self._activo = False
        time.sleep(0.1)
        if self._cap is not None and self._cap.isOpened():
            self._cap.release()
        try:
            self.destroy()
        except tk.TclError:
            pass


# ═══════════════════════════════════════════════════════════════
#  LOGIN (sin cambios)
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
        c = conn.cursor()
        c.execute("SELECT rol FROM usuarios WHERE usuario=? AND password=?", (usuario, password))
        row = c.fetchone()
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
#  REGISTRO EXITOSO, PANEL PORTERÍA, DETALLES, ADMIN, HISTORIAL, REPORTES
#  (Se mantienen exactamente igual que en el código original, sin cambios)
#  Los omito aquí por brevedad, pero debes incluirlos tal cual.
#  ...
# ═══════════════════════════════════════════════════════════════
#  (Aquí iría el resto de clases: PantallaRegistroExitoso, PanelPorteria, 
#   DetallesRegistro, PanelAdministracion, GestionEstudiantes, 
#   FormEstudiante, ConsultaHistorial, GeneracionReportes)
#  IMPORTANTE: En FormEstudiante, cambia la captura de rostro por una 
#  captura de foto normal (opcional). Te lo detallo al final.
# ═══════════════════════════════════════════════════════════════

# Por completitud, incluyo una versión simplificada de FormEstudiante
# sin dependencia de face_recognition, usando captura de imagen simple.

class FormEstudiante(BaseWindow):
    def __init__(self, master, est_id, callback):
        super().__init__(master, "Formulario Estudiante", "440x520")
        self.est_id = est_id
        self.callback = callback
        self.foto_bytes = None  # Guardaremos la foto en JPEG
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
        # Botón de captura de foto (solo si cámara disponible)
        cam_color = COLOR_GREEN if CAMARA_DISPONIBLE else COLOR_GRAY
        cam_texto = "📸 Tomar foto" if CAMARA_DISPONIBLE else "📸 Cámara no disponible"
        self.btn_foto = make_btn(card, cam_texto, self._capturar_foto,
                                color=cam_color, width=28)
        self.btn_foto.grid(row=4, column=0, columnspan=2, pady=12)
        if not CAMARA_DISPONIBLE:
            self.btn_foto.config(state="disabled")
        if self.est_id:
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT nombre, apellido, grado, password FROM estudiantes WHERE id=?", (self.est_id,))
            row = c.fetchone()
            conn.close()
            if row:
                self.e_nombre.insert(0, row[0])
                self.e_apellido.insert(0, row[1])
                self.e_grado.insert(0, row[2])
                self.e_password.insert(0, row[3])
        make_btn(self, "Guardar", self._guardar, width=20).pack(pady=12)

    def _capturar_foto(self):
        """Toma una foto con la cámara y la guarda como JPEG en self.foto_bytes."""
        if not CAMARA_DISPONIBLE:
            messagebox.showinfo("No disponible", "Instala opencv-python y pillow")
            return
        cap = None
        backends = [
            (cv2.CAP_DSHOW, "CAP_DSHOW"),
            (cv2.CAP_MSMF,  "CAP_MSMF"),
            (cv2.CAP_ANY,   "CAP_ANY"),
        ]
        indices = list(range(5))
        for backend, nombre in backends:
            for indice in indices:
                print(f"Foto: probando índice {indice}, backend {nombre}...")
                cap_temp = cv2.VideoCapture(indice, backend)
                if cap_temp.isOpened():
                    cap = cap_temp
                    print(f"✔ Cámara foto: índice {indice}, backend {nombre}")
                    break
                else:
                    cap_temp.release()
            if cap is not None:
                break
        if cap is None or not cap.isOpened():
            messagebox.showerror("Error", "No se pudo acceder a la cámara.")
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        ventana_nom = "Presiona ESPACIO para tomar la foto, ESC para cancelar"
        foto_tomada = False
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            cv2.imshow(ventana_nom, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == 32:  # ESPACIO
                # Codificar frame como JPEG en memoria
                ret, buf = cv2.imencode('.jpg', frame)
                if ret:
                    self.foto_bytes = buf.tobytes()
                    foto_tomada = True
                break
            elif key == 27:  # ESC
                break
        cap.release()
        cv2.destroyAllWindows()
        if foto_tomada:
            self.btn_foto.config(text="✅ Foto capturada", bg=COLOR_GREEN)
            messagebox.showinfo("Éxito", "Foto tomada correctamente.")
        else:
            messagebox.showinfo("Cancelado", "No se tomó ninguna foto.")

    def _guardar(self):
        nombre   = self.e_nombre.get().strip()
        apellido = self.e_apellido.get().strip()
        grado    = self.e_grado.get().strip()
        password = self.e_password.get().strip()
        if not all([nombre, apellido, grado, password]):
            messagebox.showwarning("Campos vacíos", "Complete todos los campos.")
            return
        conn = get_connection()
        c = conn.cursor()
        if self.est_id:
            c.execute("UPDATE estudiantes SET nombre=?, apellido=?, grado=?, password=? WHERE id=?",
                      (nombre, apellido, grado, password, self.est_id))
        else:
            c.execute("INSERT INTO estudiantes (nombre, apellido, grado, password) VALUES (?,?,?,?)",
                      (nombre, apellido, grado, password))
            self.est_id = c.lastrowid
        # Guardar foto si se tomó una nueva
        if self.foto_bytes is not None:
            c.execute("DELETE FROM estudiantes_fotos WHERE estudiante_id=?", (self.est_id,))
            c.execute("INSERT INTO estudiantes_fotos (estudiante_id, foto) VALUES (?,?)",
                      (self.est_id, self.foto_bytes))
        conn.commit()
        conn.close()
        self.callback()
        self.destroy()
        messagebox.showinfo("Guardado", "Estudiante guardado correctamente.")


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
    style.configure("Treeview", background="#ffffff", foreground="#333",
                    rowheight=28, font=("Segoe UI", 10))
    style.configure("Treeview.Heading", background="#d9dde3", foreground="#333",
                    font=("Segoe UI", 11, "bold"))
    style.map("Treeview", background=[("selected", "#e8eaf6")])
    PantallaInicio(root)
    root.mainloop()

if __name__ == "__main__":
    main()