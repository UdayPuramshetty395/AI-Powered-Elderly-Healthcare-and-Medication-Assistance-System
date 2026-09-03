"""
Voice Scheduler — plays Telugu audio from PC speakers via Windows MCI.
Called by fire_reminder() at exact scheduled time.
Uses edge-tts (Microsoft Neural Telugu) + Windows built-in audio (no extra libs).
"""
import os
import ctypes
import logging
import asyncio
import tempfile
import threading

logger = logging.getLogger(__name__)

VOICE = "te-IN-ShrutiNeural"

MESSAGES = [
    "మీరు మందులు తీసుకునే సమయం అయింది.",
    "దయచేసి మందులు తీసుకోండి.",
    "మీ మందులు ఇంకా తీసుకోలేదు. వెంటనే తీసుకోండి.",
    "ఇది ముఖ్యమైన గుర్తుచేయింపు. దయచేసి ఇప్పుడే మందులు తీసుకోండి.",
    "ఇది సీరియస్ రిమైండర్. మీ ఆరోగ్యం కోసం వెంటనే మందులు తీసుకోండి.",
    "హెచ్చరిక. మందు సమయం చాలా దాటింది. వెంటనే తీసుకోండి.",
]

_playing = threading.Lock()


def _mci_play(filepath: str) -> bool:
    """Play MP3 using Windows built-in MCI — works from any thread."""
    try:
        mci = ctypes.windll.winmm.mciSendStringW
        alias = "eldercare_voice"
        mci(f'close {alias}', None, 0, None)
        r1 = mci(f'open "{filepath}" type mpegvideo alias {alias}', None, 0, None)
        if r1 != 0:
            logger.error(f"MCI open failed: {r1}")
            return False
        r2 = mci(f'play {alias} wait', None, 0, None)
        mci(f'close {alias}', None, 0, None)
        return r2 == 0
    except Exception as e:
        logger.error(f"MCI error: {e}")
        return False


async def _generate(text: str) -> str:
    """Generate Telugu MP3 using Microsoft Neural TTS."""
    import edge_tts
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False,
                                     prefix="eldercare_",
                                     dir=tempfile.gettempdir()) as f:
        tmp = f.name
    await edge_tts.Communicate(text, VOICE).save(tmp)
    return tmp


def play_voice_for_reminder(elder_name: str, medicine_name: str,
                             reminder_num: int = 1):
    """
    Called by fire_reminder() at EXACT scheduled time.
    Plays Telugu voice from PC speakers — no browser needed.
    """
    def _run():
        if not _playing.acquire(blocking=False):
            logger.info("Voice already playing — skip")
            return
        tmp = None
        try:
            idx  = min(reminder_num - 1, len(MESSAGES) - 1)
            msg  = MESSAGES[idx]
            text = f"{elder_name} గారూ. {msg} మందు: {medicine_name}."

            logger.info(f"🔊 Voice R{reminder_num}: {text[:70]}")

            # Generate MP3
            tmp = asyncio.run(_generate(text))
            size = os.path.getsize(tmp) if tmp and os.path.exists(tmp) else 0
            logger.info(f"   MP3 ready: {size} bytes")

            if size == 0:
                logger.error("   MP3 generation failed")
                return

            # Play via Windows MCI
            ok = _mci_play(tmp)
            if ok:
                logger.info("   ✅ Played successfully")
            else:
                logger.warning("   MCI failed — trying os.startfile")
                os.startfile(tmp)
                import time; time.sleep(6)

        except Exception as e:
            logger.error(f"Voice error: {e}")
        finally:
            _playing.release()
            if tmp and os.path.exists(tmp):
                try: os.unlink(tmp)
                except Exception: pass

    threading.Thread(target=_run, daemon=True, name="VoiceThread").start()


def reset_voice_state():
    logger.info("Voice scheduler: new day")
