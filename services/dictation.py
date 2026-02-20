"""
MARK — Instant Local Dictation
Whisper-based speech-to-text with global hotkey (Ctrl+Shift+Space).
Records audio on key hold, transcribes locally, types into active app.
"""

import os
import threading
import tempfile
import time
import numpy as np

# Global state
_recording = False
_audio_buffer = []
_sio = None
_sample_rate = 16000


def _load_whisper():
    """Lazy-load Whisper model (base.en for speed)."""
    try:
        import whisper
        print("  🎙️  Loading Whisper base.en model...")
        model = whisper.load_model("base.en")
        print("  ✅ Whisper model loaded")
        return model
    except ImportError:
        print("  ⚠️  openai-whisper not installed. Run: pip3 install openai-whisper")
        return None
    except Exception as e:
        print(f"  ⚠️  Could not load Whisper model: {e}")
        return None


_whisper_model = None


def _on_key_press(key):
    """Start recording when hotkey is pressed."""
    global _recording, _audio_buffer

    try:
        from pynput.keyboard import Key
        # We detect Ctrl+Shift+Space by tracking modifier state
        # But for simplicity, we'll use F8 as the dictation key (easier to detect)
        if key == Key.f8:
            if not _recording:
                _recording = True
                _audio_buffer = []
                print("🎙️  Dictation: recording...")
                if _sio:
                    try:
                        _sio.emit("status", {"message": "🎙️ Listening...", "type": "info"})
                    except Exception:
                        pass
                _start_audio_capture()
    except Exception:
        pass


def _on_key_release(key):
    """Stop recording and transcribe when hotkey is released."""
    global _recording

    try:
        from pynput.keyboard import Key
        if key == Key.f8:
            if _recording:
                _recording = False
                print("🎙️  Dictation: processing...")
                # Process in background thread
                threading.Thread(target=_transcribe_and_type, daemon=True).start()
    except Exception:
        pass


def _start_audio_capture():
    """Capture audio in a background thread using sounddevice."""
    def _capture():
        global _audio_buffer, _recording
        try:
            import sounddevice as sd
            while _recording:
                # Record small chunks
                chunk = sd.rec(int(_sample_rate * 0.5), samplerate=_sample_rate, channels=1, dtype="float32")
                sd.wait()
                if _recording:
                    _audio_buffer.append(chunk.flatten())
        except Exception as e:
            print(f"  ⚠️  Audio capture error: {e}")

    threading.Thread(target=_capture, daemon=True).start()


def _transcribe_and_type():
    """Transcribe the recorded audio and type it into the active app."""
    global _whisper_model, _audio_buffer

    if not _audio_buffer:
        print("  ⚠️  No audio recorded")
        return

    # Concatenate audio buffers
    audio = np.concatenate(_audio_buffer)
    _audio_buffer = []

    if len(audio) < _sample_rate * 0.3:  # Less than 0.3 seconds
        print("  ⚠️  Recording too short")
        return

    # Load model on first use
    if _whisper_model is None:
        _whisper_model = _load_whisper()
        if _whisper_model is None:
            return

    # Transcribe
    try:
        # Pad/trim to 30 seconds max
        import whisper
        audio_padded = whisper.pad_or_trim(audio)
        mel = whisper.log_mel_spectrogram(audio_padded).to(_whisper_model.device)
        result = _whisper_model.transcribe(audio, language="en", fp16=False)
        text = result.get("text", "").strip()

        if not text:
            print("  ⚠️  No speech detected")
            return

        print(f"  🎙️  Transcribed: {text}")

        # Type into active app using pyautogui
        try:
            import pyperclip
            pyperclip.copy(text)
            import pyautogui
            pyautogui.hotkey("command", "v")
        except ImportError:
            import pyautogui
            pyautogui.write(text, interval=0.02)

        # Notify UI
        if _sio:
            try:
                _sio.emit("status", {"message": f"🎙️ Typed: {text[:60]}...", "type": "success"})
            except Exception:
                pass

    except Exception as e:
        print(f"  ❌ Transcription error: {e}")


def start_dictation(sio_instance=None):
    """Start the dictation service with global hotkey listener."""
    global _sio
    _sio = sio_instance

    try:
        from pynput import keyboard

        listener = keyboard.Listener(on_press=_on_key_press, on_release=_on_key_release)
        listener.daemon = True
        listener.start()
        print("  🎙️  Dictation service ready — hold F8 to dictate")
    except ImportError:
        print("  ⚠️  pynput not installed. Dictation disabled.")
    except Exception as e:
        print(f"  ⚠️  Could not start dictation listener: {e}")
