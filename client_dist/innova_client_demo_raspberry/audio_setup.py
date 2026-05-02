import json
import re
import subprocess
from pathlib import Path

import sounddevice as sd


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
DEFAULT_CONFIG = {
    "backend_url": "https://innovabackend-production-c18a.up.railway.app",
    "child_id": 1,
    "device_token": "innovaraspberrytoken",
    "mic_device": None,
    "mic_format": "alsa",
    "speaker_device": None,
    "speaker_rate": 48000,
}


def load_config():
    if not CONFIG_PATH.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except (OSError, json.JSONDecodeError):
        return DEFAULT_CONFIG.copy()

    merged = DEFAULT_CONFIG.copy()
    merged.update(config)
    return merged


def save_config(config):
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        json.dump(config, file, indent=2, ensure_ascii=False)
        file.write("\n")


def run_command(command):
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    return completed.stdout + completed.stderr


def query_alsa_capture_devices():
    output = run_command(["arecord", "-l"])
    devices = []
    pattern = re.compile(r"^card\s+(\d+):\s+(.+?),\s+device\s+(\d+):\s+(.+?)\s+\[")

    for line in output.splitlines():
        match = pattern.search(line.strip())
        if not match:
            continue

        card_number, card_name, device_number, device_name = match.groups()
        devices.append(
            {
                "index": len(devices),
                "alsa_device": f"plughw:{card_number},{device_number}",
                "name": f"{card_name} - {device_name}",
            }
        )

    return devices


def query_speakers():
    devices = sd.query_devices()
    speakers = []

    for index, device in enumerate(devices):
        if device.get("max_output_channels", 0) <= 0:
            continue
        speakers.append(dict(device, index=index))

    return speakers


def print_mics(devices):
    print()
    print("Microfonos")
    print("----------")
    for device in devices:
        print(f"{device['index']:>3} - {device['name']} ({device['alsa_device']})")


def print_speakers(devices):
    print()
    print("Parlantes / audifonos")
    print("---------------------")
    for device in devices:
        default_marker = " (default)" if device.get("default") else ""
        print(f"{device['index']:>3} - {device['name']}{default_marker}")


def choose_device(prompt, devices, key="index"):
    valid_values = {device[key] for device in devices}

    while True:
        value = input(prompt).strip()
        try:
            selected_value = int(value)
        except ValueError:
            print("Escribe solo el numero del dispositivo.")
            continue

        if selected_value not in valid_values:
            print("Ese numero no esta en la lista. Intenta otra vez.")
            continue

        return next(device for device in devices if device[key] == selected_value)


def main():
    print("Configuracion de audio para Innova en Raspberry Pi")
    print()
    print("Elige el microfono y el parlante que usara el cliente.")
    print("Si no estas seguro, prueba con los dispositivos USB o Bluetooth que usas normalmente.")

    microphones = query_alsa_capture_devices()
    speakers = query_speakers()

    if not microphones:
        raise RuntimeError(
            "No se encontraron microfonos ALSA. Revisa que el microfono este conectado y prueba: arecord -l"
        )
    if not speakers:
        raise RuntimeError("No se encontraron parlantes o audifonos conectados.")

    default_output = sd.default.device[1] if sd.default.device else None
    for device in speakers:
        device["default"] = device["index"] == default_output

    print_mics(microphones)
    mic = choose_device("Numero de microfono: ", microphones)

    print_speakers(speakers)
    speaker = choose_device("Numero de parlante o audifono: ", speakers)

    config = load_config()
    config["mic_format"] = "alsa"
    config["mic_device"] = mic["alsa_device"]
    config["speaker_device"] = speaker["index"]
    config["speaker_rate"] = int(config.get("speaker_rate") or 48000)
    save_config(config)

    print()
    print("Configuracion guardada.")
    print(f"Microfono: {mic['name']} ({mic['alsa_device']})")
    print(f"Parlante: {speaker['name']} (numero {speaker['index']})")
    print()
    print("Ahora ejecuta iniciar.sh")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print(f"Error configurando audio: {exc}")
        raise SystemExit(1)
