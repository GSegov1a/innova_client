import argparse
import asyncio
import json
import os

import aiohttp
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaRecorder


def parse_args():
    """Lee la configuración necesaria para conectar el Raspberry al backend."""
    parser = argparse.ArgumentParser(description="Raspberry Pi WebRTC client for OpenAI Realtime.")
    parser.add_argument("--backend-url", default=os.getenv("BACKEND_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--child-id", type=int, default=int(os.getenv("CHILD_ID", "1")))
    parser.add_argument("--device-token", default=os.getenv("RASPBERRY_DEVICE_TOKEN"))
    parser.add_argument("--mic-device", default=os.getenv("MIC_DEVICE", "default"))
    parser.add_argument("--speaker-device", default=os.getenv("SPEAKER_DEVICE", "default"))
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


def handle_realtime_event(message: str):
    """Extrae turnos finales desde eventos del data channel de OpenAI Realtime."""
    event = json.loads(message)
    event_type = event.get("type")

    if event_type == "conversation.item.input_audio_transcription.completed":
        return "child", event.get("transcript", "")

    if event_type in {"response.output_audio_transcript.done", "response.output_text.done"}:
        return "assistant", event.get("transcript") or event.get("text", "")

    print("Realtime event:", event_type)
    return None, None


async def run():
    """Conecta micrófono/parlante del Raspberry con OpenAI Realtime vía WebRTC."""
    args = parse_args()

    if not args.device_token:
        raise RuntimeError("RASPBERRY_DEVICE_TOKEN is required")

    pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=[]))
    channel = pc.createDataChannel("oai-events")
    session_id = None

    player = MediaPlayer(args.mic_device, format="alsa")
    recorders = []

    if player.audio:
        pc.addTrack(player.audio)
    else:
        raise RuntimeError(f"No audio input found for device: {args.mic_device}")

    @pc.on("track")
    async def on_track(track):
        print("Remote track received:", track.kind)
        if track.kind == "audio":
            recorder = MediaRecorder(args.speaker_device, format="alsa")
            recorder.addTrack(track)
            await recorder.start()
            recorders.append(recorder)

    @channel.on("message")
    def on_message(message):
        role, text = handle_realtime_event(message)

        if role and session_id:
            asyncio.create_task(post_turn(args.backend_url, session_id, args.device_token, role, text))

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    session_id, answer_sdp = await exchange_sdp(
        args.backend_url,
        args.child_id,
        args.device_token,
        pc.localDescription.sdp,
    )

    await pc.setRemoteDescription(RTCSessionDescription(sdp=answer_sdp, type="answer"))

    print("Connected. Session id:", session_id)
    print("Press Ctrl+C to stop.")

    try:
        while True:
            await asyncio.sleep(1)
    finally:
        for recorder in recorders:
            await recorder.stop()
        await pc.close()


if __name__ == "__main__":
    asyncio.run(run())
