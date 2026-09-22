# Capturador de Señas LSC — UDI 2026 (versión secuencias)

Software para capturar señas y ampliar la base de datos del proyecto de
Lengua de Señas Colombiana. **Esta versión captura secuencias de movimiento**
(no fotos), que es lo que el modelo de reconocimiento necesita.

## ⚠️ Antes de empezar: coloca los modelos

Abre la carpeta `data\` y lee `COLOCAR_MODELOS_AQUI.txt`. Debes poner ahí los
dos archivos `.task`. **Sin ellos el programa no arranca.**

## Requisitos del computador

- Windows con webcam.
- Python instalado con «Add Python to PATH» marcado.
- Conexión a internet (para instalar librerías la primera vez).

## Instalación y ejecución (la forma fácil)

1. Descomprime esta carpeta en el Escritorio.
2. Coloca los `.task` en `data\` (ver arriba).
3. Doble clic en **`ejecutar_windows.bat`**.
   - La primera vez crea el entorno e instala librerías (tarda unos minutos).
   - Las siguientes veces abre directo.

### Si prefieres la terminal

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app_captura_lsc.py
```

## Cómo capturar

Al abrir, llena los datos:

| Campo | Qué poner |
|---|---|
| Seña | En minúscula, sin tildes, sin espacios (usa guion_bajo). Ej: `hola`, `por_favor` |
| Código del estudiante | El asignado, ej. `E01` |
| Código del participante | `P001`, `P002`... (NO nombres reales) |
| Sesión | `01` la primera vez |
| Mano | `derecha`, `izquierda`, `ambas` o `sin_manos` |
| Iluminación | `buena`, `media` o `baja` |
| Fondo | `claro`, `oscuro` o `cotidiano` |
| Cantidad de secuencias | `30` para captura oficial; `3` para probar |

Sobre la opción **Mano**:
- `derecha` / `izquierda` / `ambas`: si no se ven manos, la secuencia se
  descarta y se repite (control de calidad).
- `sin_manos`: para señas que solo usan la cabeza. Graba aunque no haya manos.

### Durante la captura
- Mantén la seña de forma natural durante cada ráfaga (verás «GRABANDO»).
- No cambies de seña a mitad.
- Espera a que el contador llegue al número indicado.
- Al final, el programa pregunta si quedó bien: Sí conserva, No borra y repite.

## Qué se guarda

Se crea una carpeta `dataset_lsc` con esta estructura:

```
dataset_lsc/
└── hola/
    └── E01_P001/
        └── sesion_01/
            ├── hola_E01_P001_s01_derecha_luzbuena_fondoclaro_001.npy
            ├── ...
            └── metadata.csv
```

Los archivos son **.npy** (secuencias de características), no imágenes.

## Qué entregar

La carpeta completa `dataset_lsc`, sin borrar ni renombrar nada. Incluye
los `metadata.csv` y el `metadata_global.csv`.

## Problemas frecuentes

| Problema | Solución |
|---|---|
| «Falta MediaPipe» al capturar | Faltan los `.task` en `data\`, o no se instaló mediapipe. Revisa ambos. |
| No abre la cámara | Cierra Zoom/Teams. Revisa permisos: Config > Privacidad > Cámara. |
| «python no se reconoce» | Reinstala Python marcando «Add Python to PATH». |
| No instala librerías | Verifica que aparezca `(venv)` en la terminal y reintenta. |

## Regla final

No modifiques el código. Solo captura y entrega la carpeta `dataset_lsc`.
La calidad del dataset depende de capturar bien, no rápido.
