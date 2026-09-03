"""
Voice Preloader
===============
Pre-generates all Telugu reminder MP3s at startup
so they're instantly available when a reminder fires.

Safe version:
- Does not crash if Google TTS fails
- Does not stop on a single MP3 failure
- Runs in background thread
"""

import os
import logging

logger = logging.getLogger(__name__)

# Generic placeholder name for preloaded audio
PLACEHOLDER = "గారూ"

TELUGU_TEXTS = {
    'morning': [
        "శుభోదయం. మీ మందు తీసుకునే సమయం వచ్చింది.",
        "దయచేసి మీ మందు తీసుకోవడం మర్చిపోవద్దు.",
        "మీ మందు ఇంకా తీసుకోలేదు. దయచేసి ఇప్పుడు తీసుకోండి.",
        "మీ ఆరోగ్యం కోసం మందు తీసుకోవడం చాలా ముఖ్యం.",
        "మీ మందు ఇంకా పెండింగ్‌లో ఉంది. వెంటనే తీసుకోండి.",
        "హెచ్చరిక. మీ మందు సమయం చాలా దాటింది. దయచేసి వెంటనే మందు తీసుకోండి.",
    ],
    'afternoon': [
        "నమస్కారం. మీ మందు సమయం వచ్చింది.",
        "దయచేసి మీ మందు తీసుకోవడం మర్చిపోవద్దు.",
        "మీ మందు ఇంకా తీసుకోలేదు. దయచేసి తీసుకోండి.",
        "మీ ఆరోగ్య సంరక్షణ కోసం మందు తీసుకోవడం అవసరం.",
        "మీ మందు ఇంకా పెండింగ్‌లో ఉంది.",
        "హెచ్చరిక. మందు సమయం చాలా దాటింది.",
    ],
    'night': [
        "శుభ సాయంత్రం. మీ మందు తీసుకునే సమయం వచ్చింది.",
        "దయచేసి మీ రాత్రి మందు తీసుకోండి.",
        "మీ మందు ఇంకా తీసుకోలేదు.",
        "మీ ఆరోగ్యం కోసం మందు తీసుకోవడం అవసరం.",
        "మీ మందు ఇంకా పెండింగ్‌లో ఉంది.",
        "హెచ్చరిక. మందు సమయం చాలా దాటింది. దయచేసి వెంటనే మందు తీసుకోండి.",
    ],
}


def _audio_dir():
    from flask import current_app

    audio_dir = current_app.config.get(
        'AUDIO_DIR',
        'app/static/audio'
    )

    os.makedirs(audio_dir, exist_ok=True)
    return audio_dir


def _key(tod: str, level: int) -> str:
    """
    Returns a stable filename key
    """
    return f"te_{tod}_L{level}"


def get_preloaded_url(tod: str, level: int) -> str:
    """
    Return URL of preloaded MP3 if it exists.
    """
    filename = f"reminder_{_key(tod, level)}.mp3"

    audio_dir = _audio_dir()
    filepath = os.path.join(audio_dir, filename)

    if os.path.exists(filepath):
        return f"/static/audio/{filename}"

    return ""


def preload_all(app):
    """
    Generate all Telugu reminder MP3s in background.
    Safe against internet/gTTS failures.
    """

    import threading

    def _worker():
        with app.app_context():

            try:
                from gtts import gTTS

                audio_dir = _audio_dir()
                generated = 0

                for tod, texts in TELUGU_TEXTS.items():

                    for i, text in enumerate(texts):

                        level = i + 1

                        filename = (
                            f"reminder_{_key(tod, level)}.mp3"
                        )

                        filepath = os.path.join(
                            audio_dir,
                            filename
                        )

                        # Skip existing files
                        if os.path.exists(filepath):
                            continue

                        try:
                            tts = gTTS(
                                text=text,
                                lang='te',
                                slow=False
                            )

                            tts.save(filepath)

                            generated += 1

                        except Exception as e:
                            logger.warning(
                                f"Failed generating "
                                f"{filename}: {e}"
                            )
                            continue

                if generated > 0:
                    logger.info(
                        f"Voice preloader generated "
                        f"{generated} Telugu MP3s"
                    )
                else:
                    logger.info(
                        "Voice preloader: all MP3s already cached"
                    )

            except Exception as e:
                logger.warning(
                    f"Voice preloader error: {e}"
                )

    threading.Thread(
        target=_worker,
        daemon=True
    ).start()