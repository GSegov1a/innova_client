Innova Client Demo para Mac
===========================

Contenido
---------
- instalar.command: ejecutalo solo una vez.
- configurar_audio.command: usalo si no se escucha, no escucha, o cambiaste parlante/audifono.
- iniciar.command: uso normal del cliente.

Primer uso
----------
1. Descomprime el ZIP.
2. Entra a la carpeta innova_client_demo_mac.
3. Haz doble click en instalar.command.
4. Si macOS bloquea el archivo, abre Terminal en esta carpeta y ejecuta:
   chmod +x *.command
   ./instalar.command
5. El instalador abrira la configuracion de audio.
6. Elige el parlante/audifono, o presiona Enter para usar el default de macOS.
7. Cuando termine, ejecuta iniciar.command.

Uso normal
----------
Ejecuta iniciar.command.

Dentro de la consola:
- Presiona c para conectar o desconectar.
- Presiona q para salir.

Permisos de microfono
---------------------
La primera vez, macOS puede pedir permiso de Microfono para Terminal o Python.
Acepta el permiso.

Si no aparece el permiso o no escucha:
System Settings > Privacy & Security > Microphone

Activa Terminal y/o Python.

Audio de Mac
------------
El microfono usa avfoundation con :0.
El parlante usa sounddevice. Puedes elegir uno en configurar_audio.command o usar el default de macOS.

Configuracion incluida
----------------------
Backend:
https://innovabackend-production-c18a.up.railway.app

child_id:
1

device_token:
innovaraspberrytoken
