#!/bin/bash
set -u

cd "$(dirname "$0")" || exit 1

echo
echo "Configurar audio - Innova Client Demo para Raspberry Pi"
echo "-------------------------------------------------------"
echo

if [ ! -x ".venv/bin/python" ]; then
  echo "No se encontro el entorno .venv."
  echo "Ejecuta instalar.sh primero."
  echo
  read -r -p "Presiona Enter para cerrar..."
  exit 1
fi

source ".venv/bin/activate"
python audio_setup.py
if [ $? -ne 0 ]; then
  echo
  echo "No se pudo guardar la configuracion de audio."
  echo
  read -r -p "Presiona Enter para cerrar..."
  exit 1
fi

echo
read -r -p "Presiona Enter para cerrar..."
