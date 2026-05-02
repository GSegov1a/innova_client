import json
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
CLIENT_PATH = BASE_DIR / "webrtc_client.py"


REQUIRED_KEYS = (
    "backend_url",
    "child_id",
    "device_token",
    "mic_device",
    "speaker_device",
    "speaker_rate",
)


def load_config():
    if not CONFIG_PATH.exists():
        raise RuntimeError("No existe config.json. Ejecuta configurar_audio.bat primero.")

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as file:
            config = json.load(file)
    except json.JSONDecodeError as exc:
        raise RuntimeError("config.json esta dañado. Ejecuta configurar_audio.bat otra vez.") from exc

    missing = [key for key in REQUIRED_KEYS if config.get(key) in {None, ""}]
    if missing:
        raise RuntimeError(
            "Faltan datos en config.json: "
            + ", ".join(missing)
            + ". Ejecuta configurar_audio.bat primero."
        )

    return config


def build_command(config):
    return [
        sys.executable,
        str(CLIENT_PATH),
        "--backend-url",
        str(config["backend_url"]),
        "--child-id",
        str(config["child_id"]),
        "--device-token",
        str(config["device_token"]),
        "--mic-format",
        "dshow",
        "--mic-device",
        str(config["mic_device"]),
        "--speaker-device",
        str(config["speaker_device"]),
        "--speaker-rate",
        str(config["speaker_rate"]),
        "--manual-control",
    ]


def main():
    config = load_config()
    command = build_command(config)
    completed = subprocess.run(command, cwd=BASE_DIR)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print()
        print(f"Error: {exc}")
        raise SystemExit(2)
