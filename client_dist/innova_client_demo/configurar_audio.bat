@echo off
setlocal
cd /d "%~dp0"

echo.
echo Configurar audio - Innova Client Demo
echo -------------------------------------
echo.

if not exist ".venv\Scripts\python.exe" (
  echo No se encontro el entorno .venv.
  echo Ejecuta instalar.bat primero.
  echo.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
python audio_setup.py
if errorlevel 1 (
  echo.
  echo No se pudo guardar la configuracion de audio.
  echo.
  pause
  exit /b 1
)

echo.
pause
