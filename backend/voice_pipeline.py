"""ElevenLabs voice pipeline — streams audio bytes for low-latency TTS."""
import os
import httpx
from typing import AsyncGenerator

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "nPczCjzI2devNBz1zQrb")  # Brian

TTS_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream"

VOICE_SETTINGS = {
    "stability": 0.75,
    "similarity_boost": 0.85,
    "style": 0.2,
    "use_speaker_boost": True,
}

HEADERS = {
    "xi-api-key": ELEVENLABS_API_KEY,
    "Content-Type": "application/json",
    "Accept": "audio/mpeg",
}


async def synthesize_stream(text: str) -> AsyncGenerator[bytes, None]:
    """Stream MP3 audio bytes from ElevenLabs for the given text."""
    if not ELEVENLABS_API_KEY:
        return

    payload = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": VOICE_SETTINGS,
        "output_format": "mp3_44100_128",
    }

    async with httpx.AsyncClient(timeout=30.0) as http:
        async with http.stream("POST", TTS_URL, headers=HEADERS, json=payload) as resp:
            if resp.status_code == 200:
                async for chunk in resp.aiter_bytes(chunk_size=4096):
                    if chunk:
                        yield chunk


async def synthesize_full(text: str) -> bytes:
    """Return the complete audio bytes for the given text."""
    audio = b""
    async for chunk in synthesize_stream(text):
        audio += chunk
    return audio
