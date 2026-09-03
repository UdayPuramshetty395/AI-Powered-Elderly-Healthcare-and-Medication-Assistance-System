import os
import logging
import hashlib
from pathlib import Path

logger = logging.getLogger(__name__)


class VoiceService:
    """
    Generates voice reminder audio files using gTTS.
    Supports English and Telugu.
    """

    def __init__(self, audio_dir: str = 'app/static/audio'):
        self.audio_dir = audio_dir
        os.makedirs(audio_dir, exist_ok=True)

    def _get_filename(self, text: str, lang: str) -> str:
        """Generate a unique filename based on text hash."""
        text_hash = hashlib.md5(f"{lang}:{text}".encode()).hexdigest()[:12]
        return f"reminder_{text_hash}.mp3"

    def generate_reminder(self, elder_name: str, medicine_name: str, dosage: str,
                          scheduled_time: str, lang: str = 'en') -> dict:
        """
        Generate voice reminder audio file.
        Returns dict with file path and URL.
        """
        text = self._build_reminder_text(elder_name, medicine_name, dosage, scheduled_time, lang)
        filename = self._get_filename(text, lang)
        filepath = os.path.join(self.audio_dir, filename)

        # Return cached file if exists
        if os.path.exists(filepath):
            return {
                'success': True,
                'filename': filename,
                'url': f'/static/audio/{filename}',
                'text': text,
                'language': lang
            }

        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(filepath)
            logger.info(f"Generated voice reminder: {filename}")
            return {
                'success': True,
                'filename': filename,
                'url': f'/static/audio/{filename}',
                'text': text,
                'language': lang
            }
        except Exception as e:
            logger.error(f"Failed to generate voice reminder: {e}")
            return {
                'success': False,
                'error': str(e),
                'text': text,
                'language': lang
            }

    def _build_reminder_text(self, elder_name: str, medicine_name: str,
                              dosage: str, scheduled_time: str, lang: str) -> str:
        """Build reminder text in the appropriate language."""
        if lang == 'te':
            # Telugu reminder
            return (
                f"{elder_name} గారూ, మీరు {medicine_name} {dosage} "
                f"{scheduled_time} సమయంలో తీసుకోవాలి. "
                f"దయచేసి మీ మందు తీసుకోండి."
            )
        elif lang == 'hi':
            # Hindi reminder
            return (
                f"{elder_name} जी, {scheduled_time} बजे {medicine_name} {dosage} "
                f"लेने का समय हो गया है। कृपया अपनी दवाई लें।"
            )
        else:
            # English reminder (default)
            return (
                f"{elder_name}, it's time to take your {medicine_name} {dosage}. "
                f"Your scheduled time is {scheduled_time}. Please take your medication now."
            )

    def generate_missed_dose_reminder(self, elder_name: str, medicine_name: str,
                                       lang: str = 'en') -> dict:
        """Generate a missed dose reminder."""
        if lang == 'te':
            text = (
                f"{elder_name} గారూ, మీరు {medicine_name} తీసుకోవడం మరచిపోయారు. "
                f"దయచేసి వెంటనే తీసుకోండి లేదా మీ వైద్యుడిని సంప్రదించండి."
            )
        elif lang == 'hi':
            text = (
                f"{elder_name} जी, आप {medicine_name} लेना भूल गए हैं। "
                f"कृपया अभी लें या अपने डॉक्टर से संपर्क करें।"
            )
        else:
            text = (
                f"{elder_name}, you have missed your {medicine_name} dose. "
                f"Please take it now or contact your caretaker."
            )

        filename = self._get_filename(text, lang)
        filepath = os.path.join(self.audio_dir, filename)

        if os.path.exists(filepath):
            return {'success': True, 'filename': filename, 'url': f'/static/audio/{filename}', 'text': text}

        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(filepath)
            return {'success': True, 'filename': filename, 'url': f'/static/audio/{filename}', 'text': text}
        except Exception as e:
            logger.error(f"Error generating missed dose reminder: {e}")
            return {'success': False, 'error': str(e), 'text': text}

    def list_audio_files(self) -> list:
        """List all generated audio files."""
        files = []
        for f in Path(self.audio_dir).glob('*.mp3'):
            files.append({
                'filename': f.name,
                'url': f'/static/audio/{f.name}',
                'size': f.stat().st_size
            })
        return files

    def delete_audio_file(self, filename: str) -> bool:
        """Delete an audio file."""
        filepath = os.path.join(self.audio_dir, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
