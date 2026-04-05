"""
MARK — TTS Engine
High-quality text-to-speech using edge-tts with dynamic voice/language switching.
Supports English, Telugu, Hindi, and many more via Microsoft Edge TTS.
"""

import asyncio
import base64
import io
import edge_tts
from dotenv import load_dotenv

load_dotenv()

# ── Curated voice list (fast, high-quality voices) ──
AVAILABLE_VOICES = [
    # ── English ──
    {"id": "en-US-GuyNeural",       "name": "Guy (US Male)",        "lang": "English",  "locale": "en-US"},
    {"id": "en-US-AndrewNeural",    "name": "Andrew (US Male)",     "lang": "English",  "locale": "en-US"},
    {"id": "en-US-ChristopherNeural","name": "Christopher (US Male)","lang": "English", "locale": "en-US"},
    {"id": "en-US-EricNeural",      "name": "Eric (US Male)",       "lang": "English",  "locale": "en-US"},
    {"id": "en-US-JennyNeural",     "name": "Jenny (US Female)",    "lang": "English",  "locale": "en-US"},
    {"id": "en-US-AriaNeural",      "name": "Aria (US Female)",     "lang": "English",  "locale": "en-US"},
    {"id": "en-GB-RyanNeural",      "name": "Ryan (UK Male)",       "lang": "English",  "locale": "en-GB"},
    {"id": "en-GB-SoniaNeural",     "name": "Sonia (UK Female)",    "lang": "English",  "locale": "en-GB"},
    {"id": "en-AU-WilliamNeural",   "name": "William (AU Male)",    "lang": "English",  "locale": "en-AU"},
    # ── Telugu ──
    {"id": "te-IN-MohanNeural",     "name": "Mohan (Telugu Male)",  "lang": "Telugu",   "locale": "te-IN"},
    {"id": "te-IN-ShrutiNeural",    "name": "Shruti (Telugu Female)","lang": "Telugu",  "locale": "te-IN"},
    # ── Hindi ──
    {"id": "hi-IN-MadhurNeural",    "name": "Madhur (Hindi Male)",  "lang": "Hindi",    "locale": "hi-IN"},
    {"id": "hi-IN-SwaraNeural",     "name": "Swara (Hindi Female)", "lang": "Hindi",    "locale": "hi-IN"},
    # ── Tamil ──
    {"id": "ta-IN-ValluvarNeural",  "name": "Valluvar (Tamil Male)","lang": "Tamil",    "locale": "ta-IN"},
    {"id": "ta-IN-PallaviNeural",   "name": "Pallavi (Tamil Female)","lang": "Tamil",   "locale": "ta-IN"},
]

# ── Current TTS settings (runtime-mutable) ──
# AndrewNeural has the most natural, conversational delivery
_current_voice = "en-US-AndrewNeural"
_current_rate  = "+5%"    # Slightly fast but still natural (not robotic)
_current_pitch = "-2Hz"   # Very slight lower pitch — sounds warmer/closer
_current_lang  = "en-US"  # For speech recognition language hint


def get_current_voice() -> str:
    return _current_voice

def get_current_lang() -> str:
    return _current_lang

def get_available_voices() -> list:
    return AVAILABLE_VOICES

def set_voice(voice_id: str) -> bool:
    """Set active TTS voice by ID. Returns True on success."""
    global _current_voice, _current_lang
    for v in AVAILABLE_VOICES:
        if v["id"] == voice_id:
            _current_voice = voice_id
            _current_lang = v["locale"]
            print(f"  🔊 Voice changed to: {v['name']} ({voice_id})")
            return True
    return False

def set_rate(rate: str):
    """Set speech rate, e.g. '+10%', '-5%', '+25%'"""
    global _current_rate
    _current_rate = rate

def set_pitch(pitch: str):
    """Set speech pitch, e.g. '+0Hz', '+5Hz', '-10Hz'"""
    global _current_pitch
    _current_pitch = pitch


async def _generate_speech(text: str) -> bytes:
    """Generate speech audio bytes from text using current voice settings."""
    communicate = edge_tts.Communicate(
        text,
        _current_voice,
        rate=_current_rate,
        pitch=_current_pitch
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
        # Naturalize text for human-like speech delivery
        from core.streaming_tts import naturalize_for_speech
        text = naturalize_for_speech(text)

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
