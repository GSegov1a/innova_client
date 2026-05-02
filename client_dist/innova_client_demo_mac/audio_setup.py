import json
from pathlib import Path

import sounddevice as sd


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
DEFAULT_CONFIG = {
    "backend_url": "https://innovabackend-production-c18a.up.railway.app",
    "child_id": 1,
    "device_token": "innovaraspberrytoken",
    "mic_device": ":0",
    "mic_format": "avfoundation",
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
        default_marker = " (default)" if device.get("default") else ""
        print(f"{device['index']:>3} - {device['name']}{default_marker}")


def choose_optional_speaker(speakers):
    valid_indexes = {device["index"] for device in speakers}

    while True:
        value = input("Numero de parlante/audifono, o Enter para usar el default de macOS: ").strip()
        if not value:
            return None, None

        try:
            selected_index = int(value)
        except ValueError:
            print("Escribe solo el numero del dispositivo, o Enter.")
            continue

        if selected_index not in valid_indexes:
            print("Ese numero no esta en la lista. Intenta otra vez.")
            continue

        speaker = next(device for device in speakers if device["index"] == selected_index)
        return speaker["index"], speaker["name"]


def main():
    print("Configuracion de audio para Innova en Mac")
    print()
    print("Microfono:")
    print("- El cliente usara avfoundation con el primer microfono de macOS (:0).")
    print("- Si macOS pide permiso de Microfono para Terminal o Python, acepta.")
    print("- Si no escucha, revisa System Settings > Privacy & Security > Microphone.")
    print()
    print("Parlante/audifono:")
    print("- Puedes elegir uno de la lista o presionar Enter para usar el default de macOS.")

    devices = query_devices()
    speakers = [device for device in devices if device.get("max_output_channels", 0) > 0]

    if not speakers:
        raise RuntimeError("No se encontraron parlantes o audifonos conectados.")

    default_output = sd.default.device[1] if sd.default.device else None
    for device in speakers:
        device["default"] = device["index"] == default_output

    print_devices("Parlantes / audifonos", speakers)
    speaker_index, speaker_name = choose_optional_speaker(speakers)

    config = load_config()
    config["mic_device"] = ":0"
    config["mic_format"] = "avfoundation"
    config["speaker_device"] = speaker_index
    config["speaker_rate"] = int(config.get("speaker_rate") or 48000)
    save_config(config)

    print()
    print("Configuracion guardada.")
    print("Microfono: avfoundation :0")
    if speaker_index is None:
        print("Parlante: default de macOS")
    else:
        print(f"Parlante: {speaker_name} (numero {speaker_index})")
    print()
    print("Ahora ejecuta iniciar.command")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print(f"Error configurando audio: {exc}")
        raise SystemExit(1)
