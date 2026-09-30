@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo   Capturador de Senas LSC - UDI 2026 - version dual
echo ============================================
echo Carpeta: %CD%
echo.

rem --- 1. Buscar Python ---
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (
    where py >nul 2>nul && set "PY=py"
)
if not defined PY goto sin_python

rem --- 2. Crear el entorno si no existe o quedo incompleto ---
if exist "venv\Scripts\python.exe" goto instalar
echo Creando entorno virtual por primera vez...
%PY% -m venv venv
if errorlevel 1 goto error_venv

:instalar
rem --- 3. Instalar librerias solo la primera vez ---
if exist "venv\instalado.ok" goto ejecutar
echo Instalando librerias, esto tarda unos minutos...
"venv\Scripts\python.exe" -m pip install --upgrade pip
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error_pip
echo ok> "venv\instalado.ok"

:ejecutar
rem --- 4. Verificar modelos ---
if not exist "data\hand_landmarker.task" goto sin_modelos
echo Iniciando capturador...
"venv\Scripts\python.exe" app_captura_lsc.py
if errorlevel 1 (
    echo.
    echo [ERROR] El capturador se cerro con un error. Copie el mensaje de arriba y envielo al docente.
)
goto fin

:sin_python
echo [ERROR] No se encontro Python. Instalelo marcando "Add Python to PATH" y vuelva a intentar.
goto fin

:error_venv
echo [ERROR] No se pudo crear el entorno virtual "venv".
goto fin

:error_pip
echo [ERROR] No se pudieron instalar las librerias. Revise la conexion a internet y vuelva a ejecutar.
goto fin

:sin_modelos
echo [ERROR] Falta data\hand_landmarker.task. Lea data\COLOCAR_MODELOS_AQUI.txt
goto fin

:fin
echo.
pause
