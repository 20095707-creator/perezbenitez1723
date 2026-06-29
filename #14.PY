import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
import pickle
import threading
import cv2
import face_recognition
import numpy as np
from PIL import Image, ImageTk

# ─────────────────────────────────────────
#  PANTALLA 2256x1504 → ventanas grandes
# ─────────────────────────────────────────
WIN_MAIN   = "1400x900"   # ventana principal
WIN_PANEL  = "1400x900"   # paneles portería / admin
WIN_INNER  = "1400x900"   # gestión, historial, reportes
WIN_FORM   = "540x640"    # formulario estudiante
WIN_CAMARA = "900x700"    # reconocimiento facial
WIN_CAPTU  = "680x520"    # captura rostro
WIN_EXITO  = "680x440"    # registro exitoso
WIN_LOGIN  = "480x340"    # login
WIN_DET    = "860x500"    # detalles registro

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
COLOR_PH   = "#aaaaaa"   # color placeholder fantasma

FONT_TITLE  = ("Segoe UI", 22, "bold")
FONT_HEADER = ("Segoe UI", 13, "bold")
FONT_NORMAL = ("Segoe UI", 12)
FONT_SMALL  = ("Segoe UI", 11)
FONT_BTN    = ("Segoe UI", 12, "bold")

# ─────────────────────────────────────────
#  BASE DE DATOS (SQLite)
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
            [("Juan","Pérez","5to","1234"),("María","García","6to","1234"),("Carlos","Rodríguez","5to","1234")]
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
    btn = tk.Button(parent, text=text, command=command,
                    bg=color, fg=fg, font=FONT_BTN,
                    relief="flat", cursor="hand2", padx=12, pady=8, width=width)
    btn.bind("<Enter>", lambda e: btn.config(bg=_darken(color)))
    btn.bind("<Leave>", lambda e: btn.config(bg=color))
    return btn

def _darken(hex_color):
    return {COLOR_BLUE:"#1558b0",COLOR_RED:"#b71c1c",COLOR_GREEN:"#2e7d32",COLOR_GRAY:"#424242"}.get(hex_color, hex_color)

def make_header(parent, title):
    hdr = tk.Frame(parent, bg=BG_HEADER, height=70)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    tk.Label(hdr, text=title, bg=BG_HEADER,
             font=("Segoe UI", 18, "bold"), padx=22).pack(side="left", pady=0)
    return hdr


# ─────────────────────────────────────────
#  PLACEHOLDER FANTASMA (Entry)
# ─────────────────────────────────────────
def make_ghost_entry(parent, placeholder, width=28, **kwargs):
    e = tk.Entry(parent, font=FONT_NORMAL, width=width, bd=1, relief="solid",
                 fg=COLOR_PH, **kwargs)
    e.insert(0, placeholder)
    e._placeholder = placeholder
    e._has_placeholder = True

    def on_focus_in(event):
        if e._has_placeholder:
            e.delete(0, "end")
            e.config(fg="black")
            e._has_placeholder = False

    def on_focus_out(event):
        if not e.get():
            e.insert(0, e._placeholder)
            e.config(fg=COLOR_PH)
            e._has_placeholder = True

    e.bind("<FocusIn>", on_focus_in)
    e.bind("<FocusOut>", on_focus_out)
    return e

def ghost_get(entry):
    if entry._has_placeholder:
        return ""
    return entry.get().strip()


# ─────────────────────────────────────────
#  NAVBAR FUNCIONAL
# ─────────────────────────────────────────
def make_navbar(parent, items):
    nav = tk.Frame(parent, bg="#c5cad1", height=54)
    nav.pack(fill="x")
    nav.pack_propagate(False)
    for label, cmd in items:
        btn = tk.Button(
            nav, text=label, command=cmd,
            bg="#c5cad1", fg="#1a1a1a",
            font=("Segoe UI", 13, "bold"),
            relief="flat", cursor="hand2",
            padx=28, pady=12,
            activebackground="#b0b5bc",
            activeforeground="#000000",
        )
        btn.pack(side="left")
        btn.bind("<Enter>", lambda e, b=btn: b.config(bg="#b0b5bc"))
        btn.bind("<Leave>", lambda e, b=btn: b.config(bg="#c5cad1"))
    return nav


# ─────────────────────────────────────────
#  NOTIFICACIÓN FLOTANTE
# ─────────────────────────────────────────
def mostrar_toast(master, mensaje, color=COLOR_GREEN, duracion=3000):
    root = master.winfo_toplevel()
    toast = tk.Toplevel(root)
    toast.overrideredirect(True)
    toast.attributes("-topmost", True)
    toast.configure(bg=color)
    lbl = tk.Label(toast, text=mensaje, bg=color, fg="white",
                   font=("Segoe UI", 15, "bold"), padx=34, pady=20)
    lbl.pack()
    root.update_idletasks()
    rx = root.winfo_x() + root.winfo_width()  // 2
    ry = root.winfo_y() + root.winfo_height() // 2
    toast.update_idletasks()
    tw = toast.winfo_reqwidth()
    th = toast.winfo_reqheight()
    toast.geometry(f"+{rx - tw//2}+{ry - th//2}")
    toast.after(duracion, toast.destroy)


# ─────────────────────────────────────────
#  LÓGICA DE REGISTRO
# ─────────────────────────────────────────
def realizar_registro_db(est_id, nombre, apellido, master=None):
    now   = datetime.now()
    fecha = now.strftime("%Y-%m-%d")
    hora  = now.strftime("%I:%M %p")
    conn = get_connection()
    c    = conn.cursor()
    c.execute(
        "SELECT tipo FROM registros WHERE estudiante_id=? AND fecha=? ORDER BY id DESC LIMIT 1",
        (est_id, fecha)
    )
    ultimo = c.fetchone()
    tipo = "Salida" if ultimo and ultimo[0] == "Ingreso" else "Ingreso"
    c.execute(
        "INSERT INTO registros (estudiante_id, tipo, fecha, hora, observaciones) VALUES (?,?,?,?,?)",
        (est_id, tipo, fecha, hora, "Registrado automáticamente")
    )
    conn.commit()
    conn.close()
    if master:
        color   = COLOR_GREEN if tipo == "Ingreso" else COLOR_BLUE
        emoji   = "✅" if tipo == "Ingreso" else "🚪"
        mensaje = f"{emoji}  {nombre} {apellido}  —  {tipo} registrado"
        mostrar_toast(master, mensaje, color=color, duracion=3000)
    return tipo, nombre, apellido


# ─────────────────────────────────────────
#  VENTANA BASE
# ─────────────────────────────────────────
class BaseWindow(tk.Toplevel):
    def __init__(self, master, title="RAE", size=WIN_PANEL):
        super().__init__(master)
        self.title(title)
        self.geometry(size)
        self.configure(bg=BG_MAIN)
        self.resizable(True, True)


# ═══════════════════════════════════════════════════════════════
#  CAPTURA DE ROSTRO
# ═══════════════════════════════════════════════════════════════
class CapturaRostro(BaseWindow):
    def __init__(self, master, callback):
        super().__init__(master, "Capturar Rostro", WIN_CAPTU)
        self.callback = callback
        self.capturando = True
        self.current_frame = None
        self.lock = threading.Lock()
        self.imgtk_ref = None
        self._build()

    def _build(self):
        make_header(self, "RAE – Captura de Rostro")
        self.lbl_video = tk.Label(self, bg="black")
        self.lbl_video.pack(pady=(10, 6))
        self.lbl_estado = tk.Label(self, text="Coloque su rostro frente a la cámara",
                                   bg=BG_MAIN, font=FONT_HEADER, fg=COLOR_GRAY)
        self.lbl_estado.pack(pady=4)
        btn_frame = tk.Frame(self, bg=BG_MAIN)
        btn_frame.pack(pady=10)
        make_btn(btn_frame, "📸  Capturar Rostro", self._capturar,
                 color=COLOR_GREEN, width=22).pack(side="left", padx=10)
        make_btn(btn_frame, "Cancelar", self._cancelar,
                 color=COLOR_RED, width=14).pack(side="left")
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            messagebox.showerror("Error", "No se pudo abrir la cámara.")
            self.destroy()
            return
        self.thread = threading.Thread(target=self._loop_video, daemon=True)
        self.thread.start()
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

    def _loop_video(self):
        while self.capturando:
            ret, frame = self.cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            with self.lock:
                self.current_frame = frame.copy()
            small = cv2.resize(frame, (0,0), fx=0.25, fy=0.25)
            rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            locs = face_recognition.face_locations(rgb_small, number_of_times_to_upsample=0)
            display = frame.copy()
            for (top, right, bottom, left) in locs:
                top    = int(top    / 0.25)
                right  = int(right  / 0.25)
                bottom = int(bottom / 0.25)
                left   = int(left   / 0.25)
                cv2.rectangle(display, (left, top), (right, bottom), (0,255,0), 2)
            img   = Image.fromarray(cv2.cvtColor(display, cv2.COLOR_BGR2RGB))
            imgtk = ImageTk.PhotoImage(image=img)
            try:
                self.lbl_video.after(0, self._show_frame, imgtk)
            except tk.TclError:
                break

    def _show_frame(self, imgtk):
        self.imgtk_ref = imgtk
        self.lbl_video.configure(image=imgtk)

    def _capturar(self):
        with self.lock:
            frame = self.current_frame.copy() if self.current_frame is not None else None
        if frame is None:
            messagebox.showwarning("Error", "La cámara aún no tiene imagen.")
            return
        self.lbl_estado.config(text="Procesando rostro...", fg=COLOR_BLUE)
        self.update()
        rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locs = face_recognition.face_locations(rgb, number_of_times_to_upsample=1)
        if not locs:
            self.lbl_estado.config(text="⚠ No se detectó ningún rostro.", fg=COLOR_RED)
            return
        encodings = face_recognition.face_encodings(rgb, locs, num_jitters=1)
        if not encodings:
            self.lbl_estado.config(text="⚠ No se pudo procesar el rostro.", fg=COLOR_RED)
            return
        encoding = encodings[0]
        self.lbl_estado.config(text="✅ Rostro capturado correctamente.", fg=COLOR_GREEN)
        self.update()
        messagebox.showinfo("Éxito", "Rostro capturado. Ahora pulse Guardar en el formulario.")
        self.capturando = False
        if self.cap.isOpened():
            self.cap.release()
        self.callback(encoding)
        self.destroy()

    def _cancelar(self):
        self.capturando = False
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        self.callback(None)
        self.destroy()


# ═══════════════════════════════════════════════════════════════
#  FORMULARIO DE ESTUDIANTE
# ═══════════════════════════════════════════════════════════════
class FormEstudiante(BaseWindow):
    def __init__(self, master, est_id, callback):
        super().__init__(master, "Formulario Estudiante", WIN_FORM)
        self.est_id   = est_id
        self.callback = callback
        self.face_encoding = None
        self._build()

    def _build(self):
        titulo = "Editar Estudiante" if self.est_id else "Añadir Estudiante"
        tk.Label(self, text=titulo, bg=BG_MAIN, font=FONT_TITLE).pack(pady=(24,12))
        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=28, pady=22)
        card.pack()

        def campo(label, row, show=None):
            tk.Label(card, text=label+":", bg=BG_CARD, font=FONT_NORMAL).grid(row=row, column=0, sticky="w", pady=6)
            e = tk.Entry(card, font=FONT_NORMAL, width=24, bd=1, relief="solid", show=show)
            e.grid(row=row, column=1, padx=(10,0), pady=6, ipady=6)
            return e

        self.e_nombre   = campo("Nombre",    0)
        self.e_apellido = campo("Apellido",  1)
        self.e_grado    = campo("Grado",     2)
        self.e_password = campo("Contraseña",3, show="*")

        self.btn_capturar = tk.Button(
            card, text="📸  Capturar Rostro",
            command=self._abrir_captura,
            bg=COLOR_GRAY, fg="white", font=FONT_BTN,
            relief="flat", cursor="hand2", padx=12, pady=8, width=24
        )
        self.btn_capturar.grid(row=4, column=0, columnspan=2, pady=16)

        self.lbl_rostro = tk.Label(card, text="Sin rostro capturado",
                                   bg=BG_CARD, font=FONT_SMALL, fg=COLOR_GRAY)
        self.lbl_rostro.grid(row=5, column=0, columnspan=2)

        if self.est_id:
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT nombre, apellido, grado, password FROM estudiantes WHERE id=?", (self.est_id,))
            row = c.fetchone()
            c.execute("SELECT COUNT(*) FROM estudiantes_faces WHERE estudiante_id=?", (self.est_id,))
            tiene_rostro = c.fetchone()[0] > 0
            conn.close()
            if row:
                self.e_nombre.insert(0, row[0])
                self.e_apellido.insert(0, row[1])
                self.e_grado.insert(0, row[2])
                self.e_password.insert(0, row[3])
            if tiene_rostro:
                self.lbl_rostro.config(text="✅ Rostro ya registrado en BD", fg=COLOR_GREEN)
                self.btn_capturar.config(text="📸  Actualizar Rostro")

        make_btn(self, "💾  Guardar Estudiante", self._guardar, width=26).pack(pady=16)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _abrir_captura(self):
        self.btn_capturar.config(state="disabled", text="Cámara abierta...")
        CapturaRostro(self, self._recibir_encoding)

    def _recibir_encoding(self, encoding):
        self.btn_capturar.config(state="normal")
        if encoding is not None:
            self.face_encoding = encoding
            self.btn_capturar.config(text="✅ Rostro listo — Pulse Guardar", bg=COLOR_GREEN)
            self.lbl_rostro.config(text=f"Encoding: {len(encoding)} valores — listo para guardar", fg=COLOR_GREEN)
        else:
            self.btn_capturar.config(text="📸  Capturar Rostro", bg=COLOR_GRAY)
            self.lbl_rostro.config(text="Captura cancelada", fg=COLOR_RED)

    def _guardar(self):
        nombre   = self.e_nombre.get().strip()
        apellido = self.e_apellido.get().strip()
        grado    = self.e_grado.get().strip()
        password = self.e_password.get().strip()
        if not nombre or not apellido or not grado or not password:
            messagebox.showwarning("Campos vacíos", "Complete todos los campos.")
            return
        conn = get_connection()
        c = conn.cursor()
        try:
            if self.est_id:
                c.execute(
                    "UPDATE estudiantes SET nombre=?, apellido=?, grado=?, password=? WHERE id=?",
                    (nombre, apellido, grado, password, self.est_id)
                )
                id_guardado = self.est_id
            else:
                c.execute(
                    "INSERT INTO estudiantes (nombre, apellido, grado, password) VALUES (?,?,?,?)",
                    (nombre, apellido, grado, password)
                )
                id_guardado = c.lastrowid
                self.est_id = id_guardado
            rostro_msg = ""
            if self.face_encoding is not None:
                if not isinstance(self.face_encoding, np.ndarray):
                    raise ValueError("El encoding no es válido.")
                blob = pickle.dumps(self.face_encoding)
                c.execute("DELETE FROM estudiantes_faces WHERE estudiante_id=?", (id_guardado,))
                c.execute("INSERT INTO estudiantes_faces (estudiante_id, encoding) VALUES (?,?)", (id_guardado, blob))
                rostro_msg = "\n✅ Rostro facial guardado correctamente."
            conn.commit()
            messagebox.showinfo("Guardado", f"Estudiante guardado.{rostro_msg}")
            self.face_encoding = None
            self.callback()
            self.destroy()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error al guardar", f"No se pudo guardar:\n{e}")
        finally:
            conn.close()

    def _on_close(self):
        if self.face_encoding is not None:
            if not messagebox.askyesno("Rostro no guardado",
                                       "Capturaste un rostro pero no lo guardaste. ¿Cerrar de todos modos?"):
                return
        self.destroy()


# ═══════════════════════════════════════════════════════════════
#  VENTANA RECONOCIMIENTO FACIAL
# ═══════════════════════════════════════════════════════════════
class VentanaCamaraReconocimiento(BaseWindow):
    FRAMES_CONFIRMACION = 8

    def __init__(self, master, callback_registro):
        super().__init__(master, "Reconocimiento Facial", WIN_CAMARA)
        self.callback_registro = callback_registro
        self.capturando        = True
        self.rostro_reconocido = None
        self.imgtk_ref         = None
        self._frames_confirm   = 0
        self._registrando      = False
        self._build()

    def _build(self):
        make_header(self, "RAE – Identificación por Cámara")
        self.lbl_video = tk.Label(self, bg="black")
        self.lbl_video.pack(padx=12, pady=(12,6))
        self.lbl_info = tk.Label(self, text="🔍 Buscando rostro...",
                                 bg=BG_MAIN, font=FONT_HEADER, fg=COLOR_GRAY)
        self.lbl_info.pack(pady=4)
        prog_frame = tk.Frame(self, bg=BG_MAIN)
        prog_frame.pack(pady=6)
        tk.Label(prog_frame, text="Confirmando:", bg=BG_MAIN, font=FONT_SMALL,
                 fg=COLOR_GRAY).pack(side="left", padx=(0,8))
        self.progress = ttk.Progressbar(prog_frame, length=320, maximum=self.FRAMES_CONFIRMACION,
                                        mode="determinate")
        self.progress.pack(side="left")
        make_btn(self, "✔ Confirmar manualmente", self._confirmar_manual,
                 color=COLOR_GRAY, width=26).pack(pady=8)
        tk.Label(self, text="El sistema registrará automáticamente al reconocer el rostro.",
                 bg=BG_MAIN, font=FONT_SMALL, fg=COLOR_GRAY).pack()
        self.known_encodings, self.known_ids, self.known_names = self._cargar_codificaciones()
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            raise Exception("No se pudo abrir la cámara.")
        self.thread = threading.Thread(target=self._loop_video, daemon=True)
        self.thread.start()
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    def _cargar_codificaciones(self):
        encodings, ids, names = [], [], []
        conn = get_connection()
        c = conn.cursor()
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
                names.append(nombre)
            except:
                pass
        conn.close()
        return encodings, ids, names

    def _loop_video(self):
        scale = 0.25
        face_locs = []
        nombre_disp = "Desconocido"
        color = (0, 0, 255)
        frame_count = 0
        while self.capturando:
            ret, frame = self.cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            if frame_count % 3 == 0:
                small     = cv2.resize(frame, (0,0), fx=scale, fy=scale)
                rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                locs      = face_recognition.face_locations(rgb_small, number_of_times_to_upsample=0)
                encs      = face_recognition.face_encodings(rgb_small, locs, num_jitters=0)
                self.rostro_reconocido = None
                nombre_disp = "Desconocido"
                color = (0, 0, 255)
                for enc in encs:
                    if self.known_encodings:
                        matches = face_recognition.compare_faces(self.known_encodings, enc, tolerance=0.5)
                        if True in matches:
                            idx = matches.index(True)
                            nombre_disp = self.known_names[idx]
                            self.rostro_reconocido = (self.known_ids[idx], self.known_names[idx])
                            color = (0, 255, 0)
                            break
                face_locs = []
                for (top, right, bottom, left) in locs:
                    face_locs.append((int(top/scale), int(right/scale), int(bottom/scale), int(left/scale)))
                if self.rostro_reconocido:
                    self._frames_confirm = min(self._frames_confirm + 1, self.FRAMES_CONFIRMACION)
                else:
                    self._frames_confirm = 0
                if self._frames_confirm >= self.FRAMES_CONFIRMACION and not self._registrando:
                    self._registrando = True
                    self.after(0, self._auto_registrar)
            for (top, right, bottom, left) in face_locs:
                cv2.rectangle(frame, (left,top), (right,bottom), color, 2)
                cv2.putText(frame, nombre_disp, (left, top-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            img   = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            imgtk = ImageTk.PhotoImage(image=img)
            try:
                self.lbl_video.after(0, self._update_video, imgtk)
                n = self._frames_confirm
                if self.rostro_reconocido:
                    self.lbl_info.after(0, lambda nm=nombre_disp: self.lbl_info.config(
                        text=f"✅ Reconocido: {nm}", fg=COLOR_GREEN))
                else:
                    self.lbl_info.after(0, lambda: self.lbl_info.config(
                        text="🔍 Buscando rostro...", fg=COLOR_GRAY))
                self.progress.after(0, lambda v=n: self.progress.config(value=v))
            except tk.TclError:
                break
            frame_count += 1

    def _update_video(self, imgtk):
        self.imgtk_ref = imgtk
        self.lbl_video.configure(image=imgtk)

    def _auto_registrar(self):
        if not self.rostro_reconocido:
            self._registrando = False
            return
        est_id, nombre = self.rostro_reconocido
        partes = nombre.split(" ", 1)
        nom = partes[0]
        ape = partes[1] if len(partes) > 1 else ""
        self._cerrar()
        realizar_registro_db(est_id, nom, ape, master=self.master)
        self.callback_registro(est_id, nom, ape)

    def _confirmar_manual(self):
        if self.rostro_reconocido:
            est_id, nombre = self.rostro_reconocido
            partes = nombre.split(" ", 1)
            nom = partes[0]
            ape = partes[1] if len(partes) > 1 else ""
            self._cerrar()
            realizar_registro_db(est_id, nom, ape, master=self.master)
            self.callback_registro(est_id, nom, ape)
        else:
            messagebox.showwarning("Sin reconocimiento",
                                   "Acérquese a la cámara o no se ha reconocido ningún rostro.")

    def _cerrar(self):
        self.capturando = False
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        try:
            self.destroy()
        except tk.TclError:
            pass


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
                 bg=BG_HEADER, font=("Segoe UI",13,"bold"), padx=20).pack(side="left", pady=14)

        tk.Label(self, text="Registro de Ingreso / Salida",
                 bg=BG_MAIN, font=FONT_TITLE).pack(pady=(50,24))

        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=50, pady=38)
        card.pack(ipadx=20)
        tk.Label(card, text="Ingresar Datos Manualmente", bg=BG_CARD, font=FONT_HEADER).pack(pady=(0,16))

        self.entry_id = tk.Entry(card, font=FONT_NORMAL, width=36, bd=1, relief="solid", fg=COLOR_GRAY)
        self.entry_id.insert(0, "Número de Identificación")
        self.entry_id.bind("<FocusIn>",  self._clear_placeholder)
        self.entry_id.bind("<FocusOut>", self._restore_placeholder)
        self.entry_id.pack(pady=(0,18), ipady=10)

        make_btn(card, "Registrar", self._registrar, width=34).pack()
        make_btn(card, "🔍 Identificación por cámara", self._abrir_camara,
                 color=COLOR_GREEN, width=34).pack(pady=12)

        icons_frame = tk.Frame(self, bg=BG_MAIN)
        icons_frame.pack(pady=50)
        self._make_icon(icons_frame, "👤","Acceso personal\nportería", COLOR_GREEN, self._login_porteria)
        self._make_icon(icons_frame, "👥","Acceso\nadministrador/director", "#7c4dff", self._login_admin)

    def _make_icon(self, parent, symbol, label, color, command):
        frame = tk.Frame(parent, bg=BG_MAIN)
        frame.pack(side="left", padx=30)
        tk.Button(frame, text=symbol, font=("Segoe UI",26), bg=color, fg="white",
                  width=3, height=1, relief="flat", cursor="hand2", command=command).pack()
        tk.Label(frame, text=label, bg=BG_MAIN, font=FONT_SMALL, fg=COLOR_GRAY, justify="center").pack(pady=6)

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
        tipo, nom, ape = realizar_registro_db(est_id, nombre, apellido, master=self)
        PantallaRegistroExitoso(self.winfo_toplevel(), nom, ape, tipo)

    def _abrir_camara(self):
        try:
            VentanaCamaraReconocimiento(self.winfo_toplevel(), self._after_camara)
        except Exception as e:
            messagebox.showerror("Error de cámara", f"No se pudo iniciar la cámara: {e}")

    def _after_camara(self, est_id, nombre, apellido):
        conn = get_connection()
        c = conn.cursor()
        fecha = datetime.now().strftime("%Y-%m-%d")
        c.execute(
            "SELECT tipo FROM registros WHERE estudiante_id=? AND fecha=? ORDER BY id DESC LIMIT 1",
            (est_id, fecha)
        )
        row  = c.fetchone()
        conn.close()
        tipo = row[0] if row else "Ingreso"
        PantallaRegistroExitoso(self.winfo_toplevel(), nombre, apellido, tipo)

    def _login_porteria(self):
        LoginWindow(self.winfo_toplevel(), "porteria")

    def _login_admin(self):
        LoginWindow(self.winfo_toplevel(), "admin")


# ═══════════════════════════════════════════════════════════════
#  PANTALLA REGISTRO EXITOSO
# ═══════════════════════════════════════════════════════════════
class PantallaRegistroExitoso(BaseWindow):
    SEGUNDOS = 3

    def __init__(self, master, nombre, apellido, tipo):
        super().__init__(master, "Registro Exitoso", WIN_EXITO)
        self._segundos_restantes = self.SEGUNDOS
        make_header(self, "RAE")

        color_tipo = COLOR_GREEN if tipo == "Ingreso" else COLOR_BLUE
        emoji_tipo = "✅" if tipo == "Ingreso" else "🚪"

        tk.Label(self, text=emoji_tipo, font=("Segoe UI", 64),
                 bg=BG_MAIN, fg=color_tipo).pack(pady=(34, 6))
        tk.Label(self, text="¡Registro Exitoso!", bg=BG_MAIN,
                 font=("Segoe UI", 20, "bold")).pack()

        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=36, pady=22)
        card.pack(pady=20)
        tk.Label(card, text=f"Tu {tipo.lower()} ha sido registrado correctamente.",
                 bg=BG_CARD, font=FONT_NORMAL, fg=COLOR_GRAY).pack()
        tk.Label(card, text=f"Estudiante: {nombre} {apellido}",
                 bg=BG_CARD, font=FONT_HEADER).pack(pady=(10, 0))

        self.btn_cerrar = make_btn(
            self, f"Cerrar  ({self.SEGUNDOS})",
            self.destroy, color=COLOR_GRAY, width=22
        )
        self.btn_cerrar.pack(pady=12)
        self.after(1000, self._tick)

    def _tick(self):
        if not self.winfo_exists():
            return
        self._segundos_restantes -= 1
        if self._segundos_restantes <= 0:
            try:
                self.destroy()
            except tk.TclError:
                pass
        else:
            try:
                self.btn_cerrar.config(text=f"Cerrar  ({self._segundos_restantes})")
                self.after(1000, self._tick)
            except tk.TclError:
                pass


# ═══════════════════════════════════════════════════════════════
#  LOGIN
# ═══════════════════════════════════════════════════════════════
class LoginWindow(BaseWindow):
    def __init__(self, master, rol_esperado):
        super().__init__(master, "Iniciar sesión", WIN_LOGIN)
        self.rol_esperado = rol_esperado
        self._build()

    def _build(self):
        tk.Label(self, text="Iniciar Sesión", bg=BG_MAIN, font=FONT_TITLE).pack(pady=(36,24))
        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=36, pady=24)
        card.pack()
        tk.Label(card, text="Usuario:", bg=BG_CARD, font=FONT_NORMAL).pack(anchor="w")
        self.e_user = tk.Entry(card, font=FONT_NORMAL, width=32, bd=1, relief="solid")
        self.e_user.pack(pady=(4,12), ipady=7)
        tk.Label(card, text="Contraseña:", bg=BG_CARD, font=FONT_NORMAL).pack(anchor="w")
        self.e_pass = tk.Entry(card, font=FONT_NORMAL, width=32, show="*", bd=1, relief="solid")
        self.e_pass.pack(pady=(4,16), ipady=7)
        make_btn(card, "Entrar", self._login, width=32).pack()

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
        self.master.withdraw()
        self.destroy()
        if rol == "porteria":
            open_new_window(self.master, PanelPorteria, root=self.master)
        else:
            open_new_window(self.master, PanelAdministracion, root=self.master)


def open_new_window(master, cls, root=None):
    win = tk.Toplevel(master)
    win.geometry(WIN_PANEL)
    win.configure(bg=BG_MAIN)
    win.title("RAE")
    def on_close():
        if root:
            root.deiconify()
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", on_close)
    cls(win, root=root, close_callback=on_close)


def open_inner_window(master, cls, root=None, close_callback=None):
    win = tk.Toplevel(master)
    win.geometry(WIN_INNER)
    win.configure(bg=BG_MAIN)
    win.title("RAE")
    def on_close():
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", on_close)
    cls(win, root=root, close_callback=on_close)


# ═══════════════════════════════════════════════════════════════
#  PANEL PORTERÍA — vista consolidada (una fila por estudiante)
# ═══════════════════════════════════════════════════════════════
class PanelPorteria(tk.Frame):
    def __init__(self, master, root=None, close_callback=None):
        super().__init__(master, bg=BG_MAIN)
        self.root = root
        self.close_callback = close_callback
        self.pack(fill="both", expand=True)
        self._build()
        self._auto_refresh()

    def _build(self):
        make_header(self, "RAE")
        make_navbar(self, [
            ("Inicio",        self._ir_inicio),
            ("Monitoreo",     self._refresh),
            ("Cerrar sesión", self._logout)
        ])

        top = tk.Frame(self, bg=BG_MAIN)
        top.pack(fill="x", padx=24, pady=(14,6))
        tk.Label(top, text="Panel de Monitoreo (Personal de Portería)",
                 bg=BG_MAIN, font=FONT_TITLE).pack(side="left")
        make_btn(top, "🔄 Actualizar", self._refresh, color=COLOR_GRAY, width=16).pack(side="right")

        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=18, pady=18)
        card.pack(fill="both", expand=True, padx=24, pady=(0,24))
        tk.Label(card, text="Estado actual de estudiantes — hoy",
                 bg=BG_CARD, font=FONT_HEADER).pack(anchor="w", pady=(0,10))

        cols = ("Estudiante", "Última Entrada", "Última Salida", "Estado")
        self.tree = ttk.Treeview(card, columns=cols, show="headings", height=18)
        widths = {"Estudiante": 380, "Última Entrada": 200, "Última Salida": 200, "Estado": 180}
        anchors = {"Estudiante": "w", "Última Entrada": "center", "Última Salida": "center", "Estado": "center"}
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[col], anchor=anchors[col])

        sb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._refresh()

    def _refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT e.id, e.nombre||' '||e.apellido,
                   MAX(CASE WHEN r.tipo='Ingreso' THEN r.hora END) AS ultima_entrada,
                   MAX(CASE WHEN r.tipo='Salida'  THEN r.hora END) AS ultima_salida
            FROM estudiantes e
            LEFT JOIN registros r ON r.estudiante_id = e.id AND r.fecha = ?
            GROUP BY e.id, e.nombre, e.apellido
            ORDER BY e.nombre
        """, (fecha_hoy,))
        for est_id, nombre, entrada, salida in c.fetchall():
            entrada_txt = entrada if entrada else "—"
            salida_txt  = salida  if salida  else "—"
            c2 = conn.cursor()
            c2.execute("""
                SELECT tipo FROM registros
                WHERE estudiante_id=? AND fecha=?
                ORDER BY id DESC LIMIT 1
            """, (est_id, fecha_hoy))
            ultimo = c2.fetchone()
            if not ultimo or ultimo[0] is None:
                estado = "Sin registro"
                tag = "sin"
            elif ultimo[0] == "Ingreso":
                estado = "✅ Dentro"
                tag = "dentro"
            else:
                estado = "🚪 Salió"
                tag = "fuera"
            self.tree.insert("", "end", values=(nombre, entrada_txt, salida_txt, estado), tags=(tag,))
        conn.close()
        self.tree.tag_configure("dentro", foreground=COLOR_GREEN)
        self.tree.tag_configure("fuera",  foreground=COLOR_BLUE)
        self.tree.tag_configure("sin",    foreground=COLOR_GRAY)

    def _auto_refresh(self):
        try:
            self._refresh()
            self.after(5000, self._auto_refresh)
        except tk.TclError:
            pass

    def _ir_inicio(self):
        self._logout()

    def _logout(self):
        if self.close_callback:
            self.close_callback()
        else:
            self.winfo_toplevel().destroy()
            if self.root:
                self.root.deiconify()


# ═══════════════════════════════════════════════════════════════
#  DETALLES DE REGISTRO
# ═══════════════════════════════════════════════════════════════
class DetallesRegistro(BaseWindow):
    def __init__(self, master, reg_id):
        super().__init__(master, "Detalles de Registro", WIN_DET)
        make_header(self, "RAE")
        tk.Label(self, text="Detalles de Registro", bg=BG_MAIN, font=FONT_TITLE).pack(anchor="w", padx=24, pady=14)
        conn = get_connection()
        c = conn.cursor()
        c.execute("""SELECT e.nombre||' '||e.apellido, e.id, r.tipo,
                            r.fecha||' '||r.hora, r.observaciones, r.registrado_por
                     FROM registros r JOIN estudiantes e ON r.estudiante_id=e.id WHERE r.id=?""", (reg_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            tk.Label(self, text="Registro no encontrado.", bg=BG_MAIN, font=FONT_NORMAL).pack(pady=50)
            return
        nombre, est_id, tipo, fecha_hora, obs, reg_por = row
        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=34, pady=28)
        card.pack(fill="x", padx=24)
        def field(lbl, val, r, col):
            tk.Label(card, text=lbl+":", bg=BG_CARD, font=FONT_HEADER).grid(row=r, column=col*2, sticky="w", pady=6, padx=(0,10))
            tk.Label(card, text=val, bg=BG_CARD, font=FONT_NORMAL, fg=COLOR_GRAY).grid(row=r+1, column=col*2, sticky="w")
        field("Estudiante", nombre, 0, 0)
        field("ID Estudiante", str(est_id), 0, 1)
        field("Tipo de Registro", tipo, 2, 0)
        field("Fecha y Hora", fecha_hora, 2, 1)
        tk.Label(card, text="Observaciones:", bg=BG_CARD, font=FONT_HEADER).grid(row=4,column=0,sticky="w",pady=(14,0))
        tk.Label(card, text=obs or "—", bg=BG_CARD, font=FONT_NORMAL, fg=COLOR_GRAY).grid(row=5,column=0,sticky="w")
        make_btn(self, "Volver al Monitoreo", self.destroy, width=24).pack(anchor="w", padx=24, pady=18)


# ═══════════════════════════════════════════════════════════════
#  PANEL ADMINISTRACIÓN
# ═══════════════════════════════════════════════════════════════
class PanelAdministracion(tk.Frame):
    def __init__(self, master, root=None, close_callback=None):
        super().__init__(master, bg=BG_MAIN)
        self.root = root
        self.close_callback = close_callback
        self._master_win = master
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        make_header(self, "RAE")
        make_navbar(self, [
            ("Inicio",        self._ir_inicio),
            ("Monitoreo",     self._ir_monitoreo),
            ("Cerrar sesión", self._logout)
        ])
        tk.Label(self, text="Panel de Administración", bg=BG_MAIN, font=FONT_TITLE).pack(pady=(36,24))
        cards_frame = tk.Frame(self, bg=BG_MAIN)
        cards_frame.pack()
        for icon, label, cmd in [
            ("👥","Gestionar estudiantes", self._gestionar_estudiantes),
            ("🕐","Consultar historial",   self._consultar_historial),
        ]:
            f = tk.Frame(cards_frame, bg=BG_CARD, bd=1, relief="solid", padx=36, pady=36)
            f.pack(side="left", padx=20, ipadx=12)
            tk.Label(f, text=icon, font=("Segoe UI",38), bg=BG_CARD, fg=COLOR_BLUE).pack(pady=(0,10))
            tk.Label(f, text=label, bg=BG_CARD, font=FONT_HEADER).pack(pady=(0,16))
            make_btn(f, "Ir", cmd, width=10).pack()

    def _ir_inicio(self):
        self._logout()

    def _ir_monitoreo(self):
        open_inner_window(self._master_win, _MonitoreoAdmin, root=self.root)

    def _gestionar_estudiantes(self):
        open_inner_window(self._master_win, GestionEstudiantes, root=self.root)

    def _consultar_historial(self):
        open_inner_window(self._master_win, ConsultaHistorial, root=self.root)

    def _logout(self):
        if self.close_callback:
            self.close_callback()
        else:
            self.winfo_toplevel().destroy()
            if self.root:
                self.root.deiconify()


# ═══════════════════════════════════════════════════════════════
#  MONITOREO (accesible desde navbar del admin) — vista consolidada
# ═══════════════════════════════════════════════════════════════
class _MonitoreoAdmin(tk.Frame):
    def __init__(self, master, root=None, close_callback=None):
        super().__init__(master, bg=BG_MAIN)
        self.root = root
        self.close_callback = close_callback
        self.pack(fill="both", expand=True)
        self._build()
        self._auto_refresh()

    def _build(self):
        make_header(self, "RAE")
        make_navbar(self, [
            ("Volver", self._volver),
            ("🔄 Actualizar", self._refresh),
        ])
        top = tk.Frame(self, bg=BG_MAIN)
        top.pack(fill="x", padx=24, pady=(14,6))
        tk.Label(top, text="Monitoreo de Estudiantes — Hoy",
                 bg=BG_MAIN, font=FONT_TITLE).pack(side="left")
        make_btn(top, "🔄 Actualizar", self._refresh, color=COLOR_GRAY, width=16).pack(side="right")

        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=18, pady=18)
        card.pack(fill="both", expand=True, padx=24, pady=(0,24))
        tk.Label(card, text="Estado actual de estudiantes — hoy",
                 bg=BG_CARD, font=FONT_HEADER).pack(anchor="w", pady=(0,10))

        cols = ("Estudiante", "Última Entrada", "Última Salida", "Estado")
        self.tree = ttk.Treeview(card, columns=cols, show="headings", height=18)
        widths = {"Estudiante": 380, "Última Entrada": 200, "Última Salida": 200, "Estado": 180}
        anchors = {"Estudiante": "w", "Última Entrada": "center", "Última Salida": "center", "Estado": "center"}
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[col], anchor=anchors[col])
        sb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._refresh()

    def _refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        conn = get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT e.id, e.nombre||' '||e.apellido,
                   MAX(CASE WHEN r.tipo='Ingreso' THEN r.hora END) AS ultima_entrada,
                   MAX(CASE WHEN r.tipo='Salida'  THEN r.hora END) AS ultima_salida
            FROM estudiantes e
            LEFT JOIN registros r ON r.estudiante_id = e.id AND r.fecha = ?
            GROUP BY e.id, e.nombre, e.apellido
            ORDER BY e.nombre
        """, (fecha_hoy,))
        for est_id, nombre, entrada, salida in c.fetchall():
            entrada_txt = entrada if entrada else "—"
            salida_txt  = salida  if salida  else "—"
            c2 = conn.cursor()
            c2.execute("""
                SELECT tipo FROM registros
                WHERE estudiante_id=? AND fecha=?
                ORDER BY id DESC LIMIT 1
            """, (est_id, fecha_hoy))
            ultimo = c2.fetchone()
            if not ultimo or ultimo[0] is None:
                estado = "Sin registro"
                tag = "sin"
            elif ultimo[0] == "Ingreso":
                estado = "✅ Dentro"
                tag = "dentro"
            else:
                estado = "🚪 Salió"
                tag = "fuera"
            self.tree.insert("", "end", values=(nombre, entrada_txt, salida_txt, estado), tags=(tag,))
        conn.close()
        self.tree.tag_configure("dentro", foreground=COLOR_GREEN)
        self.tree.tag_configure("fuera",  foreground=COLOR_BLUE)
        self.tree.tag_configure("sin",    foreground=COLOR_GRAY)

    def _auto_refresh(self):
        try:
            self._refresh()
            self.after(5000, self._auto_refresh)
        except tk.TclError:
            pass

    def _volver(self):
        self.winfo_toplevel().destroy()


# ═══════════════════════════════════════════════════════════════
#  GESTIÓN DE ESTUDIANTES
# ═══════════════════════════════════════════════════════════════
class GestionEstudiantes(tk.Frame):
    def __init__(self, master, root=None, close_callback=None):
        super().__init__(master, bg=BG_MAIN)
        self.root = root
        self.close_callback = close_callback
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        make_header(self, "RAE")
        make_navbar(self, [
            ("Inicio",         self._ir_inicio),
            ("Monitoreo",      self._ir_monitoreo),
            ("Administración", self._ir_admin),
        ])
        top = tk.Frame(self, bg=BG_MAIN)
        top.pack(fill="x", padx=24, pady=12)
        tk.Label(top, text="Gestión de Estudiantes", bg=BG_MAIN, font=FONT_TITLE).pack(side="left")
        make_btn(top, "Volver al panel", self.winfo_toplevel().destroy, width=18).pack(side="right")

        btn_row = tk.Frame(self, bg=BG_MAIN)
        btn_row.pack(anchor="w", padx=24, pady=(0,12))
        make_btn(btn_row, "Añadir Estudiante",   self._añadir,   width=20).pack(side="left", padx=4)
        make_btn(btn_row, "Editar Estudiante",   self._editar,   color=COLOR_GRAY, width=20).pack(side="left", padx=4)
        make_btn(btn_row, "Eliminar Estudiante", self._eliminar, color=COLOR_RED,  width=20).pack(side="left", padx=4)

        search_card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=16, pady=12)
        search_card.pack(fill="x", padx=24, pady=(0,12))
        tk.Label(search_card, text="Buscar Estudiante", bg=BG_CARD, font=FONT_HEADER).pack(anchor="w")
        self.e_buscar = tk.Entry(search_card, font=FONT_NORMAL, width=70, bd=1, relief="solid")
        self.e_buscar.pack(anchor="w", pady=(6,10), ipady=7)
        self.e_buscar.insert(0, "Buscar por nombre o ID")
        make_btn(search_card, "Buscar", self._buscar, width=12).pack(anchor="w")

        cols = ("ID","Nombre","Apellido","Grado","Rostro")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        widths = {"ID":80,"Nombre":280,"Apellido":280,"Grado":130,"Rostro":150}
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[col])

        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(24,0), pady=(0,18))
        sb.pack(side="left", fill="y", pady=(0,18), padx=(0,24))
        self._cargar_todos()

    def _cargar_todos(self, filtro=""):
        for row in self.tree.get_children():
            self.tree.delete(row)
        conn = get_connection()
        c = conn.cursor()
        query = """
            SELECT e.id, e.nombre, e.apellido, e.grado,
                   CASE WHEN f.id IS NOT NULL THEN '✅ Sí' ELSE '❌ No' END
            FROM estudiantes e
            LEFT JOIN estudiantes_faces f ON e.id = f.estudiante_id
        """
        params = []
        if filtro:
            query += " WHERE e.nombre LIKE ? OR e.apellido LIKE ? OR CAST(e.id AS TEXT) LIKE ?"
            params = [f"%{filtro}%", f"%{filtro}%", f"%{filtro}%"]
        c.execute(query, params)
        for row in c.fetchall():
            self.tree.insert("","end", iid=row[0], values=row)
        conn.close()

    def _buscar(self):
        q = self.e_buscar.get().strip()
        self._cargar_todos("" if q == "Buscar por nombre o ID" else q)

    def _get_selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Seleccione","Seleccione un estudiante de la lista.")
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
        if messagebox.askyesno("Confirmar","¿Eliminar este estudiante y sus registros?"):
            conn = get_connection()
            c = conn.cursor()
            c.execute("DELETE FROM registros WHERE estudiante_id=?", (est_id,))
            c.execute("DELETE FROM estudiantes_faces WHERE estudiante_id=?", (est_id,))
            c.execute("DELETE FROM estudiantes WHERE id=?", (est_id,))
            conn.commit()
            conn.close()
            self._cargar_todos()
            messagebox.showinfo("Listo","Estudiante eliminado.")

    def _ir_inicio(self):
        self.winfo_toplevel().destroy()

    def _ir_monitoreo(self):
        open_inner_window(self.winfo_toplevel(), _MonitoreoAdmin)

    def _ir_admin(self):
        self.winfo_toplevel().destroy()


# ═══════════════════════════════════════════════════════════════
#  CONSULTA HISTORIAL — MUESTRA TODOS LOS MOVIMIENTOS INDIVIDUALES
#  (cada fila = un registro de ingreso o salida, sin consolidar)
# ═══════════════════════════════════════════════════════════════
class ConsultaHistorial(tk.Frame):
    def __init__(self, master, root=None, close_callback=None):
        super().__init__(master, bg=BG_MAIN)
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        make_header(self, "RAE")
        make_navbar(self, [
            ("Inicio",         self._ir_inicio),
            ("Monitoreo",      self._ir_monitoreo),
            ("Administración", self._ir_admin),
        ])
        top = tk.Frame(self, bg=BG_MAIN)
        top.pack(fill="x", padx=24, pady=12)
        tk.Label(top, text="Consulta de Historial (todos los movimientos)",
                 bg=BG_MAIN, font=FONT_TITLE).pack(side="left")
        make_btn(top, "Volver al panel", self.winfo_toplevel().destroy, width=18).pack(side="right")

        filt = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=18, pady=16)
        filt.pack(fill="x", padx=24, pady=(0,12))

        left = tk.Frame(filt, bg=BG_CARD)
        left.pack(side="left", padx=(0,24))
        tk.Label(left, text="Buscar por Nombre:", bg=BG_CARD, font=FONT_NORMAL).pack(anchor="w")
        self.e_nombre = make_ghost_entry(left, "Ej. Juan Pérez", width=34)
        self.e_nombre.pack(pady=6, ipady=7)

        right = tk.Frame(filt, bg=BG_CARD)
        right.pack(side="left")
        tk.Label(right, text="Fecha (AAAA-MM-DD) — opcional:", bg=BG_CARD, font=FONT_NORMAL).pack(anchor="w")
        self.e_fecha = make_ghost_entry(right, "2026-06-25", width=26)
        self.e_fecha.pack(pady=6, ipady=7)

        tk.Label(filt, text="(Sin fecha = todo el historial)",
                 bg=BG_CARD, font=("Segoe UI", 10), fg=COLOR_GRAY).pack(side="left", padx=20)

        make_btn(filt, "Buscar", self._buscar, width=12).pack(side="left", padx=20, pady=16)

        # Botón eliminar registro seleccionado (ahora elimina UN registro individual)
        make_btn(filt, "🗑 Eliminar registro", self._eliminar_registro,
                 color=COLOR_RED, width=18).pack(side="left", padx=8, pady=16)

        res = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=18, pady=16)
        res.pack(fill="both", expand=True, padx=24, pady=(0,18))
        tk.Label(res, text="Historial detallado — cada fila es un movimiento (ingreso o salida)",
                 bg=BG_CARD, font=FONT_HEADER).pack(anchor="w", pady=(0,10))

        # Columnas: ahora mostramos cada registro individual
        cols = ("ID", "Estudiante", "Fecha", "Hora", "Tipo")
        self.tree = ttk.Treeview(res, columns=cols, show="headings", height=16)
        widths = {"ID": 70, "Estudiante": 340, "Fecha": 160, "Hora": 150, "Tipo": 140}
        anchors = {"ID": "center", "Estudiante": "w", "Fecha": "center",
                   "Hora": "center", "Tipo": "center"}
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[col], anchor=anchors[col])

        sb = ttk.Scrollbar(res, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # Etiquetas para colorear según tipo
        self.tree.tag_configure("Ingreso", foreground=COLOR_GREEN)
        self.tree.tag_configure("Salida",  foreground=COLOR_BLUE)

        self._buscar()

    def _buscar(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        nombre = ghost_get(self.e_nombre)
        fecha  = ghost_get(self.e_fecha)

        conn = get_connection()
        c = conn.cursor()
        # Consulta SIN GROUP BY: cada registro es una fila
        q = """
            SELECT r.id, e.nombre||' '||e.apellido, r.fecha, r.hora, r.tipo
            FROM registros r
            JOIN estudiantes e ON r.estudiante_id = e.id
            WHERE 1=1
        """
        params = []
        if nombre:
            q += " AND (e.nombre LIKE ? OR e.apellido LIKE ?)"
            params += [f"%{nombre}%", f"%{nombre}%"]
        if fecha:
            q += " AND r.fecha = ?"
            params.append(fecha)
        # Ordenar por fecha descendente, luego hora descendente (más reciente primero)
        q += " ORDER BY r.fecha DESC, r.hora DESC"
        c.execute(q, params)
        rows = c.fetchall()
        conn.close()

        for reg_id, nombre_est, fch, hora, tipo in rows:
            self.tree.insert("", "end",
                             values=(reg_id, nombre_est, fch, hora, tipo),
                             tags=(tipo,))

        if not rows:
            messagebox.showinfo("Sin resultados", "No se encontraron registros con esos filtros.")

    def _eliminar_registro(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Seleccionar", "Seleccione una fila (un registro) para eliminar.")
            return
        iid = sel[0]
        valores = self.tree.item(iid)["values"]
        if not valores:
            return
        reg_id = valores[0]
        nombre_est = valores[1]
        fecha_reg = valores[2]
        hora_reg = valores[3]
        tipo_reg = valores[4]

        if not messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Eliminar este registro?\n\n"
            f"Estudiante: {nombre_est}\n"
            f"Fecha: {fecha_reg}  Hora: {hora_reg}\n"
            f"Tipo: {tipo_reg}\n\n"
            "Esta acción no se puede deshacer."
        ):
            return

        conn = get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM registros WHERE id = ?", (reg_id,))
        conn.commit()
        conn.close()
        self._buscar()
        mostrar_toast(self, f"Registro #{reg_id} eliminado.", color=COLOR_RED)

    def _ir_inicio(self):
        self.winfo_toplevel().destroy()

    def _ir_monitoreo(self):
        open_inner_window(self.winfo_toplevel(), _MonitoreoAdmin)

    def _ir_admin(self):
        self.winfo_toplevel().destroy()


# ═══════════════════════════════════════════════════════════════
#  GENERACIÓN DE REPORTES — placeholders fantasma
# ═══════════════════════════════════════════════════════════════
class GeneracionReportes(tk.Frame):
    def __init__(self, master, root=None, close_callback=None):
        super().__init__(master, bg=BG_MAIN)
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        make_header(self, "RAE")
        make_navbar(self, [
            ("Inicio",         self._ir_inicio),
            ("Monitoreo",      self._ir_monitoreo),
            ("Administración", self._ir_admin),
        ])
        tk.Label(self, text="Generación de Reportes", bg=BG_MAIN, font=FONT_TITLE).pack(anchor="w", padx=24, pady=14)

        filt = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=18, pady=18)
        filt.pack(fill="x", padx=24, pady=(0,12))
        tk.Label(filt, text="Filtros de Reporte", bg=BG_CARD, font=FONT_HEADER).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0,12))

        tk.Label(filt, text="Nombre del Estudiante:", bg=BG_CARD, font=FONT_NORMAL).grid(row=1,column=0,sticky="w")
        self.e_nombre = make_ghost_entry(filt, "Ej. Juan Pérez", width=30)
        self.e_nombre.grid(row=1,column=1,padx=(8,24),ipady=7)

        tk.Label(filt, text="Rango de Fechas:", bg=BG_CARD, font=FONT_NORMAL).grid(row=1,column=2,sticky="w")
        self.e_rango = make_ghost_entry(filt, "AAAA-MM-DD : AAAA-MM-DD", width=30)
        self.e_rango.grid(row=1,column=3,padx=(8,0),ipady=7)

        tk.Label(filt, text="Tipo:", bg=BG_CARD, font=FONT_NORMAL).grid(row=2,column=0,sticky="w",pady=(12,0))
        self.combo_tipo = ttk.Combobox(filt, width=20,
                                        values=["Todos","Solo Ingresos","Solo Salidas"],
                                        font=FONT_NORMAL)
        self.combo_tipo.current(0)
        self.combo_tipo.grid(row=2,column=1,padx=(8,0),pady=(12,0),sticky="w")
        make_btn(filt,"Generar Reporte",self._generar,width=20).grid(
            row=3,column=0,columnspan=2,sticky="w",pady=16)

        res = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=18, pady=16)
        res.pack(fill="both", expand=True, padx=24, pady=(0,12))
        tk.Label(res, text="Reporte — movimientos individuales",
                 bg=BG_CARD, font=FONT_HEADER).pack(anchor="w", pady=(0,10))
        cols = ("ID", "Fecha", "Estudiante", "Tipo", "Hora")
        self.tree = ttk.Treeview(res, columns=cols, show="headings", height=12)
        widths = {"ID":70,"Fecha":160,"Estudiante":340,"Tipo":140,"Hora":140}
        for col in cols:
            self.tree.heading(col,text=col)
            self.tree.column(col,width=widths[col], anchor="center" if col != "Estudiante" else "w")

        sb = ttk.Scrollbar(res, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree.tag_configure("ingreso", foreground=COLOR_GREEN)
        self.tree.tag_configure("salida",  foreground=COLOR_BLUE)

        make_btn(self,"Volver al panel",self.winfo_toplevel().destroy,width=20).pack(
            anchor="w",padx=24,pady=10)

    def _generar(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        nombre = ghost_get(self.e_nombre)
        rango  = ghost_get(self.e_rango)
        fecha_ini = fecha_fin = ""
        if rango and ":" in rango:
            partes = [p.strip() for p in rango.split(":")]
            if len(partes) == 2:
                fecha_ini, fecha_fin = partes

        tipo_filtro = self.combo_tipo.get()
        conn = get_connection()
        c = conn.cursor()
        q = """
            SELECT r.id, r.fecha, e.nombre||' '||e.apellido, r.tipo, r.hora
            FROM registros r
            JOIN estudiantes e ON r.estudiante_id = e.id
            WHERE 1=1
        """
        params = []
        if nombre:
            q += " AND (e.nombre LIKE ? OR e.apellido LIKE ?)"
            params += [f"%{nombre}%",f"%{nombre}%"]
        if fecha_ini and fecha_fin:
            q += " AND r.fecha BETWEEN ? AND ?"
            params += [fecha_ini,fecha_fin]
        if tipo_filtro == "Solo Ingresos":
            q += " AND r.tipo='Ingreso'"
        elif tipo_filtro == "Solo Salidas":
            q += " AND r.tipo='Salida'"
        q += " ORDER BY r.id DESC"
        c.execute(q, params)
        rows = c.fetchall()
        conn.close()
        for reg_id, fecha, est, tipo, hora in rows:
            tag = "ingreso" if tipo == "Ingreso" else "salida"
            self.tree.insert("","end", values=(reg_id, fecha, est, tipo, hora), tags=(tag,))
        if not rows:
            messagebox.showinfo("Sin resultados","No se encontraron registros con esos filtros.")

    def _ir_inicio(self):
        self.winfo_toplevel().destroy()

    def _ir_monitoreo(self):
        open_inner_window(self.winfo_toplevel(), _MonitoreoAdmin)

    def _ir_admin(self):
        self.winfo_toplevel().destroy()


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    init_db()
    root = tk.Tk()
    root.title("RAE – Registro de Asistencia Estudiantil")
    root.geometry(WIN_MAIN)
    root.configure(bg=BG_MAIN)
    root.resizable(True, True)

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Treeview", background=BG_WHITE, foreground="#333",
                    rowheight=34, fieldbackground=BG_WHITE, font=FONT_NORMAL)
    style.configure("Treeview.Heading", background=BG_HEADER, foreground="#333",
                    font=FONT_HEADER, padding=(10,8))
    style.map("Treeview", background=[("selected", COLOR_LIGHT)])

    PantallaInicio(root)
    root.mainloop()


if __name__ == "__main__":
    main()