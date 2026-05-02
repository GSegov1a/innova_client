@echo off
setlocal
cd /d "%~dp0"

echo.
echo Instalador de Innova Client Demo
echo --------------------------------
echo Este paso se ejecuta solo una vez.
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo No se encontro Python.
  echo Instala Python desde https://www.python.org/downloads/
  echo Marca la opcion "Add Python to PATH" durante la instalacion.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno de Python...
  python -m venv .venv
  if errorlevel 1 (
    echo No se pudo crear el entorno.
    pause
    exit /b 1
  )
)

echo Instalando dependencias...
call ".venv\Scripts\activate.bat"

python -m pip install --upgrade pip
if errorlevel 1 (
  echo No se pudo actualizar pip.
  pause
  exit /b 1
)

python -m pip install -r requirements.txt
if errorlevel 1 (
  echo No se pudieron instalar las dependencias.
  pause
  exit /b 1
)

echo.
echo Instalacion lista. Ahora configuraremos el audio.
echo.
call configurar_audio.bat
if errorlevel 1 (
  echo.
  echo La instalacion termino, pero falta configurar el audio.
  echo Ejecuta configurar_audio.bat cuando puedas.
  echo.
  pause
  exit /b 1
)

echo.
echo Listo. Para usar el cliente normalmente, ejecuta iniciar.bat
echo.
pause
