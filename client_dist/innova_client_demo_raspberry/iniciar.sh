#!/bin/bash
set -u

cd "$(dirname "$0")" || exit 1

echo
echo "Innova Client Demo para Raspberry Pi"
echo "------------------------------------"
echo "Uso normal:"
echo "  c = conectar o desconectar"
echo "  q = salir"
echo

if [ ! -x ".venv/bin/python" ]; then
  echo "No se encontro el entorno .venv."
  echo "Ejecuta instalar.sh primero."
  echo
  read -r -p "Presiona Enter para cerrar..."
  exit 1
fi

source ".venv/bin/activate"

if [ ! -f "config.json" ]; then
  echo "No se encontro config.json. Vamos a configurar el audio."
  echo
  ./configurar_audio.sh
  if [ $? -ne 0 ]; then
    exit 1
  fi
fi

python run_from_config.py
if [ $? -eq 2 ]; then
  echo
  echo "Falta configuracion. Vamos a configurar el audio."
  echo
  ./configurar_audio.sh
  if [ $? -ne 0 ]; then
    exit 1
  fi
  python run_from_config.py
fi

echo
read -r -p "Presiona Enter para cerrar..."
