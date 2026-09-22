import csv
import os
import re
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

import cv2
import numpy as np

# El extractor vive en models/. Añadimos la raíz del proyecto al path.
# El extractor vive junto a este archivo (paquete autónomo para estudiantes).
_RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(_RAIZ))
try:
    from extractor_v2 import ExtractorSecuencial, VENTANA_FRAMES
    EXTRACTOR_OK = True
except Exception as _e:
    EXTRACTOR_OK = False
    _IMPORT_ERROR = str(_e)

# =====================================================
# SOFTWARE DE CAPTURA DATASET LSC - UDI
# Versión GUI — captura SECUENCIAS (.npy de features), no fotos.
# Compatible con el modelo v2 (mano + cara).
# - Ventana inicial para ingresar toda la información
# - Captura ráfagas de ~20 frames y guarda el vector de features
# - Conserva metadatos: estudiante, participante, sesión, mano, luz, fondo
# =====================================================

DATASET_DIR = Path("dataset_lsc")
MANOS_VALIDAS = ["derecha", "izquierda", "ambas", "sin_manos"]
ILUMINACION_VALIDA = ["buena", "media", "baja"]
FONDOS_VALIDOS = ["claro", "oscuro", "cotidiano"]

# Cuántas secuencias grabar por defecto (antes eran 100 fotos; ahora son
# secuencias completas, así que el número razonable es mucho menor).
SECUENCIAS_POR_DEFECTO = 30
DURACION_SECUENCIA_S = 0.7  # duración de cada ráfaga, igual que capturar_secuencias


def limpiar_texto(texto: str) -> str:
    texto = texto.lower().strip()
    reemplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n",
        "Á": "a", "É": "e", "Í": "i", "Ó": "o", "Ú": "u", "Ñ": "n"
    }
    for original, nuevo in reemplazos.items():
        texto = texto.replace(original, nuevo)
    texto = texto.replace(" ", "_")
    texto = re.sub(r"[^a-zA-Z0-9_\-]", "", texto)
    texto = re.sub(r"_+", "_", texto)
    return texto.strip("_")


def limpiar_codigo(texto: str) -> str:
    texto = texto.strip().upper().replace(" ", "_")
    texto = re.sub(r"[^a-zA-Z0-9_\-]", "", texto)
    return texto


def crear_metadata_si_no_existe(metadata_path: Path):
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    if not metadata_path.exists():
        with metadata_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([
                "archivo",
                "sena",
                "estudiante",
                "participante",
                "sesion",
                "mano",
                "iluminacion",
                "fondo",
                "frames_usados",
                "manos_detectadas",
                "fecha",
                "ruta"
            ])


def guardar_metadata(metadata_path: Path, fila):
    with metadata_path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(fila)


def eliminar_filas_metadata_global(metadata_global_path: Path, ruta_sesion: Path):
    if not metadata_global_path.exists():
        return

    with metadata_global_path.open("r", newline="", encoding="utf-8") as file:
        filas = list(csv.reader(file))

    if not filas:
        return

    encabezado = filas[0]
    ruta_abs = str(ruta_sesion.resolve())
    filas_filtradas = [encabezado]

    for fila in filas[1:]:
        if len(fila) < 12:
            continue
        ruta_imagen = Path(fila[11])
        try:
            ruta_imagen_abs = str(ruta_imagen.resolve())
        except OSError:
            ruta_imagen_abs = str(ruta_imagen)
        if not ruta_imagen_abs.startswith(ruta_abs):
            filas_filtradas.append(fila)

    with metadata_global_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerows(filas_filtradas)


class CapturaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Captura Dataset LSC - UDI")
        self.root.geometry("720x560")
        self.root.resizable(False, False)

        self.capturando = False
        self.cancelar = False
        self.datos_actuales = None

        self.crear_interfaz()

    def crear_interfaz(self):
        titulo = ttk.Label(
            self.root,
            text="Software de Captura de Imágenes - Dataset LSC",
            font=("Arial", 16, "bold")
        )
        titulo.pack(pady=12)

        subtitulo = ttk.Label(
            self.root,
            text="Proyecto Lengua de Señas Colombiana | Interacción con Unitree G1",
            font=("Arial", 10)
        )
        subtitulo.pack(pady=2)

        frame = ttk.LabelFrame(self.root, text="Información de captura")
        frame.pack(padx=20, pady=15, fill="x")

        self.var_sena = tk.StringVar()
        self.var_estudiante = tk.StringVar(value="E01")
        self.var_participante = tk.StringVar(value="P001")
        self.var_sesion = tk.StringVar(value="01")
        self.var_mano = tk.StringVar(value="derecha")
        self.var_iluminacion = tk.StringVar(value="buena")
        self.var_fondo = tk.StringVar(value="claro")
        self.var_cantidad = tk.StringVar(value=str(SECUENCIAS_POR_DEFECTO))

        self.agregar_campo(frame, "Seña a capturar:", self.var_sena, 0, ejemplo="Ej: hola, gracias, buenos_dias")
        self.agregar_campo(frame, "Código estudiante:", self.var_estudiante, 1, ejemplo="Ej: E01")
        self.agregar_campo(frame, "Código participante:", self.var_participante, 2, ejemplo="Ej: P001")
        self.agregar_campo(frame, "Sesión:", self.var_sesion, 3, ejemplo="Ej: 01")

        ttk.Label(frame, text="Mano:").grid(row=4, column=0, padx=10, pady=8, sticky="e")
        ttk.Combobox(frame, textvariable=self.var_mano, values=MANOS_VALIDAS, state="readonly", width=28).grid(row=4, column=1, padx=10, pady=8, sticky="w")

        ttk.Label(frame, text="Iluminación:").grid(row=5, column=0, padx=10, pady=8, sticky="e")
        ttk.Combobox(frame, textvariable=self.var_iluminacion, values=ILUMINACION_VALIDA, state="readonly", width=28).grid(row=5, column=1, padx=10, pady=8, sticky="w")

        ttk.Label(frame, text="Fondo:").grid(row=6, column=0, padx=10, pady=8, sticky="e")
        ttk.Combobox(frame, textvariable=self.var_fondo, values=FONDOS_VALIDOS, state="readonly", width=28).grid(row=6, column=1, padx=10, pady=8, sticky="w")

        self.agregar_campo(frame, "Cantidad de secuencias:", self.var_cantidad, 7, ejemplo="Recomendado: 30")

        frame_botones = ttk.Frame(self.root)
        frame_botones.pack(pady=10)

        self.btn_iniciar = ttk.Button(frame_botones, text="Iniciar captura", command=self.iniciar_captura)
        self.btn_iniciar.grid(row=0, column=0, padx=8)

        self.btn_salir = ttk.Button(frame_botones, text="Salir", command=self.root.destroy)
        self.btn_salir.grid(row=0, column=1, padx=8)

        self.estado = tk.StringVar(value="Estado: esperando información de captura")
        ttk.Label(self.root, textvariable=self.estado, font=("Arial", 10, "bold")).pack(pady=10)

        instrucciones = (
            "Indicaciones:\n"
            "1. Escriba la seña sin tildes preferiblemente. Ej: si, hola, gracias.\n"
            "2. No use nombres reales de participantes. Use códigos: P001, P002...\n"
            "3. La cámara abrirá una ventana externa. Mantenga la seña estable.\n"
            "4. Al finalizar podrá aceptar la captura o repetirla si quedó mal."
        )
        ttk.Label(self.root, text=instrucciones, justify="left").pack(padx=20, pady=10, anchor="w")

    def agregar_campo(self, frame, etiqueta, variable, fila, ejemplo=""):
        ttk.Label(frame, text=etiqueta).grid(row=fila, column=0, padx=10, pady=8, sticky="e")
        entrada = ttk.Entry(frame, textvariable=variable, width=31)
        entrada.grid(row=fila, column=1, padx=10, pady=8, sticky="w")
        if ejemplo:
            ttk.Label(frame, text=ejemplo, foreground="gray").grid(row=fila, column=2, padx=6, pady=8, sticky="w")

    def validar_datos(self):
        sena = limpiar_texto(self.var_sena.get())
        estudiante = limpiar_codigo(self.var_estudiante.get())
        participante = limpiar_codigo(self.var_participante.get())
        sesion = limpiar_texto(self.var_sesion.get()) or "01"
        mano = limpiar_texto(self.var_mano.get())
        iluminacion = limpiar_texto(self.var_iluminacion.get())
        fondo = limpiar_texto(self.var_fondo.get())

        try:
            cantidad = int(self.var_cantidad.get())
        except ValueError:
            messagebox.showerror("Error", "La cantidad de imágenes debe ser un número entero.")
            return None

        if cantidad <= 0:
            messagebox.showerror("Error", "La cantidad de imágenes debe ser mayor que cero.")
            return None

        if not sena:
            messagebox.showerror("Error", "Debe escribir la seña a capturar.")
            return None
        if not estudiante:
            messagebox.showerror("Error", "Debe escribir el código del estudiante.")
            return None
        if not participante:
            messagebox.showerror("Error", "Debe escribir el código del participante.")
            return None

        return {
            "sena": sena,
            "estudiante": estudiante,
            "participante": participante,
            "sesion": sesion,
            "mano": mano,
            "iluminacion": iluminacion,
            "fondo": fondo,
            "cantidad": cantidad,
        }

    def iniciar_captura(self):
        datos = self.validar_datos()
        if datos is None:
            return

        id_participante = f"{datos['estudiante']}_{datos['participante']}"
        ruta_salida = DATASET_DIR / datos["sena"] / id_participante / f"sesion_{datos['sesion']}"

        if ruta_salida.exists():
            respuesta = messagebox.askyesno(
                "Captura existente",
                "Ya existe una captura con estos datos.\n\n"
                f"Ruta:\n{ruta_salida}\n\n"
                "¿Desea reemplazarla?\n\n"
                "Sí: borra la captura anterior y repite.\n"
                "No: cancela para cambiar sesión o participante."
            )
            if respuesta:
                shutil.rmtree(ruta_salida, ignore_errors=True)
                eliminar_filas_metadata_global(DATASET_DIR / "metadata_global.csv", ruta_salida)
            else:
                return

        resumen = (
            f"Seña: {datos['sena']}\n"
            f"Estudiante: {datos['estudiante']}\n"
            f"Participante: {id_participante}\n"
            f"Sesión: {datos['sesion']}\n"
            f"Mano: {datos['mano']}\n"
            f"Iluminación: {datos['iluminacion']}\n"
            f"Fondo: {datos['fondo']}\n"
            f"Cantidad: {datos['cantidad']}\n\n"
            "¿Desea iniciar la captura?"
        )

        if not messagebox.askyesno("Confirmar captura", resumen):
            return

        self.btn_iniciar.config(state="disabled")
        self.estado.set("Estado: captura en proceso")
        self.datos_actuales = datos

        hilo = threading.Thread(target=self.capturar, args=(datos,), daemon=True)
        hilo.start()

    def capturar(self, datos):
        id_participante = f"{datos['estudiante']}_{datos['participante']}"
        sesion_txt = f"s{datos['sesion']}"
        ruta_salida = DATASET_DIR / datos["sena"] / id_participante / f"sesion_{datos['sesion']}"
        ruta_salida.mkdir(parents=True, exist_ok=True)

        metadata_path = ruta_salida / "metadata.csv"
        metadata_global_path = DATASET_DIR / "metadata_global.csv"
        crear_metadata_si_no_existe(metadata_path)
        crear_metadata_si_no_existe(metadata_global_path)

        # Iniciar el extractor de features (mano + cara). Cada secuencia se
        # convierte en un vector de 342 dimensiones, igual que el dataset del v2.
        if not EXTRACTOR_OK:
            self.root.after(0, lambda: messagebox.showerror(
                "Falta MediaPipe",
                "No se pudo cargar el extractor de features.\n\n"
                f"Detalle: {_IMPORT_ERROR}\n\n"
                "Instala las dependencias y descarga los modelos .task."))
            self.root.after(0, lambda: self.btn_iniciar.config(state="normal"))
            self.root.after(0, lambda: self.estado.set("Estado: falta MediaPipe"))
            return

        extractor = ExtractorSecuencial()
        if not extractor.iniciar():
            self.root.after(0, lambda: messagebox.showerror(
                "Error de modelos",
                "No se pudo iniciar el extractor.\n"
                "Verifica que data/hand_landmarker.task exista."))
            self.root.after(0, lambda: self.btn_iniciar.config(state="normal"))
            self.root.after(0, lambda: self.estado.set("Estado: error de modelos"))
            return

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            extractor.detener()
            self.root.after(0, lambda: messagebox.showerror("Error", "No se pudo abrir la cámara."))
            self.root.after(0, lambda: self.btn_iniciar.config(state="normal"))
            self.root.after(0, lambda: self.estado.set("Estado: error de cámara"))
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        # ¿Esta seña usa manos? Para "sin_manos" NO exigimos manos presentes.
        exige_manos = datos["mano"] != "sin_manos"
        t_global = time.time()

        # Vista previa y cuenta regresiva
        inicio_previa = time.time()
        while time.time() - inicio_previa < 3:
            ret, frame = cap.read()
            if not ret:
                continue
            frame = cv2.flip(frame, 1)
            restante = 3 - int(time.time() - inicio_previa)
            cv2.putText(frame, f"Prepare la sena: {datos['sena']}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            cv2.putText(frame, f"Inicia en {restante}", (20, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
            cv2.imshow("Capturador Dataset LSC", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                cap.release(); cv2.destroyAllWindows(); extractor.detener()
                self.root.after(0, lambda: self.btn_iniciar.config(state="normal"))
                self.root.after(0, lambda: self.estado.set("Estado: captura cancelada"))
                return

        contador = 0
        objetivo = datos["cantidad"]

        # Bucle principal: cada iteración graba UNA secuencia completa.
        while contador < objetivo:
            # --- Grabar una ráfaga de ~VENTANA_FRAMES frames durante DURACION_SECUENCIA_S ---
            frames_features = []
            t_inicio_seq = time.time()
            cancelado = False
            manos_vistas = False

            while time.time() - t_inicio_seq < DURACION_SECUENCIA_S:
                ret, frame = cap.read()
                if not ret:
                    break
                frame = cv2.flip(frame, 1)
                ts_ms = int((time.time() - t_global) * 1000)
                ff = extractor.procesar_frame(frame, ts_ms)
                if ff is not None:
                    frames_features.append(ff)
                    if ff.manos_presentes:
                        manos_vistas = True

                # Overlay
                disp = frame.copy()
                cv2.putText(disp, f"Sena: {datos['sena']} | {id_participante}", (20, 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(disp, f"Secuencia: {contador+1}/{objetivo}", (20, 70),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(disp, "GRABANDO", (20, 105),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.circle(disp, (disp.shape[1] - 40, 40), 12, (0, 0, 255), -1)
                cv2.imshow("Capturador Dataset LSC", disp)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    cancelado = True
                    break

            if cancelado:
                break

            # --- Validar la secuencia ---
            if len(frames_features) < 5:
                # Muy pocos frames: descartar y reintentar sin sumar al contador
                continue
            if exige_manos and not manos_vistas:
                # La seña debería tener manos pero no se vieron: descartar
                # (para "sin_manos" esto no aplica y sí se guarda)
                disp = frame.copy()
                cv2.putText(disp, "No se vieron manos, repite", (20, 140),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
                cv2.imshow("Capturador Dataset LSC", disp)
                cv2.waitKey(400)
                continue

            # --- Guardar el vector de la secuencia ---
            vector = extractor.agregar_secuencia(frames_features)
            contador += 1
            nombre_archivo = (
                f"{datos['sena']}_{id_participante}_{sesion_txt}_"
                f"{datos['mano']}_luz{datos['iluminacion']}_fondo{datos['fondo']}_{contador:03d}.npy"
            )
            ruta_npy = ruta_salida / nombre_archivo
            np.save(ruta_npy, vector)

            fila_metadata = [
                nombre_archivo,
                datos["sena"],
                datos["estudiante"],
                id_participante,
                datos["sesion"],
                datos["mano"],
                datos["iluminacion"],
                datos["fondo"],
                len(frames_features),
                "si" if manos_vistas else "no",
                datetime.now().isoformat(),
                str(ruta_npy)
            ]
            guardar_metadata(metadata_path, fila_metadata)
            guardar_metadata(metadata_global_path, fila_metadata)

            # Breve pausa entre secuencias para reposicionar
            pausa_ini = time.time()
            while time.time() - pausa_ini < 0.4:
                ret, frame = cap.read()
                if not ret:
                    break
                frame = cv2.flip(frame, 1)
                disp = frame.copy()
                cv2.putText(disp, f"Guardada {contador}/{objetivo} - prepara la siguiente", (20, 35),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.imshow("Capturador Dataset LSC", disp)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    cancelado = True
                    break
            if cancelado:
                break

        cap.release()
        cv2.destroyAllWindows()
        extractor.detener()

        self.root.after(0, lambda: self.finalizar_captura(contador, datos, ruta_salida, metadata_global_path))

    def finalizar_captura(self, contador, datos, ruta_salida, metadata_global_path):
        self.estado.set(f"Estado: captura finalizada. Secuencias guardadas: {contador}")

        quedo_bien = messagebox.askyesno(
            "Validar captura",
            f"Se guardaron {contador} secuencias en:\n{ruta_salida}\n\n"
            "¿La captura quedó bien?\n\n"
            "Sí: conservar captura.\n"
            "No: borrar y repetir con los mismos datos."
        )

        if quedo_bien:
            messagebox.showinfo("Captura aceptada", "La captura fue conservada correctamente.")
            self.estado.set("Estado: captura aceptada. Puede registrar otra seña o participante.")
            self.btn_iniciar.config(state="normal")
        else:
            shutil.rmtree(ruta_salida, ignore_errors=True)
            eliminar_filas_metadata_global(metadata_global_path, ruta_salida)
            self.estado.set("Estado: captura eliminada. Repitiendo con los mismos datos...")
            self.btn_iniciar.config(state="disabled")
            hilo = threading.Thread(target=self.capturar, args=(datos,), daemon=True)
            hilo.start()


if __name__ == "__main__":
    root = tk.Tk()
    app = CapturaApp(root)
    root.mainloop()
