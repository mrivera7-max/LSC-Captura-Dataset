"""
Manifiesto y huella de una versión del dataset LSC.

Uso:
    python manifiesto_dataset.py <carpeta_dataset> --version v1
        -> MANIFIESTO_v1.csv  (ruta relativa, bytes, sha256 de cada archivo)
           MANIFIESTO_v1.json (huella del dataset, conteos por seña y sujeto)

    python manifiesto_dataset.py <carpeta_dataset> --verificar MANIFIESTO_v1.csv
        -> informa archivos modificados, faltantes o nuevos (código de salida 1 si hay diferencias)

La huella es el SHA-256 de las líneas "ruta;sha256" ordenadas: no depende del
equipo, de la fecha ni del orden de lectura. Dos copias del mismo dataset dan
la misma huella; cualquier cambio en un archivo la cambia.
Los manifiestos se guardan junto a la carpeta del dataset, no dentro de ella.
"""

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

IGNORAR = {"Thumbs.db", "desktop.ini", ".DS_Store"}
PATRON_SUJETO = re.compile(r"^E\d+_P\d+$", re.I)
PATRON_SESION = re.compile(r"^sesion_\d+$", re.I)


def sha256_archivo(ruta: Path, bloque: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for trozo in iter(lambda: f.read(bloque), b""):
            h.update(trozo)
    return h.hexdigest()


def listar(raiz: Path):
    archivos = []
    for p in raiz.rglob("*"):
        if not p.is_file() or p.name in IGNORAR or p.name.startswith("MANIFIESTO_"):
            continue
        if any(parte.startswith(".") or parte == "__pycache__" for parte in p.relative_to(raiz).parts):
            continue
        archivos.append(p)
    return sorted(archivos, key=lambda p: p.relative_to(raiz).as_posix())


def huella(filas) -> str:
    h = hashlib.sha256()
    for ruta, _, digest in sorted(filas):
        h.update(f"{ruta};{digest}\n".encode("utf-8"))
    return h.hexdigest()


def huella_dataset(raiz) -> str:
    """Huella de una carpeta sin escribir nada (la usa la bitácora de experimentos)."""
    raiz = Path(raiz)
    return huella([(p.relative_to(raiz).as_posix(), 0, sha256_archivo(p)) for p in listar(raiz)])


def resumen(raiz: Path, rutas):
    """Cuenta secuencias (archivos *_frames.npy) por seña, sujeto y sesión."""
    por_sena, por_sujeto, sesiones = Counter(), Counter(), set()
    tabla = defaultdict(Counter)
    avisos = []
    for r in rutas:
        partes = r.split("/")
        if not r.endswith("_frames.npy") or len(partes) != 4:
            continue
        sena, sujeto, sesion, _ = partes
        if not PATRON_SUJETO.match(sujeto):
            avisos.append(f"carpeta de sujeto con formato no válido (se espera E##_P###): {sena}/{sujeto}")
        if not PATRON_SESION.match(sesion):
            avisos.append(f"carpeta de sesión con formato no válido (se espera sesion_NN): {sena}/{sujeto}/{sesion}")
        por_sena[sena] += 1
        por_sujeto[sujeto] += 1
        tabla[sena][sujeto] += 1
        sesiones.add((sujeto, sesion))
    senas, sujetos = sorted(por_sena), sorted(por_sujeto)
    faltan = [f"{s} × {u}" for s in senas for u in sujetos if tabla[s][u] == 0]
    if faltan:
        avisos.append(f"{len(faltan)} combinaciones seña × sujeto sin secuencias: " + ", ".join(faltan[:10])
                      + (" …" if len(faltan) > 10 else ""))
    return {
        "secuencias": sum(por_sena.values()),
        "senas": dict(sorted(por_sena.items())),
        "sujetos": len(sujetos),
        "secuencias_por_sujeto": dict(sorted(por_sujeto.items())),
        "sesiones": len(sesiones),
        "tabla_sena_sujeto": {s: dict(sorted(tabla[s].items())) for s in senas},
        "avisos": sorted(set(avisos)),
    }


def generar(raiz: Path, version: str, destino: Path):
    archivos = listar(raiz)
    if not archivos:
        sys.exit(f"No hay archivos en {raiz}")
    filas = []
    for i, p in enumerate(archivos, 1):
        filas.append((p.relative_to(raiz).as_posix(), p.stat().st_size, sha256_archivo(p)))
        if i % 500 == 0:
            print(f"  {i}/{len(archivos)} archivos…")
    h = huella(filas)
    ruta_csv = destino / f"MANIFIESTO_{version}.csv"
    with ruta_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ruta", "bytes", "sha256"])
        w.writerows(filas)
    info = {
        "version": version,
        "huella_sha256": h,
        "huella_corta": h[:12],
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "carpeta": str(raiz.resolve()),
        "archivos": len(filas),
        "bytes": sum(b for _, b, _ in filas),
        **resumen(raiz, [r for r, _, _ in filas]),
    }
    ruta_json = destino / f"MANIFIESTO_{version}.json"
    ruta_json.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDataset {version}: {info['secuencias']} secuencias · {len(info['senas'])} señas · "
          f"{info['sujetos']} sujetos · {info['archivos']} archivos")
    print(f"Huella: {h}")
    for a in info["avisos"]:
        print(f"[AVISO] {a}")
    print(f"\nManifiesto: {ruta_csv}\nResumen:    {ruta_json}")


def verificar(raiz: Path, manifiesto: Path) -> int:
    with manifiesto.open(encoding="utf-8") as f:
        esperado = {r["ruta"]: r["sha256"] for r in csv.DictReader(f)}
    actual = {p.relative_to(raiz).as_posix(): p for p in listar(raiz)}
    faltan = sorted(set(esperado) - set(actual))
    nuevos = sorted(set(actual) - set(esperado))
    cambiados = sorted(r for r in set(esperado) & set(actual) if sha256_archivo(actual[r]) != esperado[r])
    print(f"Verificando {len(esperado)} archivos contra {manifiesto.name}")
    for titulo, lista in (("Modificados", cambiados), ("Faltantes", faltan), ("Nuevos", nuevos)):
        if lista:
            print(f"\n{titulo} ({len(lista)}):")
            for r in lista[:20]:
                print(f"  {r}")
            if len(lista) > 20:
                print(f"  … y {len(lista) - 20} más")
    if faltan or nuevos or cambiados:
        print("\nRESULTADO: el dataset NO coincide con el manifiesto.")
        return 1
    print("\nRESULTADO: el dataset coincide exactamente con el manifiesto.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Manifiesto y huella de una versión del dataset LSC")
    ap.add_argument("carpeta", help="carpeta raíz del dataset (p. ej. dataset_lsc)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--version", help="nombre de la versión, p. ej. v1")
    g.add_argument("--verificar", metavar="MANIFIESTO_CSV", help="comprobar contra un manifiesto existente")
    ap.add_argument("--destino", help="carpeta donde guardar el manifiesto (por defecto, junto al dataset)")
    a = ap.parse_args()
    raiz = Path(a.carpeta)
    if not raiz.is_dir():
        sys.exit(f"No existe la carpeta {raiz}")
    if a.verificar:
        sys.exit(verificar(raiz, Path(a.verificar)))
    if not re.fullmatch(r"[A-Za-z0-9._-]+", a.version):
        sys.exit("La versión solo puede tener letras, números, punto, guion o guion bajo (p. ej. v1)")
    destino = Path(a.destino) if a.destino else raiz.resolve().parent
    for ext in ("csv", "json"):
        if (destino / f"MANIFIESTO_{a.version}.{ext}").exists():
            sys.exit(f"Ya existe MANIFIESTO_{a.version}.{ext}: una versión publicada no se sobrescribe; use otra versión.")
    generar(raiz, a.version, destino)


if __name__ == "__main__":
    main()
