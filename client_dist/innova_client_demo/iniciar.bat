@echo off
setlocal
cd /d "%~dp0"

echo.
echo Innova Client Demo
echo ------------------
echo Uso normal:
echo   c = conectar o desconectar
echo   q = salir
echo.

if not exist ".venv\Scripts\python.exe" (
  echo No se encontro el entorno .venv.
  echo Ejecuta instalar.bat primero.
  echo.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"

if not exist "config.json" (
  echo No se encontro config.json. Vamos a configurar el audio.
  echo.
  call configurar_audio.bat
  if errorlevel 1 exit /b 1
)

python run_from_config.py
if errorlevel 2 (
  echo.
  echo Falta configuracion. Vamos a configurar el audio.
  echo.
  call configurar_audio.bat
  if errorlevel 1 exit /b 1
  python run_from_config.py
)

echo.
pause
