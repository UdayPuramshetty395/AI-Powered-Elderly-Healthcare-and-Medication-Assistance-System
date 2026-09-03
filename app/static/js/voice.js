/**
 * Voice JS - Web Speech API & gTTS audio playback
 */

let currentAudio = null;

async function generateVoiceReminder(elderId, lang = 'en') {
    const player = document.getElementById('voice-player');
    if (player) {
        player.innerHTML = '<div class="spinner-border spinner-border-sm text-primary"></div> Generating voice...';
    }

    // Get elder's first scheduled medicine
    const schedulesData = await API.get(`/schedules/today/${elderId}`);
    if (!schedulesData || !schedulesData._ok || !schedulesData.schedules.length) {
        if (player) player.innerHTML = '<p class="text-muted small">No schedules found for today</p>';
        return;
    }

    const schedule = schedulesData.schedules[0];
    const elderData = await API.get(`/elders/${elderId}`);
    if (!elderData || !elderData._ok) return;

    // Call voice service via a direct play using browser TTS as fallback
    const elderName = elderData.elder.name;
    const medicineName = schedule.medicine_name;
    const dosage = schedule.medicine_dosage;
    const scheduledTime = Utils.formatTime(schedule.scheduled_time);

    // Try browser Speech Synthesis
    if ('speechSynthesis' in window) {
        playBrowserTTS(elderName, medicineName, dosage, scheduledTime, lang);
    }

    if (player) {
        player.innerHTML = `
            <div class="p-3 rounded" style="background:#e8f5e9">
                <p class="small mb-2"><strong>🔊 Reminder for:</strong> ${elderName}</p>
                <p class="small mb-2">${medicineName} ${dosage} at ${scheduledTime}</p>
                <button onclick="playBrowserTTS('${elderName}', '${medicineName}', '${dosage}', '${scheduledTime}', 'en')" 
                        class="btn btn-sm btn-success me-2">
                    <i class="bi bi-play-fill"></i> English
                </button>
                <button onclick="playBrowserTTS('${elderName}', '${medicineName}', '${dosage}', '${scheduledTime}', 'te')" 
                        class="btn btn-sm btn-outline-success">
                    <i class="bi bi-play-fill"></i> Telugu
                </button>
            </div>
        `;
    }
}

function playBrowserTTS(elderName, medicineName, dosage, scheduledTime, lang = 'en') {
    if (!('speechSynthesis' in window)) {
        Toast.error('Text-to-speech not supported in this browser');
        return;
    }

    // Stop any ongoing speech
    window.speechSynthesis.cancel();

    let text;
    if (lang === 'te') {
        text = `${elderName} గారూ, మీరు ${medicineName} ${dosage} తీసుకోవాలి. సమయం ${scheduledTime}.`;
    } else {
        text = `${elderName}, it's time to take your ${medicineName} ${dosage}. Your scheduled time is ${scheduledTime}. Please take your medication now.`;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.85;
    utterance.pitch = 1;
    utterance.volume = 1;

    // Try to set a matching voice
    const voices = window.speechSynthesis.getVoices();
    if (lang === 'te') {
        const teluguVoice = voices.find(v => v.lang === 'te-IN' || v.lang.startsWith('te'));
        if (teluguVoice) utterance.voice = teluguVoice;
    } else {
        const englishVoice = voices.find(v => v.lang === 'en-IN' || v.lang === 'en-US');
        if (englishVoice) utterance.voice = englishVoice;
    }

    utterance.onstart = () => Toast.info('Playing voice reminder...');
    utterance.onend = () => Toast.success('Reminder played!');
    utterance.onerror = () => Toast.error('Voice playback error');

    window.speechSynthesis.speak(utterance);
}

function stopVoice() {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
    }
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
}

function playAudioFile(url) {
    stopVoice();
    currentAudio = new Audio(url);
    currentAudio.play()
        .then(() => Toast.info('Playing audio reminder'))
        .catch(err => Toast.error('Failed to play audio: ' + err.message));
}

// Initialize voices list when page loads
window.speechSynthesis?.addEventListener('voiceschanged', () => {
    window.speechSynthesis.getVoices();
});
