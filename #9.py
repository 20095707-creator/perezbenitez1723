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
#  COLORES Y FUENTES (tema visual)
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

FONT_TITLE  = ("Segoe UI", 18, "bold")
FONT_HEADER = ("Segoe UI", 11, "bold")
FONT_NORMAL = ("Segoe UI", 10)
FONT_SMALL  = ("Segoe UI", 9)
FONT_BTN    = ("Segoe UI", 10, "bold")

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
                    relief="flat", cursor="hand2", padx=10, pady=6, width=width)
    btn.bind("<Enter>", lambda e: btn.config(bg=_darken(color)))
    btn.bind("<Leave>", lambda e: btn.config(bg=color))
    return btn

def _darken(hex_color):
    return {COLOR_BLUE:"#1558b0",COLOR_RED:"#b71c1c",COLOR_GREEN:"#2e7d32",COLOR_GRAY:"#424242"}.get(hex_color, hex_color)

def make_header(parent, title):
    hdr = tk.Frame(parent, bg=BG_HEADER, height=50)
    hdr.pack(fill="x")
    tk.Label(hdr, text=title, bg=BG_HEADER, font=("Segoe UI",13,"bold"), padx=14).pack(side="left", pady=10)
    return hdr

def make_navbar(parent, items):
    nav = tk.Frame(parent, bg=BG_HEADER, height=34)
    nav.pack(fill="x")
    for label, cmd in items:
        tk.Button(nav, text=label, command=cmd, bg=BG_HEADER, fg="#333",
                  font=FONT_NORMAL, relief="flat", cursor="hand2", padx=12, pady=5).pack(side="left")
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
#  CAPTURA DE ROSTRO — VERSIÓN CORREGIDA
#  Problema original: face_recognition.face_encodings() se llamaba
#  desde el hilo de video, causando que el encoding nunca llegara
#  al callback correctamente. Ahora la detección para el guardado
#  ocurre en el hilo principal al presionar "Capturar".
# ═══════════════════════════════════════════════════════════════
class CapturaRostro(BaseWindow):
    def __init__(self, master, callback):
        super().__init__(master, "Capturar Rostro", "520x430")
        self.callback = callback
        self.capturando = True
        self.current_frame = None          # frame más reciente (BGR)
        self.lock = threading.Lock()
        self.imgtk_ref = None              # evitar garbage-collection de la imagen
        self._build()

    def _build(self):
        make_header(self, "RAE – Captura de Rostro")

        self.lbl_video = tk.Label(self, bg="black")
        self.lbl_video.pack(pady=(8, 4))

        self.lbl_estado = tk.Label(self, text="Coloque su rostro frente a la cámara",
                                   bg=BG_MAIN, font=FONT_HEADER, fg=COLOR_GRAY)
        self.lbl_estado.pack(pady=2)

        btn_frame = tk.Frame(self, bg=BG_MAIN)
        btn_frame.pack(pady=8)
        make_btn(btn_frame, "📸  Capturar Rostro", self._capturar,
                 color=COLOR_GREEN, width=20).pack(side="left", padx=8)
        make_btn(btn_frame, "Cancelar", self._cancelar,
                 color=COLOR_RED, width=12).pack(side="left")

        # Abrir cámara
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            messagebox.showerror("Error", "No se pudo abrir la cámara.")
            self.destroy()
            return

        # Hilo solo para leer frames y mostrarlos — NO procesa encodings
        self.thread = threading.Thread(target=self._loop_video, daemon=True)
        self.thread.start()
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

    # ── hilo de video: solo captura + muestra preview ──────────
    def _loop_video(self):
        while self.capturando:
            ret, frame = self.cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)

            # Guardar frame en variable compartida (con lock)
            with self.lock:
                self.current_frame = frame.copy()

            # Detección rápida para el rectángulo visual (escala pequeña)
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

            # Convertir y mostrar en el hilo principal via after()
            img = Image.fromarray(cv2.cvtColor(display, cv2.COLOR_BGR2RGB))
            imgtk = ImageTk.PhotoImage(image=img)
            try:
                self.lbl_video.after(0, self._show_frame, imgtk)
            except tk.TclError:
                break   # ventana cerrada

    def _show_frame(self, imgtk):
        self.imgtk_ref = imgtk          # ← CRÍTICO: evitar garbage-collection
        self.lbl_video.configure(image=imgtk)

    # ── botón Capturar: corre en el hilo principal ──────────────
    def _capturar(self):
        """
        Toma el frame actual y extrae el encoding EN EL HILO PRINCIPAL.
        Esto evita condiciones de carrera y asegura que el encoding
        se pase correctamente al callback del formulario.
        """
        with self.lock:
            frame = self.current_frame.copy() if self.current_frame is not None else None

        if frame is None:
            messagebox.showwarning("Error", "La cámara aún no tiene imagen. Espere un momento.")
            return

        self.lbl_estado.config(text="Procesando rostro...", fg=COLOR_BLUE)
        self.update()   # refrescar UI antes de procesar

        # Procesar en resolución completa para mejor precisión
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locs = face_recognition.face_locations(rgb, number_of_times_to_upsample=1)

        if not locs:
            self.lbl_estado.config(text="⚠ No se detectó ningún rostro. Intente de nuevo.", fg=COLOR_RED)
            return

        # Extraer encoding del primer rostro detectado
        encodings = face_recognition.face_encodings(rgb, locs, num_jitters=1)
        if not encodings:
            self.lbl_estado.config(text="⚠ No se pudo procesar el rostro.", fg=COLOR_RED)
            return

        encoding = encodings[0]
        self.lbl_estado.config(text="✅ Rostro capturado correctamente.", fg=COLOR_GREEN)
        self.update()

        messagebox.showinfo("Éxito", "Rostro capturado. Ahora pulse Guardar en el formulario.")

        # Pasar el encoding al formulario y cerrar
        self.capturando = False
        if self.cap.isOpened():
            self.cap.release()

        self.callback(encoding)   # ← siempre llegar aquí con un encoding válido
        self.destroy()

    def _cancelar(self):
        self.capturando = False
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        self.callback(None)
        self.destroy()


# ═══════════════════════════════════════════════════════════════
#  FORMULARIO DE ESTUDIANTE — VERSIÓN CORREGIDA
# ═══════════════════════════════════════════════════════════════
class FormEstudiante(BaseWindow):
    def __init__(self, master, est_id, callback):
        super().__init__(master, "Formulario Estudiante", "420x530")
        self.est_id   = est_id
        self.callback = callback
        self.face_encoding = None          # se llena al capturar
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

        # Botón capturar rostro
        self.btn_capturar = tk.Button(
            card, text="📸  Capturar Rostro",
            command=self._abrir_captura,
            bg=COLOR_GRAY, fg="white", font=FONT_BTN,
            relief="flat", cursor="hand2", padx=10, pady=6, width=22
        )
        self.btn_capturar.grid(row=4, column=0, columnspan=2, pady=14)

        # Etiqueta de estado del rostro
        self.lbl_rostro = tk.Label(card, text="Sin rostro capturado",
                                   bg=BG_CARD, font=FONT_SMALL, fg=COLOR_GRAY)
        self.lbl_rostro.grid(row=5, column=0, columnspan=2)

        # Pre-cargar datos si es edición
        if self.est_id:
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT nombre, apellido, grado, password FROM estudiantes WHERE id=?", (self.est_id,))
            row = c.fetchone()
            # Verificar si ya tiene rostro guardado
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

        make_btn(self, "💾  Guardar Estudiante", self._guardar, width=24).pack(pady=14)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _abrir_captura(self):
        # Deshabilitar botón mientras la cámara está abierta
        self.btn_capturar.config(state="disabled", text="Cámara abierta...")
        CapturaRostro(self, self._recibir_encoding)

    def _recibir_encoding(self, encoding):
        """Callback que llama CapturaRostro al terminar."""
        self.btn_capturar.config(state="normal")
        if encoding is not None:
            self.face_encoding = encoding
            # Confirmar visualmente que el encoding llegó
            self.btn_capturar.config(
                text="✅ Rostro listo — Pulse Guardar",
                bg=COLOR_GREEN
            )
            self.lbl_rostro.config(
                text=f"Encoding: {len(encoding)} valores — listo para guardar",
                fg=COLOR_GREEN
            )
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

            # ── Guardar encoding facial ──────────────────────────────
            rostro_msg = ""
            if self.face_encoding is not None:
                # Verificar que el encoding sea un numpy array válido
                if not isinstance(self.face_encoding, np.ndarray):
                    raise ValueError("El encoding no es válido.")

                blob = pickle.dumps(self.face_encoding)

                # Reemplazar cualquier encoding anterior
                c.execute("DELETE FROM estudiantes_faces WHERE estudiante_id=?", (id_guardado,))
                c.execute(
                    "INSERT INTO estudiantes_faces (estudiante_id, encoding) VALUES (?,?)",
                    (id_guardado, blob)
                )
                rostro_msg = "\n✅ Rostro facial guardado correctamente."
            # ────────────────────────────────────────────────────────

            conn.commit()
            messagebox.showinfo("Guardado", f"Estudiante guardado.{rostro_msg}")

            self.face_encoding = None   # marcar como ya guardado
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
#  VENTANA DE RECONOCIMIENTO FACIAL EN TIEMPO REAL
# ═══════════════════════════════════════════════════════════════
class VentanaCamaraReconocimiento(BaseWindow):
    def __init__(self, master, callback_registro):
        super().__init__(master, "Reconocimiento Facial", "750x550")
        self.callback_registro = callback_registro
        self.capturando = True
        self.rostro_reconocido = None
        self.imgtk_ref = None
        self._build()

    def _build(self):
        make_header(self, "RAE – Identificación por Cámara")
        self.lbl_video = tk.Label(self, bg="black")
        self.lbl_video.pack(padx=10, pady=10)
        self.lbl_info = tk.Label(self, text="Buscando rostro...", bg=BG_MAIN, font=FONT_HEADER)
        self.lbl_info.pack(pady=5)
        make_btn(self, "Confirmar Registro", self._confirmar, color=COLOR_GREEN, width=22).pack(pady=5)

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
        face_locations_draw = []
        nombre_mostrar = "Desconocido"
        color = (0,0,255)
        frame_count = 0

        while self.capturando:
            ret, frame = self.cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)

            if frame_count % 3 == 0:
                small = cv2.resize(frame, (0,0), fx=scale, fy=scale)
                rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                locs = face_recognition.face_locations(rgb_small, number_of_times_to_upsample=0)
                encs = face_recognition.face_encodings(rgb_small, locs, num_jitters=0)

                self.rostro_reconocido = None
                nombre_mostrar = "Desconocido"
                color = (0,0,255)

                for enc in encs:
                    if self.known_encodings:
                        matches = face_recognition.compare_faces(self.known_encodings, enc, tolerance=0.5)
                        if True in matches:
                            idx = matches.index(True)
                            nombre_mostrar = self.known_names[idx]
                            self.rostro_reconocido = (self.known_ids[idx], self.known_names[idx])
                            color = (0,255,0)
                            break

                face_locations_draw = []
                for (top, right, bottom, left) in locs:
                    face_locations_draw.append((
                        int(top/scale), int(right/scale),
                        int(bottom/scale), int(left/scale)
                    ))

            for (top, right, bottom, left) in face_locations_draw:
                cv2.rectangle(frame, (left,top), (right,bottom), color, 2)
                cv2.putText(frame, nombre_mostrar, (left, top-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            imgtk = ImageTk.PhotoImage(image=img)
            try:
                self.lbl_video.after(0, self._update_video, imgtk)
                if self.rostro_reconocido:
                    nombre = self.rostro_reconocido[1]
                    self.lbl_info.after(0, lambda n=nombre: self.lbl_info.config(
                        text=f"✅ Reconocido: {n}", fg="green"))
                else:
                    self.lbl_info.after(0, lambda: self.lbl_info.config(
                        text="🔍 Buscando rostro...", fg="black"))
            except tk.TclError:
                break
            frame_count += 1

    def _update_video(self, imgtk):
        self.imgtk_ref = imgtk
        self.lbl_video.configure(image=imgtk)

    def _confirmar(self):
        if self.rostro_reconocido:
            est_id, nombre = self.rostro_reconocido
            partes = nombre.split(" ", 1)
            nom = partes[0]
            ape = partes[1] if len(partes) > 1 else ""
            self.callback_registro(est_id, nom, ape)
            self._cerrar()
        else:
            messagebox.showwarning("Sin reconocimiento",
                                   "Acérquese a la cámara o no se ha reconocido ningún rostro.")

    def _cerrar(self):
        self.capturando = False
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
        self.destroy()


# ═══════════════════════════════════════════════════════════════
#  PANTALLA 1 – INICIO
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
                 bg=BG_HEADER, font=("Segoe UI",11,"bold"), padx=16).pack(side="left", pady=12)

        tk.Label(self, text="Registro de Ingreso / Salida",
                 bg=BG_MAIN, font=FONT_TITLE).pack(pady=(40,20))

        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=40, pady=30)
        card.pack(ipadx=20)

        tk.Label(card, text="Ingresar Datos Manualmente", bg=BG_CARD, font=FONT_HEADER).pack(pady=(0,14))

        self.entry_id = tk.Entry(card, font=FONT_NORMAL, width=32, bd=1, relief="solid", fg=COLOR_GRAY)
        self.entry_id.insert(0, "Número de Identificación")
        self.entry_id.bind("<FocusIn>",  self._clear_placeholder)
        self.entry_id.bind("<FocusOut>", self._restore_placeholder)
        self.entry_id.pack(pady=(0,16), ipady=8)

        make_btn(card, "Registrar", self._registrar, width=30).pack()
        make_btn(card, "🔍 Identificación por cámara", self._abrir_camara,
                 color=COLOR_GREEN, width=30).pack(pady=10)

        icons_frame = tk.Frame(self, bg=BG_MAIN)
        icons_frame.pack(pady=40)
        self._make_icon(icons_frame, "✔", "Registro\nexitoso",    COLOR_BLUE,  self._ver_exitoso)
        self._make_icon(icons_frame, "👤","Acceso personal\nportería", COLOR_GREEN, self._login_porteria)
        self._make_icon(icons_frame, "👥","Acceso\nadministrador/director", "#7c4dff", self._login_admin)

    def _make_icon(self, parent, symbol, label, color, command):
        frame = tk.Frame(parent, bg=BG_MAIN)
        frame.pack(side="left", padx=24)
        tk.Button(frame, text=symbol, font=("Segoe UI",22), bg=color, fg="white",
                  width=3, height=1, relief="flat", cursor="hand2", command=command).pack()
        tk.Label(frame, text=label, bg=BG_MAIN, font=FONT_SMALL, fg=COLOR_GRAY, justify="center").pack(pady=4)

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
        now = datetime.now()
        fecha = now.strftime("%Y-%m-%d")
        hora  = now.strftime("%I:%M %p")
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT tipo FROM registros WHERE estudiante_id=? AND fecha=? ORDER BY id DESC LIMIT 1",
                  (est_id, fecha))
        ultimo = c.fetchone()
        tipo = "Salida" if ultimo and ultimo[0] == "Ingreso" else "Ingreso"
        c.execute("INSERT INTO registros (estudiante_id, tipo, fecha, hora, observaciones) VALUES (?,?,?,?,?)",
                  (est_id, tipo, fecha, hora, "Registrado automáticamente"))
        conn.commit()
        conn.close()
        PantallaRegistroExitoso(self.winfo_toplevel(), nombre, apellido, tipo)

    def _abrir_camara(self):
        try:
            VentanaCamaraReconocimiento(self.winfo_toplevel(), self._realizar_registro)
        except Exception as e:
            messagebox.showerror("Error de cámara", f"No se pudo iniciar la cámara: {e}")

    def _ver_exitoso(self):
        PantallaRegistroExitoso(self.winfo_toplevel(), "Demo", "Usuario", "Ingreso")

    def _login_porteria(self):
        LoginWindow(self.winfo_toplevel(), "porteria")

    def _login_admin(self):
        LoginWindow(self.winfo_toplevel(), "admin")


# ═══════════════════════════════════════════════════════════════
#  RESTO DE PANTALLAS (sin cambios funcionales)
# ═══════════════════════════════════════════════════════════════
class PantallaRegistroExitoso(BaseWindow):
    def __init__(self, master, nombre, apellido, tipo):
        super().__init__(master, "Registro Exitoso", "540x380")
        make_header(self, "RAE")
        tk.Label(self, text="✔", font=("Segoe UI",48), bg=BG_MAIN, fg=COLOR_GREEN).pack(pady=(40,6))
        tk.Label(self, text="¡Registro Exitoso!", bg=BG_MAIN, font=("Segoe UI",16,"bold")).pack()
        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=30, pady=20)
        card.pack(pady=20)
        tk.Label(card, text=f"Tu {tipo.lower()} ha sido registrado correctamente.",
                 bg=BG_CARD, font=FONT_NORMAL, fg=COLOR_GRAY).pack()
        tk.Label(card, text=f"Estudiante: {nombre} {apellido}",
                 bg=BG_CARD, font=FONT_HEADER).pack(pady=(8,0))
        make_btn(self, "Volver al Inicio", self.destroy, width=20).pack(pady=8)


class LoginWindow(BaseWindow):
    def __init__(self, master, rol_esperado):
        super().__init__(master, "Iniciar sesión", "380x280")
        self.rol_esperado = rol_esperado
        self._build()

    def _build(self):
        tk.Label(self, text="Iniciar Sesión", bg=BG_MAIN, font=FONT_TITLE).pack(pady=(30,20))
        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=30, pady=20)
        card.pack()
        tk.Label(card, text="Usuario:", bg=BG_CARD, font=FONT_NORMAL).pack(anchor="w")
        self.e_user = tk.Entry(card, font=FONT_NORMAL, width=28, bd=1, relief="solid")
        self.e_user.pack(pady=(2,10), ipady=5)
        tk.Label(card, text="Contraseña:", bg=BG_CARD, font=FONT_NORMAL).pack(anchor="w")
        self.e_pass = tk.Entry(card, font=FONT_NORMAL, width=28, show="*", bd=1, relief="solid")
        self.e_pass.pack(pady=(2,14), ipady=5)
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
        self.master.withdraw()
        self.destroy()
        if rol == "porteria":
            open_new_window(self.master, PanelPorteria, root=self.master)
        else:
            open_new_window(self.master, PanelAdministracion, root=self.master)


def open_new_window(master, cls, root=None):
    win = tk.Toplevel(master)
    win.geometry("1000x660")
    win.configure(bg=BG_MAIN)
    win.title("RAE")
    def on_close():
        if root:
            root.deiconify()
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", on_close)
    cls(win, root=root, close_callback=on_close)


class PanelPorteria(tk.Frame):
    def __init__(self, master, root=None, close_callback=None):
        super().__init__(master, bg=BG_MAIN)
        self.root = root
        self.close_callback = close_callback
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        make_header(self, "RAE")
        make_navbar(self, [("Inicio",lambda:None),("Monitoreo",self._refresh),("Cerrar sesión",self._logout)])
        tk.Label(self, text="Panel de Monitoreo (Personal de Portería)",
                 bg=BG_MAIN, font=FONT_TITLE).pack(anchor="w", padx=20, pady=14)
        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=16, pady=16)
        card.pack(fill="both", expand=True, padx=20, pady=(0,20))
        tk.Label(card, text="Registros en Tiempo Real", bg=BG_CARD, font=FONT_HEADER).pack(anchor="w", pady=(0,10))
        cols = ("Estudiante","Tipo de Registro","Hora","Acciones")
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
        c = conn.cursor()
        c.execute("""SELECT r.id, e.nombre||' '||e.apellido, r.tipo, r.hora
                     FROM registros r JOIN estudiantes e ON r.estudiante_id=e.id
                     ORDER BY r.id DESC LIMIT 20""")
        for reg_id, nombre, tipo, hora in c.fetchall():
            self.tree.insert("","end", iid=reg_id, values=(nombre,tipo,hora,"Doble clic → detalles"))
        conn.close()

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if sel:
            DetallesRegistro(self.winfo_toplevel(), int(sel[0]))

    def _logout(self):
        if self.close_callback:
            self.close_callback()
        else:
            self.winfo_toplevel().destroy()
            if self.root:
                self.root.deiconify()


class DetallesRegistro(BaseWindow):
    def __init__(self, master, reg_id):
        super().__init__(master, "Detalles de Registro", "700x420")
        make_header(self, "RAE")
        tk.Label(self, text="Detalles de Registro", bg=BG_MAIN, font=FONT_TITLE).pack(anchor="w", padx=20, pady=12)
        conn = get_connection()
        c = conn.cursor()
        c.execute("""SELECT e.nombre||' '||e.apellido, e.id, r.tipo,
                            r.fecha||' '||r.hora, r.observaciones, r.registrado_por
                     FROM registros r JOIN estudiantes e ON r.estudiante_id=e.id WHERE r.id=?""", (reg_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            tk.Label(self, text="Registro no encontrado.", bg=BG_MAIN, font=FONT_NORMAL).pack(pady=40)
            return
        nombre, est_id, tipo, fecha_hora, obs, reg_por = row
        card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=30, pady=24)
        card.pack(fill="x", padx=20)
        def field(lbl, val, r, col):
            tk.Label(card, text=lbl+":", bg=BG_CARD, font=FONT_HEADER).grid(row=r, column=col*2, sticky="w", pady=4, padx=(0,8))
            tk.Label(card, text=val, bg=BG_CARD, font=FONT_NORMAL, fg=COLOR_GRAY).grid(row=r+1, column=col*2, sticky="w")
        field("Estudiante", nombre, 0, 0)
        field("ID Estudiante", str(est_id), 0, 1)
        field("Tipo de Registro", tipo, 2, 0)
        field("Fecha y Hora", fecha_hora, 2, 1)
        tk.Label(card, text="Observaciones:", bg=BG_CARD, font=FONT_HEADER).grid(row=4,column=0,sticky="w",pady=(12,0))
        tk.Label(card, text=obs or "—", bg=BG_CARD, font=FONT_NORMAL, fg=COLOR_GRAY).grid(row=5,column=0,sticky="w")
        make_btn(self, "Volver al Monitoreo", self.destroy, width=22).pack(anchor="w", padx=20, pady=16)


class PanelAdministracion(tk.Frame):
    def __init__(self, master, root=None, close_callback=None):
        super().__init__(master, bg=BG_MAIN)
        self.root = root
        self.close_callback = close_callback
        self.pack(fill="both", expand=True)
        self._build()

    def _build(self):
        make_header(self, "RAE")
        make_navbar(self, [("Inicio",lambda:None),("Monitoreo",lambda:None),("Cerrar sesión",self._logout)])
        tk.Label(self, text="Panel de Administración", bg=BG_MAIN, font=FONT_TITLE).pack(pady=(30,20))
        cards_frame = tk.Frame(self, bg=BG_MAIN)
        cards_frame.pack()
        for icon, label, cmd in [
            ("👥","Gestionar estudiantes",self._gestionar_estudiantes),
            ("🕐","Consultar historial",  self._consultar_historial),
            ("📄","Generar reportes",     self._generar_reportes),
        ]:
            f = tk.Frame(cards_frame, bg=BG_CARD, bd=1, relief="solid", padx=30, pady=30)
            f.pack(side="left", padx=16, ipadx=10)
            tk.Label(f, text=icon, font=("Segoe UI",32), bg=BG_CARD, fg=COLOR_BLUE).pack(pady=(0,8))
            tk.Label(f, text=label, bg=BG_CARD, font=FONT_HEADER).pack(pady=(0,14))
            make_btn(f, "Ir", cmd, width=8).pack()

    def _gestionar_estudiantes(self):
        open_new_window(self.winfo_toplevel(), GestionEstudiantes)

    def _consultar_historial(self):
        open_new_window(self.winfo_toplevel(), ConsultaHistorial)

    def _generar_reportes(self):
        open_new_window(self.winfo_toplevel(), GeneracionReportes)

    def _logout(self):
        if self.close_callback:
            self.close_callback()
        else:
            self.winfo_toplevel().destroy()
            if self.root:
                self.root.deiconify()


class GestionEstudiantes(tk.Frame):
    def __init__(self, master, root=None, close_callback=None):
        super().__init__(master, bg=BG_MAIN)
        self.root = root
        self.close_callback = close_callback
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
        make_btn(btn_row, "Editar Estudiante",  self._editar,   color=COLOR_GRAY, width=18).pack(side="left", padx=4)
        make_btn(btn_row, "Eliminar Estudiante",self._eliminar, color=COLOR_RED,  width=18).pack(side="left", padx=4)

        search_card = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=14, pady=10)
        search_card.pack(fill="x", padx=20, pady=(0,10))
        tk.Label(search_card, text="Buscar Estudiante", bg=BG_CARD, font=FONT_HEADER).pack(anchor="w")
        self.e_buscar = tk.Entry(search_card, font=FONT_NORMAL, width=60, bd=1, relief="solid")
        self.e_buscar.pack(anchor="w", pady=(4,8), ipady=5)
        self.e_buscar.insert(0, "Buscar por nombre o ID")
        make_btn(search_card, "Buscar", self._buscar, width=10).pack(anchor="w")

        cols = ("ID","Nombre","Apellido","Grado","Rostro","Acciones")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=10)
        widths = {"ID":60,"Nombre":180,"Apellido":180,"Grado":80,"Rostro":100,"Acciones":150}
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[col])
        self.tree.pack(fill="both", expand=True, padx=20, pady=(0,16))
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
            self.tree.insert("","end", iid=row[0], values=(*row,"Editar | Eliminar"))
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


class ConsultaHistorial(tk.Frame):
    def __init__(self, master, root=None, close_callback=None):
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
        left = tk.Frame(filt, bg=BG_CARD)
        left.pack(side="left", padx=(0,20))
        tk.Label(left, text="Buscar por Nombre:", bg=BG_CARD, font=FONT_NORMAL).pack(anchor="w")
        self.e_nombre = tk.Entry(left, font=FONT_NORMAL, width=30, bd=1, relief="solid")
        self.e_nombre.pack(pady=4, ipady=5)
        right = tk.Frame(filt, bg=BG_CARD)
        right.pack(side="left")
        tk.Label(right, text="Buscar por Fecha (AAAA-MM-DD):", bg=BG_CARD, font=FONT_NORMAL).pack(anchor="w")
        self.e_fecha = tk.Entry(right, font=FONT_NORMAL, width=22, bd=1, relief="solid")
        self.e_fecha.pack(pady=4, ipady=5)
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
        for row in self.tree.get_children():
            self.tree.delete(row)
        nombre = self.e_nombre.get().strip()
        fecha  = self.e_fecha.get().strip()
        conn = get_connection()
        c = conn.cursor()
        q = """SELECT e.nombre||' '||e.apellido, r.fecha,
                      MAX(CASE WHEN r.tipo='Ingreso' THEN r.hora END),
                      MAX(CASE WHEN r.tipo='Salida'  THEN r.hora END)
               FROM registros r JOIN estudiantes e ON r.estudiante_id=e.id WHERE 1=1"""
        params = []
        if nombre:
            q += " AND (e.nombre LIKE ? OR e.apellido LIKE ?)"
            params += [f"%{nombre}%", f"%{nombre}%"]
        if fecha:
            q += " AND r.fecha=?"
            params.append(fecha)
        q += " GROUP BY e.id, r.fecha ORDER BY r.fecha DESC"
        c.execute(q, params)
        for row in c.fetchall():
            self.tree.insert("","end", values=(row[0],row[1],row[2] or "—",row[3] or "—"))
        conn.close()


class GeneracionReportes(tk.Frame):
    def __init__(self, master, root=None, close_callback=None):
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
        self.e_nombre.insert(0,"Ej. Juan Pérez")
        self.e_nombre.grid(row=1,column=1,padx=(6,20),ipady=5)
        tk.Label(filt, text="Rango de Fechas:", bg=BG_CARD, font=FONT_NORMAL).grid(row=1,column=2,sticky="w")
        self.e_rango = tk.Entry(filt, font=FONT_NORMAL, width=28, bd=1, relief="solid")
        self.e_rango.insert(0,"AAAA-MM-DD : AAAA-MM-DD")
        self.e_rango.grid(row=1,column=3,padx=(6,0),ipady=5)
        tk.Label(filt, text="Tipo de Reporte:", bg=BG_CARD, font=FONT_NORMAL).grid(row=2,column=0,sticky="w",pady=(10,0))
        self.combo_tipo = ttk.Combobox(filt, width=26, values=["Asistencia Diaria","Resumen Mensual","Ausencias"])
        self.combo_tipo.current(0)
        self.combo_tipo.grid(row=2,column=1,padx=(6,0),pady=(10,0),sticky="w")
        make_btn(filt,"Generar Reporte",self._generar,width=18).grid(row=3,column=0,columnspan=2,sticky="w",pady=14)

        res = tk.Frame(self, bg=BG_CARD, bd=1, relief="solid", padx=16, pady=14)
        res.pack(fill="both", expand=True, padx=20, pady=(0,10))
        tk.Label(res, text="Reporte Generado", bg=BG_CARD, font=FONT_HEADER).pack(anchor="w", pady=(0,8))
        cols = ("Fecha","Estudiante","Hora de Entrada","Hora de Salida","Estado")
        self.tree = ttk.Treeview(res, columns=cols, show="headings", height=8)
        for col in cols:
            self.tree.heading(col,text=col)
            self.tree.column(col,width=160)
        self.tree.pack(fill="both", expand=True)
        make_btn(self,"Volver al panel",self.winfo_toplevel().destroy,width=18).pack(anchor="w",padx=20,pady=8)

    def _generar(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        nombre = self.e_nombre.get().strip()
        if nombre == "Ej. Juan Pérez":
            nombre = ""
        rango = self.e_rango.get().strip()
        fecha_ini = fecha_fin = ""
        if ":" in rango:
            partes = [p.strip() for p in rango.split(":")]
            if len(partes) == 2:
                fecha_ini, fecha_fin = partes
        conn = get_connection()
        c = conn.cursor()
        q = """SELECT r.fecha, e.nombre||' '||e.apellido,
                      MAX(CASE WHEN r.tipo='Ingreso' THEN r.hora END),
                      MAX(CASE WHEN r.tipo='Salida'  THEN r.hora END)
               FROM registros r JOIN estudiantes e ON r.estudiante_id=e.id WHERE 1=1"""
        params = []
        if nombre:
            q += " AND (e.nombre LIKE ? OR e.apellido LIKE ?)"
            params += [f"%{nombre}%",f"%{nombre}%"]
        if fecha_ini and fecha_fin:
            q += " AND r.fecha BETWEEN ? AND ?"
            params += [fecha_ini,fecha_fin]
        q += " GROUP BY r.fecha, e.id ORDER BY r.fecha DESC"
        c.execute(q, params)
        rows = c.fetchall()
        conn.close()
        for fecha, est, entrada, salida in rows:
            estado = "Presente" if entrada else "Ausente"
            self.tree.insert("","end", values=(fecha,est,entrada or "—",salida or "—",estado))
        if not rows:
            messagebox.showinfo("Sin resultados","No se encontraron registros con esos filtros.")


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