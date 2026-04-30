import argparse
import asyncio
import json
import logging
import sys

import aiohttp
import av
import numpy as np
from aiortc import MediaStreamTrack, RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaRecorder


CLIENT_VERSION = "2026-04-30-clean-config-mute"
LOGGER = logging.getLogger("innova-client")


def default_audio_devices():
    """Devuelve dispositivos/formatos de FFmpeg razonables para cada plataforma."""
    if sys.platform.startswith("win"):
        return {
            "mic_device": None,
            "mic_format": "dshow",
            "speaker_device": None,
            "speaker_format": None,
        }

    if sys.platform == "darwin":
        return {
            "mic_device": ":0",
            "mic_format": "avfoundation",
            "speaker_device": "-",
            "speaker_format": "audiotoolbox",
        }

    return {
        "mic_device": "default",
        "mic_format": "alsa",
        "speaker_device": "default",
        "speaker_format": "alsa",
    }


def parse_args():
    """Lee la configuración necesaria para conectar el cliente al backend."""
    defaults = default_audio_devices()
    parser = argparse.ArgumentParser(
        description="WebRTC audio client for Innova/OpenAI Realtime.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            'Windows example: python webrtc_client.py --backend-url http://192.168.1.91:8000 '
            '--child-id 1 --device-token innovaraspberrytoken --mic-format dshow '
            '--mic-device "audio=Micrófono (Realtek(R) Audio)" --speaker-device 3 '
            "--speaker-rate 48000 --manual-control"
        ),
    )
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000", help="Backend base URL.")
    parser.add_argument("--child-id", type=int, default=1, help="Child id used to create the Realtime session.")
    parser.add_argument("--device-token", required=True, help="Device token sent as X-Device-Token.")
    parser.add_argument("--mic-device", default=defaults["mic_device"], help="FFmpeg input device name.")
    parser.add_argument("--mic-format", default=defaults["mic_format"], help="FFmpeg input format, e.g. dshow or alsa.")
    parser.add_argument("--speaker-device", default=defaults["speaker_device"], help="Output device. On Windows use sounddevice index, e.g. 3.")
    parser.add_argument("--speaker-format", default=defaults["speaker_format"], help="Optional FFmpeg output format. Leave empty on Windows to use sounddevice.")
    parser.add_argument("--speaker-rate", type=int, default=48000, help="Playback sample rate used by sounddevice output.")
    parser.add_argument("--manual-control", action="store_true", help="Start disconnected; press toggle key to connect/disconnect.")
    parser.add_argument("--toggle-key", default="c", help="Key used in manual mode to connect/disconnect.")
    parser.add_argument("--quit-key", default="q", help="Key used in manual mode to quit.")
    parser.add_argument("--verbose-events", action="store_true", help="Print raw Realtime event names for debugging.")
    return parser.parse_args()


async def post_turn(backend_url: str, session_id: str, device_token: str, role: str, text: str):
    """Envía al backend un turno final recibido por el data channel."""
    if not text.strip():
        return

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{backend_url}/realtime/sessions/{session_id}/turns",
            json={"role": role, "text": text},
            headers={"X-Device-Token": device_token},
        ) as response:
            if response.status >= 400:
                LOGGER.warning("Failed to persist turn: %s %s", response.status, await response.text())


async def exchange_sdp(backend_url: str, child_id: int, device_token: str, offer_sdp: str):
    """Intercambia el SDP offer local por el SDP answer creado por el backend."""
    if not offer_sdp.strip().startswith("v=0"):
        raise RuntimeError(f"Invalid local SDP offer generated. Length: {len(offer_sdp)}")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{backend_url}/realtime/sessions/{child_id}/sdp",
            data=offer_sdp,
            headers={
                "Content-Type": "application/sdp",
                "X-Device-Token": device_token,
            },
        ) as response:
            if response.status >= 400:
                raise RuntimeError(f"SDP exchange failed: {response.status} {await response.text()}")

            return response.headers["X-Session-Id"], await response.text()


class RealtimeEventLogger:
    """Convierte eventos Realtime verbosos en logs orientados a conversación."""

    def __init__(self, verbose_events: bool = False, output_state_callback=None):
        self.verbose_events = verbose_events
        self.output_state_callback = output_state_callback
        self.input_transcripts = {}
        self.output_transcripts = {}

    def handle(self, message: str):
        event = json.loads(message)
        event_type = event.get("type")

        if self.verbose_events:
            LOGGER.info("Realtime event: %s", event_type)

        if event_type == "error":
            LOGGER.error("Realtime error: %s", event.get("error") or event)
            return None, None

        if event_type == "session.created":
            LOGGER.info("Realtime session ready.")
            self._print_session_audio_config(event)
            return None, None

        if event_type == "session.updated":
            self._print_session_audio_config(event)
            return None, None

        if event_type in {"response.created", "response.output_item.added"}:
            self._set_output_active(True)
            return None, None

        if event_type == "input_audio_buffer.speech_started":
            LOGGER.info("Listening...")
            return None, None

        if event_type == "input_audio_buffer.speech_stopped":
            LOGGER.info("Processing speech...")
            return None, None

        if event_type == "output_audio_buffer.started":
            LOGGER.info("Playing assistant audio...")
            self._set_output_active(True)
            return None, None

        if event_type == "output_audio_buffer.stopped":
            self._set_output_active(False)
            return None, None

        if event_type == "output_audio_buffer.cleared":
            LOGGER.info("Assistant audio was cleared.")
            self._set_output_active(False)
            return None, None

        if event_type == "conversation.item.input_audio_transcription.delta":
            key = event.get("item_id") or "latest"
            self.input_transcripts[key] = self.input_transcripts.get(key, "") + event.get("delta", "")
            return None, None

        if event_type == "conversation.item.input_audio_transcription.completed":
            key = event.get("item_id") or "latest"
            text = event.get("transcript") or self.input_transcripts.pop(key, "")
            if text.strip():
                LOGGER.info("Child: %s", text.strip())
            return "child", text

        if event_type == "response.output_audio_transcript.delta":
            key = event.get("item_id") or event.get("response_id") or "latest"
            self.output_transcripts[key] = self.output_transcripts.get(key, "") + event.get("delta", "")
            return None, None

        if event_type in {"response.output_audio_transcript.done", "response.output_text.done"}:
            key = event.get("item_id") or event.get("response_id") or "latest"
            text = event.get("transcript") or event.get("text") or self.output_transcripts.pop(key, "")
            if text.strip():
                LOGGER.info("Assistant: %s", text.strip())
            return "assistant", text

        if event_type == "response.done":
            self._set_output_active(False)
            return None, None

        return None, None

    def _set_output_active(self, active):
        if self.output_state_callback:
            self.output_state_callback(active)

    def _print_session_audio_config(self, event):
        session = event.get("session") or {}
        audio = session.get("audio") or {}
        audio_input = audio.get("input") or {}
        turn_detection = audio_input.get("turn_detection") or {}

        if not turn_detection:
            return

        LOGGER.info(
            "Realtime VAD: threshold=%s, silence=%sms, interrupt_response=%s",
            turn_detection.get("threshold"),
            turn_detection.get("silence_duration_ms"),
            turn_detection.get("interrupt_response"),
        )


class SoundDeviceAudioPlayer:
    """Reproduce una pista remota WebRTC con sounddevice cuando FFmpeg no tiene salida."""

    def __init__(self, device=None, sample_rate=None):
        self.device = self._coerce_device(device)
        self.output_sample_rate = sample_rate
        self.stream = None
        self.task = None
        self.sample_rate = None
        self.channels = None
        self.frames_written = 0
        self.logged_frame_format = False

    @staticmethod
    def _coerce_device(device):
        if device in {None, ""}:
            return None
        try:
            return int(device)
        except ValueError:
            return device

    async def start(self, track):
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError as exc:
            raise RuntimeError(
                "Remote audio playback needs sounddevice and numpy on Windows. "
                "Install them with: pip install sounddevice numpy"
            ) from exc

        self.sd = sd
        self.np = np
        self.task = asyncio.create_task(self._play(track))
        self.task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task):
        if task.cancelled():
            return

        exc = task.exception()
        if exc:
            LOGGER.error("Audio playback stopped with error: %s", exc)

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        if self.stream:
            self.stream.stop()
            self.stream.close()

    async def _play(self, track):
        while True:
            frame = await track.recv()
            audio = frame.to_ndarray()
            channel_count = self._channel_count(frame)
            frame_sample_rate = frame.sample_rate or 48000
            sample_rate = self.output_sample_rate or frame_sample_rate
            audio = self._shape_audio(audio, channel_count)
            channels = audio.shape[1]
            audio = self._to_float32(audio)

            if not self.logged_frame_format:
                LOGGER.info(
                    "Audio frame: %s Hz, %s channel%s, %s -> %s output channel%s",
                    frame_sample_rate,
                    channel_count,
                    "s" if channel_count != 1 else "",
                    getattr(frame.format, "name", "unknown"),
                    channels,
                    "s" if channels != 1 else "",
                )
                self.logged_frame_format = True

            if not self.stream or sample_rate != self.sample_rate or channels != self.channels:
                if self.stream:
                    self.stream.stop()
                    self.stream.close()

                self.sample_rate = sample_rate
                self.channels = channels
                self.stream = self.sd.OutputStream(
                    samplerate=sample_rate,
                    channels=channels,
                    dtype="float32",
                    device=self.device,
                    blocksize=0,
                )
                self.stream.start()
                device_info = self.sd.query_devices(self.stream.device, "output")
                LOGGER.info(
                    "Audio output: %s (%s Hz, %s channel%s)",
                    device_info["name"],
                    sample_rate,
                    channels,
                    "s" if channels != 1 else "",
                )
                if frame_sample_rate != sample_rate:
                    LOGGER.info("Audio frame rate: %s Hz; forced playback rate: %s Hz", frame_sample_rate, sample_rate)

            await asyncio.to_thread(self.stream.write, audio)
            self.frames_written += len(audio)

    def _to_float32(self, audio):
        if audio.dtype == self.np.float32:
            return audio

        if self.np.issubdtype(audio.dtype, self.np.integer):
            scale = max(abs(self.np.iinfo(audio.dtype).min), self.np.iinfo(audio.dtype).max)
            return (audio.astype(self.np.float32) / scale).clip(-1.0, 1.0)

        return audio.astype(self.np.float32)

    def _channel_count(self, frame):
        try:
            return len(frame.layout.channels)
        except (AttributeError, TypeError):
            return 1

    def _shape_audio(self, audio, channel_count):
        if audio.ndim == 1:
            if channel_count > 1 and len(audio) % channel_count == 0:
                return audio.reshape(-1, channel_count)
            return audio.reshape(-1, 1)

        if audio.shape[0] == 1 and channel_count > 1 and audio.shape[1] % channel_count == 0:
            return audio.reshape(-1, channel_count)

        if audio.shape[0] == channel_count and audio.shape[0] < audio.shape[1]:
            return audio.T

        if audio.shape[0] <= 8 and audio.shape[0] < audio.shape[1]:
            return audio.T

        return audio


class MutingAudioTrack(MediaStreamTrack):
    """Proxy de micrófono que puede enviar silencio mientras conserva la conexión."""

    kind = "audio"

    def __init__(self, source):
        super().__init__()
        self.source = source
        self.muted = False

    def set_muted(self, muted):
        if muted != self.muted:
            LOGGER.info("Microphone muted while assistant speaks." if muted else "Microphone unmuted.")
        self.muted = muted

    async def recv(self):
        frame = await self.source.recv()
        if not self.muted:
            return frame
        return self._silent_frame(frame)

    def stop(self):
        super().stop()
        self.source.stop()

    def _silent_frame(self, frame):
        silence = np.zeros_like(frame.to_ndarray())
        layout = getattr(frame.layout, "name", "mono")
        silent = av.AudioFrame.from_ndarray(
            silence,
            format=frame.format.name,
            layout=layout,
        )
        silent.sample_rate = frame.sample_rate
        silent.pts = frame.pts
        silent.time_base = frame.time_base
        return silent


def validate_args(args):
    """Valida argumentos comunes antes de abrir dispositivos o red."""
    if not args.mic_device:
        raise RuntimeError(
            "--mic-device is required on Windows because DirectShow does not provide a portable default "
            "microphone alias. Run `ffmpeg -list_devices true -f dshow -i dummy` and then pass "
            '`--mic-device "audio=Exact Microphone Name"`.'
        )


def normalize_key(value):
    """Normaliza nombres simples de teclas para el modo manual."""
    if value.lower() in {"space", "espacio"}:
        return " "
    if value.lower() in {"enter", "return"}:
        return "\r"
    return value[:1].lower()


def read_key_blocking():
    """Lee una tecla sin requerir Enter en Windows y terminales POSIX."""
    if sys.platform.startswith("win"):
        import msvcrt

        return msvcrt.getwch().lower()

    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1).lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


async def read_key():
    """Lee una tecla sin bloquear el event loop."""
    return await asyncio.to_thread(read_key_blocking)


async def run_connected_session(args, stop_event=None):
    """Abre una sesión WebRTC y la mantiene viva hasta recibir stop_event."""
    stop_event = stop_event or asyncio.Event()
    pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=[]))
    channel = pc.createDataChannel("oai-events")
    session_id = None
    input_track = None
    muted_input_track = None
    unmute_task = None

    def clear_input_buffer():
        if channel.readyState == "open":
            channel.send(json.dumps({"type": "input_audio_buffer.clear"}))
            LOGGER.info("Cleared input audio buffer.")

    def set_assistant_output_active(active):
        nonlocal unmute_task

        if not muted_input_track:
            return

        if active:
            if unmute_task and not unmute_task.done():
                unmute_task.cancel()
            muted_input_track.set_muted(True)
            clear_input_buffer()
            return

        async def delayed_unmute():
            await asyncio.sleep(0.3)
            muted_input_track.set_muted(False)

        if unmute_task and not unmute_task.done():
            unmute_task.cancel()
        unmute_task = asyncio.create_task(delayed_unmute())

    event_logger = RealtimeEventLogger(args.verbose_events, set_assistant_output_active)

    try:
        player = MediaPlayer(args.mic_device, format=args.mic_format)
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            f"Could not open microphone {args.mic_device!r} with format {args.mic_format!r}. "
            "On Windows use --mic-format dshow and the exact DirectShow device name, for example "
            '--mic-device "audio=Microphone Name". List devices with: '
            "ffmpeg -list_devices true -f dshow -i dummy"
        ) from exc

    audio_outputs = []

    if player.audio:
        input_track = player.audio
        muted_input_track = MutingAudioTrack(input_track)
        pc.addTrack(muted_input_track)
    else:
        raise RuntimeError(f"No audio input found for device: {args.mic_device}")

    @pc.on("track")
    async def on_track(track):
        if args.verbose_events:
            LOGGER.info("Remote track received: %s", track.kind)

        if track.kind == "audio":
            if not args.speaker_format:
                LOGGER.info("Remote audio received. Using sounddevice playback.")
                player = SoundDeviceAudioPlayer(args.speaker_device, args.speaker_rate)
                await player.start(track)
                audio_outputs.append(player)
                return

            try:
                recorder = MediaRecorder(args.speaker_device, format=args.speaker_format)
            except ValueError as exc:
                raise RuntimeError(
                    f"Could not open speaker {args.speaker_device!r} with format {args.speaker_format!r}. "
                    "Set --speaker-format and --speaker-device for an FFmpeg output device available on this system."
                ) from exc

            recorder.addTrack(track)
            await recorder.start()
            audio_outputs.append(recorder)

    @channel.on("message")
    def on_message(message):
        role, text = event_logger.handle(message)

        if role and session_id:
            asyncio.create_task(post_turn(args.backend_url, session_id, args.device_token, role, text))

    @channel.on("open")
    def on_open():
        LOGGER.info("Realtime data channel open.")

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    offer_sdp = offer.sdp

    LOGGER.info("Generated SDP offer bytes: %s", len(offer_sdp.encode("utf-8")))
    session_id, answer_sdp = await exchange_sdp(
        args.backend_url,
        args.child_id,
        args.device_token,
        offer_sdp,
    )

    await pc.setRemoteDescription(RTCSessionDescription(sdp=answer_sdp, type="answer"))

    LOGGER.info("Connected. Session id: %s", session_id)
    if not args.manual_control:
        LOGGER.info("Press Ctrl+C to stop.")

    try:
        while not stop_event.is_set():
            await asyncio.sleep(0.2)
    finally:
        for output in audio_outputs:
            await output.stop()
        if unmute_task and not unmute_task.done():
            unmute_task.cancel()
        if input_track:
            input_track.stop()
        await pc.close()
        LOGGER.info("Disconnected.")


async def run_manual_control(args):
    """Controla conexión/desconexión con una tecla para el MVP."""
    toggle_key = normalize_key(args.toggle_key)
    quit_key = normalize_key(args.quit_key)
    stop_event = None
    session_task = None

    LOGGER.info("Manual control enabled. Press '%s' to connect/disconnect, '%s' to quit.", args.toggle_key, args.quit_key)

    while True:
        key = await read_key()

        if key == quit_key:
            if session_task and not session_task.done():
                stop_event.set()
                await session_task
            LOGGER.info("Bye.")
            return

        if key != toggle_key:
            continue

        if session_task and not session_task.done():
            LOGGER.info("Disconnecting...")
            stop_event.set()
            await session_task
            session_task = None
            stop_event = None
            continue

        LOGGER.info("Connecting...")
        stop_event = asyncio.Event()
        session_task = asyncio.create_task(run_connected_session(args, stop_event))

        def on_done(task):
            if task.cancelled():
                return
            exc = task.exception()
            if exc:
                LOGGER.error("Session stopped with error: %s", exc)

        session_task.add_done_callback(on_done)


def configure_logging():
    """Configura logs simples y legibles para uso en consola."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")


def mask_secret(value):
    """Enmascara tokens sin ocultar completamente qué valor está en uso."""
    if not value:
        return "<missing>"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def log_startup_config(args):
    """Imprime la configuración efectiva importante del cliente."""
    LOGGER.info("Innova WebRTC client version: %s", CLIENT_VERSION)
    LOGGER.info("Backend URL: %s", args.backend_url)
    LOGGER.info("Child id: %s", args.child_id)
    LOGGER.info("Device token: %s", mask_secret(args.device_token))
    LOGGER.info("Microphone: device=%r format=%r", args.mic_device, args.mic_format)
    LOGGER.info("Speaker: device=%r format=%r rate=%s", args.speaker_device, args.speaker_format, args.speaker_rate)
    LOGGER.info("Manual control: %s (toggle=%r quit=%r)", args.manual_control, args.toggle_key, args.quit_key)
    LOGGER.info("Realtime model/VAD config is controlled by backend environment variables.")


async def run():
    """Punto de entrada del cliente."""
    args = parse_args()

    configure_logging()
    log_startup_config(args)
    validate_args(args)

    if args.manual_control:
        await run_manual_control(args)
        return

    await run_connected_session(args)


if __name__ == "__main__":
    asyncio.run(run())
