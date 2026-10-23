"""
Visor de archivos .npy del dataset LSC (versión dual).

Uso:
    python ver_npy.py <archivo.npy | archivo_frames.npy | carpeta_de_sesion>
    (en Windows: arrastre el archivo o la carpeta sobre ver_npy.bat)

Qué hace:
  * Imprime forma, tipo y estadísticos del archivo.
  * Exporta un .csv con nombres de columna al lado del .npy (se abre en Excel).
  * Para <base>_frames.npy (N x 152): dibuja el esqueleto de la mano frame a frame
    junto a la imagen .jpg correspondiente y guarda <base>_vista.png.
  * Con una carpeta: lista todas las secuencias (frames por secuencia, % con mano).
"""

import csv
import sys
from pathlib import Path

import cv2
import numpy as np

CONEXIONES = [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
              (5, 9), (9, 10), (10, 11), (11, 12), (9, 13), (13, 14), (14, 15), (15, 16),
              (13, 17), (17, 18), (18, 19), (19, 20), (0, 17)]


def _pts(prefijo, n=21):
    return [f"{prefijo}_p{i:02d}_{c}" for i in range(n) for c in "xyz"]


COLS_FRAME = _pts("mano_der") + _pts("mano_izq") + _pts("boca", 8) + ["dist_mano_boca", "cara_presente"]
COLS_AGREGADO = (_pts("mean_der") + _pts("mean_izq") + _pts("mean_boca", 8) + _pts("std_der") +
                 _pts("std_izq") + _pts("delta_der") + ["dist_mean", "dist_min", "dist_std"])


def exportar_csv(arr, ruta_csv):
    arr2 = arr.reshape(1, -1) if arr.ndim == 1 else arr
    if arr2.shape[1] == 152:
        cols = COLS_FRAME
    elif arr2.shape[1] == 342:
        cols = COLS_AGREGADO
    else:
        cols = [f"f{i}" for i in range(arr2.shape[1])]
    with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["frame"] + cols)
        for i, fila in enumerate(arr2):
            w.writerow([i] + [f"{v:.6f}".replace(".", ",") for v in fila])
    print(f"CSV (Excel, separador ';'): {ruta_csv}")


def dibujar_mano(lienzo, vec63, color):
    if not np.any(vec63):
        return
    p = vec63.reshape(21, 3)[:, :2]
    h, w = lienzo.shape[:2]
    escala = min(h, w) * 0.22
    centro = np.array([w / 2, h * 0.70])
    xy = (p * escala + centro).astype(int)
    for a, b in CONEXIONES:
        cv2.line(lienzo, tuple(xy[a]), tuple(xy[b]), color, 2)
    for q in xy:
        cv2.circle(lienzo, tuple(q), 3, color, -1)


def vista_frames(ruta_npy, arr):
    base = ruta_npy.name[:-len("_frames.npy")]
    carpeta = ruta_npy.parent / base
    jpgs = sorted(carpeta.glob("*.jpg")) if carpeta.is_dir() else []
    celdas = []
    for i, fila in enumerate(arr):
        img = cv2.imread(str(jpgs[i])) if i < len(jpgs) else None
        img = cv2.resize(img, (240, 135)) if img is not None else np.zeros((135, 240, 3), np.uint8)
        esq = np.full((135, 135, 3), 30, np.uint8)
        dibujar_mano(esq, fila[0:63], (0, 220, 0))     # derecha: verde
        dibujar_mano(esq, fila[63:126], (255, 160, 0))  # izquierda: azul
        celda = np.hstack([img, esq])
        cv2.putText(celda, f"{i:02d}  d_boca={fila[150]:.2f}", (5, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        celdas.append(celda)
    cols = 4
    while len(celdas) % cols:
        celdas.append(np.zeros_like(celdas[0]))
    mosaico = np.vstack([np.hstack(celdas[r:r + cols]) for r in range(0, len(celdas), cols)])
    salida = ruta_npy.parent / f"{base}_vista.png"
    cv2.imwrite(str(salida), mosaico)
    print(f"Vista guardada: {salida}  (verde = mano derecha, azul = izquierda)")
    if len(jpgs) != len(arr):
        print(f"AVISO: {len(arr)} filas en el npy pero {len(jpgs)} imágenes en {carpeta}")
    try:
        alto = mosaico.shape[0]
        if alto > 900:
            mosaico = cv2.resize(mosaico, None, fx=900 / alto, fy=900 / alto)
        cv2.imshow("Secuencia LSC - cualquier tecla para cerrar", mosaico)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    except cv2.error:
        pass  # sin entorno gráfico: queda el .png


def ver_archivo(ruta):
    arr = np.load(ruta, allow_pickle=False)
    print(f"\nArchivo: {ruta}\nForma: {arr.shape}  tipo: {arr.dtype}")
    print(f"min={arr.min():.4f}  max={arr.max():.4f}  media={arr.mean():.4f}  NaN={int(np.isnan(arr).sum())}")
    if arr.ndim == 2 and arr.shape[1] == 152:
        con_mano = np.any(arr[:, :126] != 0, axis=1)
        print(f"Frames: {len(arr)}  con mano: {con_mano.sum()}  con rostro: {int(arr[:, 151].sum())}")
        mov = np.linalg.norm(np.diff(arr[:, :63], axis=0), axis=1)
        if len(mov):
            print("Movimiento mano der. entre frames consecutivos:", np.round(mov, 3))
    elif arr.ndim == 1 and arr.size == 342:
        print("Vector agregado de 342 (mean/std/delta de la secuencia). "
              "Para ver frame a frame abra el *_frames.npy.")
    exportar_csv(arr, ruta.with_suffix(".csv"))
    if arr.ndim == 2 and arr.shape[1] == 152:
        vista_frames(ruta, arr)
    elif arr.ndim == 1 and arr.size == 342:
        hermano = ruta.with_name(ruta.stem + "_frames.npy")
        if hermano.exists():
            print(f"\nAbriendo los frames de esta secuencia: {hermano.name}")
            ver_archivo(hermano)
        else:
            print("No se encontró el *_frames.npy de esta secuencia (captura de versión anterior).")


def ver_carpeta(carpeta):
    archivos = sorted(carpeta.rglob("*_frames.npy"))
    if not archivos:
        print("No hay *_frames.npy en la carpeta.")
        return
    print(f"{'secuencia':60s} frames  %mano  %rostro")
    for f in archivos:
        a = np.load(f)
        print(f"{f.name[:-11]:60s} {len(a):6d}  {100*np.mean(np.any(a[:, :126] != 0, axis=1)):5.0f}"
              f"  {100*a[:, 151].mean():6.0f}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    ruta = Path(sys.argv[1])
    if ruta.is_dir():
        ver_carpeta(ruta)
    elif ruta.suffix == ".npy":
        ver_archivo(ruta)
    else:
        print("Indique un .npy o una carpeta.")


if __name__ == "__main__":
    main()
