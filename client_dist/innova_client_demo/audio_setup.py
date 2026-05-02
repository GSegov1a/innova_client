import json
from pathlib import Path

import sounddevice as sd


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
DEFAULT_CONFIG = {
    "backend_url": "https://innovabackend-production-c18a.up.railway.app",
    "child_id": 1,
    "device_token": "innovaraspberrytoken",
    "mic_device": None,
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


def query_devices():
    devices = sd.query_devices()
    return [dict(device, index=index) for index, device in enumerate(devices)]


def print_devices(title, devices):
    print()
    print(title)
    print("-" * len(title))
    for device in devices:
        print(f"{device['index']:>3} - {device['name']}")


def choose_device(prompt, devices):
    valid_indexes = {device["index"] for device in devices}

    while True:
        value = input(prompt).strip()
        try:
            selected_index = int(value)
        except ValueError:
            print("Escribe solo el numero del dispositivo.")
            continue

        if selected_index not in valid_indexes:
            print("Ese numero no esta en la lista. Intenta otra vez.")
            continue

        return next(device for device in devices if device["index"] == selected_index)


def main():
    print("Configuracion de audio para Innova")
    print()
    print("Elige el microfono y el parlante que usara el cliente.")
    print("Si no estas segura, prueba con los dispositivos que usas normalmente en Windows.")

    devices = query_devices()
    microphones = [device for device in devices if device.get("max_input_channels", 0) > 0]
    speakers = [device for device in devices if device.get("max_output_channels", 0) > 0]

    if not microphones:
        raise RuntimeError("No se encontraron microfonos conectados.")
    if not speakers:
        raise RuntimeError("No se encontraron parlantes o audifonos conectados.")

    print_devices("Microfonos", microphones)
    mic = choose_device("Numero de microfono: ", microphones)

    print_devices("Parlantes / audifonos", speakers)
    speaker = choose_device("Numero de parlante o audifono: ", speakers)

    config = load_config()
    config["mic_device"] = f"audio={mic['name']}"
    config["speaker_device"] = speaker["index"]
    config["speaker_rate"] = int(config.get("speaker_rate") or 48000)
    save_config(config)

    print()
    print("Configuracion guardada.")
    print(f"Microfono: {config['mic_device']}")
    print(f"Parlante: {speaker['name']} (numero {speaker['index']})")
    print()
    print("Ahora ejecuta iniciar.bat")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print(f"Error configurando audio: {exc}")
        raise SystemExit(1)
