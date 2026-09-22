@echo off
echo ============================================
echo   Capturador de Senas LSC - UDI 2026
echo ============================================
if not exist venv (
    echo Creando entorno virtual por primera vez...
    python -m venv venv
    call venv\Scripts\activate
    echo Instalando librerias (esto tarda unos minutos)...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate
)
echo Iniciando capturador...
python app_captura_lsc.py
pause
