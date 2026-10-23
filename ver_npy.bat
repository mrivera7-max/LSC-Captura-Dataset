@echo off
setlocal
cd /d "%~dp0"
rem Arrastre un .npy (o una carpeta de sesion) sobre este archivo.
if "%~1"=="" (
    echo Arrastre un archivo .npy o una carpeta sobre ver_npy.bat
    pause
    goto :eof
)
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" ver_npy.py "%~1"
) else (
    python ver_npy.py "%~1"
)
pause
