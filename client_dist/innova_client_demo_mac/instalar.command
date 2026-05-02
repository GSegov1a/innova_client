#!/bin/bash
cd "$(dirname "$0")" || exit 1

echo
echo "Instalador de Innova Client Demo para Mac"
echo "-----------------------------------------"
echo "Este paso se ejecuta solo una vez."
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "No se encontro Python 3."
  echo "Instala Python desde https://www.python.org/downloads/"
  echo
  read -r -p "Presiona Enter para cerrar..."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Creando entorno de Python..."
  python3 -m venv .venv
  if [ $? -ne 0 ]; then
    echo "No se pudo crear el entorno."
    read -r -p "Presiona Enter para cerrar..."
    exit 1
  fi
fi

echo "Instalando dependencias..."
source ".venv/bin/activate"

python -m pip install --upgrade pip
if [ $? -ne 0 ]; then
  echo "No se pudo actualizar pip."
  read -r -p "Presiona Enter para cerrar..."
  exit 1
fi

python -m pip install -r requirements.txt
if [ $? -ne 0 ]; then
  echo "No se pudieron instalar las dependencias."
  read -r -p "Presiona Enter para cerrar..."
  exit 1
fi

echo
echo "Instalacion lista. Ahora configuraremos el audio."
echo
./configurar_audio.command
if [ $? -ne 0 ]; then
  echo
  echo "La instalacion termino, pero falta configurar el audio."
  echo "Ejecuta configurar_audio.command cuando puedas."
  echo
  read -r -p "Presiona Enter para cerrar..."
  exit 1
fi

echo
echo "Listo. Para usar el cliente normalmente, ejecuta iniciar.command"
echo
read -r -p "Presiona Enter para cerrar..."
