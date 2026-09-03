"""
Voice API — reminder audio generation.
POST /api/voice/generate  — generate a speech MP3 and return its URL
GET  /api/voice/reminder-audio — generate + return the audio file directly

The preferred backend is Sarvam AI Bulbul for more natural Indic speech.
If the API key is unavailable, the code falls back to edge-tts and then gTTS.
Generated files are cached in app/static/audio/
"""

import os
import base64
import hashlib
import logging

from flask import (
    Blueprint,
    request,
    jsonify,
    current_app,
    send_file
)

from flask_jwt_extended import jwt_required

voice_api_bp = Blueprint('voice_api', __name__)
logger = logging.getLogger(__name__)


def _audio_path(filename: str) -> str:
    """Return full path to audio file."""
    audio_dir = current_app.config.get(
        'AUDIO_DIR',
        'app/static/audio'
    )

    os.makedirs(audio_dir, exist_ok=True)

    return os.path.join(audio_dir, filename)


def _make_filename(text: str, lang: str) -> str:
    """Generate deterministic filename from text."""
    hash_value = hashlib.md5(
        f"{lang}:{text}".encode("utf-8")
    ).hexdigest()[:14]

    return f"voice_{lang}_{hash_value}.mp3"


def _select_voice_for_lang(lang: str) -> str:
    """Pick a more natural regional voice when available."""
    if lang == "te":
        return "te-IN-ShrutiNeural"
    if lang == "en":
        return "en-IN-NeerjaNeural"
    return "en-US-JennyNeural"


def _select_speaker_for_lang(lang: str) -> str:
    """Pick a Bulbul speaker that matches the language and sounds natural."""
    if lang == "te":
        return "shubh"
    if lang == "en":
        return "shubh"
    return "shubh"


def _generate_sarvam(text: str, lang: str, filepath: str) -> None:
    """Generate audio using Sarvam AI Bulbul and save it to disk."""
    api_key = current_app.config.get('SARVAM_API_KEY') or os.environ.get('SARVAM_API_KEY')
    if not api_key:
        raise RuntimeError('SARVAM_API_KEY is not configured')

    from sarvamai import SarvamAI

    model = current_app.config.get('SARVAM_TTS_MODEL', 'bulbul:v3')
    language_code = {
        'te': 'te-IN',
        'en': 'en-IN'
    }.get(lang, 'en-IN')

    client = SarvamAI(api_subscription_key=api_key)
    response = client.text_to_speech.convert(
        text=text,
        target_language_code=language_code,
        speaker=_select_speaker_for_lang(lang),
        model=model,
        pace=0.98,
        output_audio_codec='mp3'
    )

    if not getattr(response, 'audios', None):
        raise RuntimeError('Sarvam AI returned no audio payload')

    with open(filepath, 'wb') as audio_file:
        audio_file.write(base64.b64decode(response.audios[0]))


def _generate_gtts(text: str, lang: str) -> dict:
    """
    Prefer gTTS for a natural-enough Telugu voice here,
    then fall back to edge-tts and Sarvam AI if needed.
    """

    filename = _make_filename(text, lang)
    filepath = _audio_path(filename)

    # Return cached file if available
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        return {
            "success": True,
            "filename": filename,
            "url": f"/static/audio/{filename}",
            "cached": True
        }

    try:
        from gtts import gTTS

        tts = gTTS(
            text=text,
            lang=lang,
            slow=False
        )

        tts.save(filepath)
        logger.info(f"Generated voice file via gTTS: {filename}")

        return {
            "success": True,
            "filename": filename,
            "url": f"/static/audio/{filename}",
            "cached": False
        }

    except Exception as gtts_error:
        logger.warning(
            f"gTTS failed for {lang} (trying edge-tts fallback): {gtts_error}"
        )

    try:
        import asyncio
        from edge_tts import Communicate

        voice = _select_voice_for_lang(lang)

        async def _save_edge_tts():
            await Communicate(text, voice).save(filepath)

        asyncio.run(_save_edge_tts())
        logger.info(f"Generated voice file via edge_tts: {filename}")

        return {
            "success": True,
            "filename": filename,
            "url": f"/static/audio/{filename}",
            "cached": False
        }

    except Exception as edge_error:
        logger.warning(
            f"edge_tts failed for {lang} (trying Sarvam fallback): {edge_error}"
        )

    try:
        _generate_sarvam(text, lang, filepath)
        logger.info(f"Generated voice file via Sarvam Bulbul: {filename}")

        return {
            "success": True,
            "filename": filename,
            "url": f"/static/audio/{filename}",
            "cached": False
        }

    except Exception as e:
        logger.error(f"Voice generation failed: {e}")

        return {
            "success": False,
            "error": str(e)
        }


@voice_api_bp.route('/generate', methods=['POST'])
@jwt_required()
def generate_voice():
    """
    Generate MP3 and return URL.

    Body:
    {
        text,
        lang,
        elder_name,
        medicine_name,
        dosage,
        reminder_num,
        time_of_day
    }
    """

    data = request.get_json() or {}

    lang = data.get("lang", "te")

    if lang not in ["te", "en"]:
        lang = "te"

    text = data.get("text", "").strip()

    elder_name = data.get("elder_name", "")
    medicine_name = data.get("medicine_name", "")
    dosage = data.get("dosage", "")

    reminder_num = data.get("reminder_num", 1)
    time_of_day = data.get("time_of_day", "morning")

    if not text:
        text = _build_reminder_text(
            lang,
            elder_name,
            medicine_name,
            dosage,
            reminder_num,
            time_of_day
        )

    if not text:
        return jsonify({
            "error": "text is required"
        }), 400

    result = _generate_gtts(text, lang)

    if not result["success"]:
        return jsonify({
            "error": result.get("error", "Voice generation failed")
        }), 500

    return jsonify({
        "url": result["url"],
        "filename": result["filename"],
        "text": text,
        "lang": lang,
        "cached": result.get("cached", False)
    }), 200


@voice_api_bp.route('/reminder-audio', methods=['GET'])
def get_reminder_audio():
    """
    Example:

    /api/voice/reminder-audio
        ?elder=Ramesh
        &medicine=Paracetamol
        &dosage=500mg
        &lang=te
        &num=1
        &tod=morning
    """

    lang = request.args.get("lang", "te")

    if lang not in ["te", "en"]:
        lang = "te"

    elder_name = request.args.get("elder", "")
    medicine_name = request.args.get("medicine", "")
    dosage = request.args.get("dosage", "")
    time_of_day = request.args.get("tod", "morning")

    try:
        reminder_num = int(
            request.args.get("num", 1)
        )
    except (TypeError, ValueError):
        reminder_num = 1

    text = _build_reminder_text(
        lang,
        elder_name,
        medicine_name,
        dosage,
        reminder_num,
        time_of_day
    )

    result = _generate_gtts(text, lang)

    if not result["success"]:
        return jsonify({
            "error": result.get("error", "Voice generation failed")
        }), 500

    filepath = _audio_path(result["filename"])

    if not os.path.exists(filepath):
        return jsonify({
            "error": "Generated audio file not found"
        }), 404

    return send_file(
        filepath,
        mimetype="audio/mpeg",
        as_attachment=False
    )


def _build_reminder_text(
    lang: str,
    name: str,
    medicine: str,
    dosage: str,
    num: int,
    tod: str
) -> str:
    """Build reminder message."""

    greetings_te = {
        "morning": "శుభోదయం",
        "afternoon": "నమస్కారం",
        "night": "శుభరాత్రి"
    }

    greetings_en = {
        "morning": "Good morning",
        "afternoon": "Hello",
        "night": "Good evening"
    }

    if lang == "te":

        greeting = greetings_te.get(
            tod,
            "నమస్కారం"
        )

        if num == 1:
            return (
                f"{greeting}! {name} గారూ. "
                f"మీ {medicine} {dosage} "
                f"తీసుకోవలసిన సమయం వచ్చింది. "
                f"దయచేసి ఇప్పుడు తీసుకోండి."
            )

        elif num <= 4:
            return (
                f"{name} గారూ. "
                f"మీ {medicine} ఇంకా తీసుకోలేదు. "
                f"ఇది గుర్తుచేసే సందేశం."
            )

        else:
            return (
                f"{name} గారూ. "
                f"మీ {medicine} ఇంకా తీసుకోలేదు. "
                f"దయచేసి వెంటనే తీసుకోండి. "
                f"ఇది అత్యవసర సందేశం."
            )

    greeting = greetings_en.get(
        tod,
        "Hello"
    )

    if num == 1:
        return (
            f"{greeting} {name}. "
            f"It is time to take your "
            f"{medicine} {dosage}. "
            f"Please take it now."
        )

    elif num <= 4:
        return (
            f"{name}, you have not confirmed "
            f"taking {medicine} after "
            f"{num - 1} reminders. "
            f"Please take it immediately."
        )

    return (
        f"Important warning {name}. "
        f"You have missed {medicine} "
        f"{num - 1} times. "
        f"Please take it immediately. "
        f"Your caretaker has been notified."
    )