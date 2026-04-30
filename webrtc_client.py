import argparse
import asyncio
import json
import os
import sys

import aiohttp
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaRecorder


CLIENT_VERSION = "2026-04-30-packed-audio-layout"


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
    parser = argparse.ArgumentParser(description="WebRTC audio client for OpenAI Realtime.")
    parser.add_argument("--backend-url", default=os.getenv("BACKEND_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--child-id", type=int, default=int(os.getenv("CHILD_ID", "1")))
    parser.add_argument("--device-token", default=os.getenv("RASPBERRY_DEVICE_TOKEN"))
    parser.add_argument("--mic-device", default=os.getenv("MIC_DEVICE", defaults["mic_device"]))
    parser.add_argument("--mic-format", default=os.getenv("MIC_FORMAT", defaults["mic_format"]))
    parser.add_argument("--speaker-device", default=os.getenv("SPEAKER_DEVICE", defaults["speaker_device"]))
    parser.add_argument("--speaker-format", default=os.getenv("SPEAKER_FORMAT", defaults["speaker_format"]))
    parser.add_argument("--speaker-rate", type=int, default=int(os.getenv("SPEAKER_RATE", "48000")))
    parser.add_argument("--verbose-events", action="store_true")
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
                print("Failed to persist turn:", response.status, await response.text())


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

    def __init__(self, verbose_events: bool = False):
        self.verbose_events = verbose_events
        self.input_transcripts = {}
        self.output_transcripts = {}

    def handle(self, message: str):
        event = json.loads(message)
        event_type = event.get("type")

        if self.verbose_events:
            print("Realtime event:", event_type)

        if event_type == "session.created":
            print("Realtime session ready.")
            return None, None

        if event_type == "input_audio_buffer.speech_started":
            print("Listening...")
            return None, None

        if event_type == "input_audio_buffer.speech_stopped":
            print("Processing speech...")
            return None, None

        if event_type == "output_audio_buffer.started":
            print("Playing assistant audio...")
            return None, None

        if event_type == "conversation.item.input_audio_transcription.delta":
            key = event.get("item_id") or "latest"
            self.input_transcripts[key] = self.input_transcripts.get(key, "") + event.get("delta", "")
            return None, None

        if event_type == "conversation.item.input_audio_transcription.completed":
            key = event.get("item_id") or "latest"
            text = event.get("transcript") or self.input_transcripts.pop(key, "")
            if text.strip():
                print(f"Child: {text.strip()}")
            return "child", text

        if event_type == "response.output_audio_transcript.delta":
            key = event.get("item_id") or event.get("response_id") or "latest"
            self.output_transcripts[key] = self.output_transcripts.get(key, "") + event.get("delta", "")
            return None, None

        if event_type in {"response.output_audio_transcript.done", "response.output_text.done"}:
            key = event.get("item_id") or event.get("response_id") or "latest"
            text = event.get("transcript") or event.get("text") or self.output_transcripts.pop(key, "")
            if text.strip():
                print(f"Assistant: {text.strip()}")
            return "assistant", text

        return None, None


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
            print(f"Audio playback stopped with error: {exc}")

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
                print(
                    "Audio frame:",
                    f"{frame_sample_rate} Hz, {channel_count} channel{'s' if channel_count != 1 else ''},",
                    f"{getattr(frame.format, 'name', 'unknown')} -> {channels} output channel{'s' if channels != 1 else ''}",
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
                print(
                    "Audio output:",
                    f"{device_info['name']} ({sample_rate} Hz, {channels} channel{'s' if channels != 1 else ''})",
                )
                if frame_sample_rate != sample_rate:
                    print(f"Audio frame rate: {frame_sample_rate} Hz; forced playback rate: {sample_rate} Hz")

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


async def run():
    """Conecta micrófono/parlante del cliente con OpenAI Realtime vía WebRTC."""
    args = parse_args()

    print("Innova WebRTC client version:", CLIENT_VERSION)

    if not args.device_token:
        raise RuntimeError("RASPBERRY_DEVICE_TOKEN is required")

    if not args.mic_device:
        raise RuntimeError(
            "MIC_DEVICE is required on Windows because DirectShow does not provide a portable default "
            "microphone alias. Run `ffmpeg -list_devices true -f dshow -i dummy` and then pass "
            '`--mic-device "audio=Exact Microphone Name"`.'
        )

    pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=[]))
    channel = pc.createDataChannel("oai-events")
    event_logger = RealtimeEventLogger(args.verbose_events)
    session_id = None

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
        pc.addTrack(player.audio)
    else:
        raise RuntimeError(f"No audio input found for device: {args.mic_device}")

    @pc.on("track")
    async def on_track(track):
        if args.verbose_events:
            print("Remote track received:", track.kind)

        if track.kind == "audio":
            if not args.speaker_format:
                print("Remote audio received. Using sounddevice playback.")
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

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    offer_sdp = offer.sdp

    print("Generated SDP offer bytes:", len(offer_sdp.encode("utf-8")))
    session_id, answer_sdp = await exchange_sdp(
        args.backend_url,
        args.child_id,
        args.device_token,
        offer_sdp,
    )

    await pc.setRemoteDescription(RTCSessionDescription(sdp=answer_sdp, type="answer"))

    print("Connected. Session id:", session_id)
    print("Press Ctrl+C to stop.")

    try:
        while True:
            await asyncio.sleep(1)
    finally:
        for output in audio_outputs:
            await output.stop()
        await pc.close()


if __name__ == "__main__":
    asyncio.run(run())
