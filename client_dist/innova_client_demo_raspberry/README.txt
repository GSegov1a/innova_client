Innova Client Demo para Raspberry Pi
====================================

Target probado/esperado
-----------------------
- Raspberry Pi OS 32-bit
- Raspberry Pi 3 Model B+
- Microfono y parlante/audifono conectados por USB, Bluetooth o audio disponible en ALSA.

Contenido
---------
- instalar.sh: ejecutalo solo una vez.
- configurar_audio.sh: usalo si no escucha, no se escucha, o cambiaste microfono/parlante.
- iniciar.sh: uso normal del cliente.

Primer uso
----------
1. Descomprime el ZIP.
2. Entra a la carpeta innova_client_demo_raspberry.
3. Abre Terminal en esta carpeta.
4. Ejecuta:
   chmod +x *.sh
   ./instalar.sh
5. El instalador instalara dependencias del sistema y de Python.
6. El instalador abrira la configuracion de audio.
7. Elige el numero del microfono.
8. Elige el numero del parlante o audifono.
9. Cuando termine, ejecuta:
   ./iniciar.sh

Uso normal
----------
Ejecuta:
./iniciar.sh

Dentro de la consola:
- Presiona c para conectar o desconectar.
- Presiona q para salir.

Audio en Raspberry Pi OS
------------------------
El microfono usa FFmpeg con ALSA.
La configuracion lista dispositivos de arecord y guarda el dispositivo como plughw:X,Y.

El parlante usa sounddevice. La configuracion lista las salidas disponibles y guarda el numero elegido.

Si no aparece el microfono:
- Revisa que este conectado.
- Ejecuta: arecord -l
- Vuelve a ejecutar: ./configurar_audio.sh

Si no aparece el parlante:
- Revisa la salida de audio de Raspberry Pi OS.
- Ejecuta: python -m sounddevice
- Vuelve a ejecutar: ./configurar_audio.sh

Configuracion incluida
----------------------
Backend:
https://innovabackend-production-c18a.up.railway.app

child_id:
1

device_token:
innovaraspberrytoken
