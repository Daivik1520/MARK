"""
MARK — Streaming TTS Engine
Splits text into sentences and generates audio chunks independently.
First sentence starts playing within ~300ms, giving near-zero perceived latency.
Designed for real-time voice conversations and future phone calling support.
Includes speech naturalizer for human-like delivery with fillers and pauses.
"""

import re
import asyncio
import base64
import edge_tts


# ─────────────────────────────────────────────
# SPEECH NATURALIZER
# Makes AI text sound more human when spoken by TTS.
# Converts written patterns into speech-friendly forms.
# ─────────────────────────────────────────────

def naturalize_for_speech(text):
    """
    Transform AI text into more natural speech.
    - Converts '...' into natural breath pauses
    - Ensures fillers (umm, hmm) get proper spacing for TTS to render naturally
    - Removes any remaining markdown artifacts
    - Adds micro-pauses around parenthetical thoughts
    """
    if not text:
        return text

    # Remove markdown formatting that sounds bad in speech
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # bold
    text = re.sub(r'\*(.+?)\*', r'\1', text)       # italic
    text = re.sub(r'`(.+?)`', r'\1', text)         # inline code
    text = re.sub(r'```[\s\S]*?```', '', text)      # code blocks
    text = re.sub(r'#+\s*', '', text)               # headers
    text = re.sub(r'[-•]\s*', '', text)             # bullet points
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # links

    # Convert ellipsis into comma-pause for natural breath
    # "well... let me see" → "well, let me see"
    # "hmm... okay" → "hmm, okay"
    text = re.sub(r'\.{2,}\s*', ', ', text)

    # Ensure fillers get natural comma separation so TTS pauses slightly
    # "umm I think" → "umm, I think"
    filler_pattern = r'\b(umm|hmm|uh|ah|oh|well|huh|mhm|ehh|aah)\b(?!\s*[,.\-!?])'
    text = re.sub(filler_pattern, r'\1,', text, flags=re.IGNORECASE)

    # Natural pauses after discourse markers
    # "okay so I checked" → "okay, so I checked"
    # "alright here's" → "alright, here's"
    markers = r'\b(okay so|alright so|right so|so basically|I mean|you know|let me think|one sec|got it|there you go)\b(?!\s*[,.])'
    text = re.sub(markers, r'\1,', text, flags=re.IGNORECASE)

    # Em-dash to comma for natural pauses
    text = re.sub(r'\s*—\s*', ', ', text)
    text = re.sub(r'\s*--\s*', ', ', text)

    # Clean up formatting
    text = re.sub(r'\n{2,}', '. ', text)
    text = re.sub(r'\n', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r',\s*,', ',', text)  # double commas
    text = re.sub(r',\s*\.', '.', text)  # comma before period

    return text.strip()


# ─────────────────────────────────────────────
# SENTENCE SPLITTER
# ─────────────────────────────────────────────

# Split on sentence boundaries but keep the text natural
_SENTENCE_RE = re.compile(
    r'(?<=[.!?])\s+'           # After . ! ? followed by space
    r'|(?<=[.!?])(?=[A-Z"])'   # After . ! ? followed by capital letter or quote
    r'|(?<=\n)\s*'             # After newline
)

# Minimum chars for a chunk to be worth generating audio for
_MIN_CHUNK = 8
# Maximum chars per chunk (split long sentences)
_MAX_CHUNK = 200


def split_into_chunks(text):
    """
    Split text into natural speech chunks optimized for streaming TTS.
    Applies speech naturalization before splitting.
    Returns list of text strings, each suitable for independent TTS generation.
    """
    if not text or not text.strip():
        return []

    # Naturalize the text for speech first
    text = naturalize_for_speech(text)

    # Split on sentence boundaries
    raw_chunks = _SENTENCE_RE.split(text)

    # Process chunks: merge tiny ones, split huge ones
    chunks = []
    buffer = ""

    for piece in raw_chunks:
        piece = piece.strip()
        if not piece:
            continue

        if len(buffer) + len(piece) < _MIN_CHUNK:
            buffer += (" " if buffer else "") + piece
            continue

        if buffer:
            if len(buffer) >= _MIN_CHUNK:
                chunks.append(buffer)
                buffer = ""
            else:
                piece = buffer + " " + piece
                buffer = ""

        # Split overly long pieces at commas or conjunctions
        if len(piece) > _MAX_CHUNK:
            sub_parts = re.split(r'(?<=[,;:])\s+|(?<=\band\b)\s+|(?<=\bbut\b)\s+|(?<=\bthen\b)\s+', piece)
            sub_buffer = ""
            for sp in sub_parts:
                if len(sub_buffer) + len(sp) < _MAX_CHUNK:
                    sub_buffer += (" " if sub_buffer else "") + sp
                else:
                    if sub_buffer:
                        chunks.append(sub_buffer)
                    sub_buffer = sp
            if sub_buffer:
                chunks.append(sub_buffer)
        else:
            chunks.append(piece)

    if buffer and len(buffer) >= _MIN_CHUNK:
        chunks.append(buffer)
    elif buffer and chunks:
        chunks[-1] += " " + buffer
    elif buffer:
        chunks.append(buffer)

    return [c.strip() for c in chunks if c.strip()]


# ─────────────────────────────────────────────
# STREAMING TTS GENERATION
# ─────────────────────────────────────────────

async def generate_tts_chunk(text, voice, rate="+10%", pitch="+0Hz"):
    """
    Generate TTS audio for a single text chunk.
    Returns base64-encoded MP3 audio string, or empty string on error.
    """
    if not text or not text.strip():
        return ""

    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        audio_buffer = bytearray()

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.extend(chunk["data"])

        if not audio_buffer:
            return ""

        return base64.b64encode(bytes(audio_buffer)).decode("utf-8")
    except Exception as e:
        print(f"  TTS chunk error: {e}")
        return ""


async def stream_tts_chunks(text, voice, rate="+10%", pitch="+0Hz"):
    """
    Generator that yields (chunk_index, total_chunks, text_chunk, audio_base64)
    for each sentence in the text. Yields as soon as each chunk is ready.
    """
    chunks = split_into_chunks(text)
    if not chunks:
        return

    total = len(chunks)

    for i, chunk_text in enumerate(chunks):
        audio_b64 = await generate_tts_chunk(chunk_text, voice, rate, pitch)
        if audio_b64:
            yield {
                "index": i,
                "total": total,
                "text": chunk_text,
                "audio": audio_b64,
                "final": (i == total - 1),
            }


async def generate_tts_first_chunk(text, voice, rate="+10%", pitch="+0Hz"):
    """
    Generate ONLY the first sentence's audio as fast as possible.
    Returns (first_chunk_audio_b64, remaining_text).
    Used for ultra-low latency: start speaking immediately, generate rest in background.
    """
    chunks = split_into_chunks(text)
    if not chunks:
        return "", ""

    first_audio = await generate_tts_chunk(chunks[0], voice, rate, pitch)
    remaining = " ".join(chunks[1:]) if len(chunks) > 1 else ""

    return first_audio, remaining
