from app.routes.voice_api import (
    _build_reminder_text,
    _select_speaker_for_lang,
    _select_voice_for_lang,
)
from app.services.adaptive_reminder_engine import _build_texts


def test_telugu_voice_prefers_neural_voice():
    assert _select_voice_for_lang('te') == 'te-IN-ShrutiNeural'


def test_sarvam_speaker_selection_for_telugu():
    assert _select_speaker_for_lang('te') == 'shubh'


def test_build_reminder_text_uses_telugu_script():
    text = _build_reminder_text(
        lang='te',
        name='రమేష్',
        medicine='పారాసెటమాల్',
        dosage='500mg',
        num=1,
        tod='morning'
    )
    assert 'గారూ' in text
    assert 'తీసుకోవలసిన సమయం' in text


def test_build_reminder_text_uses_simple_reminder_style():
    text = _build_reminder_text(
        lang='te',
        name='శ్రీవాస్',
        medicine='మందులు',
        dosage='',
        num=2,
        tod='morning'
    )
    assert 'ఇది గుర్తుచేసే సందేశం' in text
    assert 'గారూ' in text


def test_build_texts_includes_elder_name_in_telugu():
    texts = _build_texts(
        elder_name='రమేష్',
        medicine_name='పారాసెటమాల్',
        dosage='500mg',
        scheduled_time='08:00 AM',
        reminder_num=1,
        time_of_day='morning'
    )
    assert 'రమేష్' in texts['te']
    assert 'గారూ' in texts['te']
