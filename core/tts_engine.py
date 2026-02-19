"""
MARK — TTS Engine
High-quality text-to-speech using edge-tts, returning base64 audio.
"""

import asyncio
import base64
import io
import edge_tts

VOICE = "en-US-GuyNeural"
RATE = "+10%"
PITCH = "+0Hz"


async def _generate_speech(text: str) -> bytes:
    """Generate speech audio bytes from text."""
    communicate = edge_tts.Communicate(
        text,
        VOICE,
        rate=RATE,
        pitch=PITCH
    )

    audio_buffer = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.extend(chunk["data"])

    return bytes(audio_buffer)


def text_to_speech_base64(text: str) -> str:
    """Convert text to speech and return base64-encoded MP3 audio."""
    if not text or not text.strip():
        return ""

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio_bytes = loop.run_until_complete(_generate_speech(text))
        loop.close()

        if not audio_bytes:
            return ""

        return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        print(f"TTS Error: {e}")
        return ""


def get_available_voices():
    """List available edge-tts voices."""
    async def _list():
        voices = await edge_tts.list_voices()
        return [{"name": v["ShortName"], "gender": v["Gender"], "locale": v["Locale"]} for v in voices]

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(_list())
    loop.close()
    return result
