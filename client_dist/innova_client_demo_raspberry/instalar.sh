#!/bin/bash
set -u

cd "$(dirname "$0")" || exit 1

echo
echo "Instalador de Innova Client Demo para Raspberry Pi"
echo "--------------------------------------------------"
echo "Este paso se ejecuta solo una vez."
echo

if [ "$(uname -s)" != "Linux" ]; then
  echo "Este paquete esta pensado para Raspberry Pi OS / Linux."
  echo
  read -r -p "Presiona Enter para cerrar..."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "No se encontro Python 3."
  echo "Instalalo con: sudo apt update && sudo apt install -y python3 python3-venv python3-pip"
  echo
  read -r -p "Presiona Enter para cerrar..."
  exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
  echo "No se encontro apt-get. Instala manualmente las dependencias de requirements.txt."
  echo
else
  echo "Instalando dependencias del sistema..."
  sudo apt-get update
  if [ $? -ne 0 ]; then
    echo "No se pudo ejecutar apt-get update."
    read -r -p "Presiona Enter para cerrar..."
    exit 1
  fi

  sudo apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    python3-dev \
    python3-numpy \
    build-essential \
    pkg-config \
    ffmpeg \
    alsa-utils \
    portaudio19-dev \
    libasound2-dev \
    libavdevice-dev \
    libavfilter-dev \
    libavformat-dev \
    libavcodec-dev \
    libavutil-dev \
    libswresample-dev \
    libswscale-dev \
    libopus-dev \
    libvpx-dev \
    libsrtp2-dev \
    libffi-dev \
    libssl-dev
  if [ $? -ne 0 ]; then
    echo "No se pudieron instalar las dependencias del sistema."
    read -r -p "Presiona Enter para cerrar..."
    exit 1
  fi
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Creando entorno de Python..."
  python3 -m venv --system-site-packages .venv
  if [ $? -ne 0 ]; then
    echo "No se pudo crear el entorno."
    read -r -p "Presiona Enter para cerrar..."
    exit 1
  fi
fi

echo "Instalando dependencias de Python..."
source ".venv/bin/activate"

python -m pip install --upgrade pip setuptools wheel
if [ $? -ne 0 ]; then
  echo "No se pudo actualizar pip."
  read -r -p "Presiona Enter para cerrar..."
  exit 1
fi

python -m pip install -r requirements.txt
if [ $? -ne 0 ]; then
  echo "No se pudieron instalar las dependencias de Python."
  echo
  echo "En Raspberry Pi OS 32-bit algunas librerias pueden tardar o compilar."
  echo "Revisa el error anterior y vuelve a ejecutar instalar.sh."
  read -r -p "Presiona Enter para cerrar..."
  exit 1
fi

echo
echo "Instalacion lista. Ahora configuraremos el audio."
echo
./configurar_audio.sh
if [ $? -ne 0 ]; then
  echo
  echo "La instalacion termino, pero falta configurar el audio."
  echo "Ejecuta configurar_audio.sh cuando puedas."
  echo
  read -r -p "Presiona Enter para cerrar..."
  exit 1
fi

echo
echo "Listo. Para usar el cliente normalmente, ejecuta iniciar.sh"
echo
read -r -p "Presiona Enter para cerrar..."
