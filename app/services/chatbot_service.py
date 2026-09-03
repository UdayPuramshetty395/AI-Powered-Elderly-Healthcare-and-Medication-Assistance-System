import logging
import re
import random
import hashlib
from functools import lru_cache

logger = logging.getLogger(__name__)

# Response cache for common queries (max 128 entries)
_response_cache: dict = {}
_cache_max_size = 128

# Rule-based knowledge base for common medication queries
HEALTH_KNOWLEDGE_BASE = {
    'metformin': {
        'use': 'Metformin is used to treat type 2 diabetes by lowering blood sugar levels.',
        'side_effects': 'Common side effects include nausea, stomach upset, diarrhea, and loss of appetite. Rare but serious: lactic acidosis.',
        'timing': 'Take with meals to reduce stomach upset. Usually taken twice or three times daily.',
        'avoid': 'Avoid excessive alcohol. Skip dose if not eating (consult doctor). Do not take before CT scan with contrast dye.',
        'interaction': 'Inform doctor about kidney issues, liver problems, or upcoming surgery.'
    },
    'amlodipine': {
        'use': 'Amlodipine is a calcium channel blocker used to treat high blood pressure and chest pain (angina).',
        'side_effects': 'May cause swelling of ankles/feet, flushing, headache, dizziness, or fatigue.',
        'timing': 'Take once daily, at the same time each day. Can be taken with or without food.',
        'avoid': 'Avoid grapefruit juice. Do not stop suddenly without consulting your doctor.',
        'interaction': 'Interacts with simvastatin — dose limitation required. Inform all doctors you take amlodipine.'
    },
    'atorvastatin': {
        'use': 'Atorvastatin lowers cholesterol and reduces the risk of heart disease and stroke.',
        'side_effects': 'Muscle pain, weakness, liver enzyme changes. Rare: rhabdomyolysis (muscle breakdown).',
        'timing': 'Take once daily, usually in the evening. Can be taken with or without food.',
        'avoid': 'Avoid grapefruit juice. Report any unexplained muscle pain immediately.',
        'interaction': 'Interactions with certain antibiotics, antifungals, and other cholesterol-lowering drugs.'
    },
    'aspirin': {
        'use': 'Aspirin is used as a blood thinner to prevent heart attacks and strokes in high-risk patients.',
        'side_effects': 'Stomach irritation, bleeding risk, ulcers with long-term use.',
        'timing': 'Take with food or milk to reduce stomach upset. Usually once daily (low dose 75-100mg).',
        'avoid': 'Avoid if you have active ulcers or bleeding disorders. Use caution with other blood thinners.',
        'interaction': 'Do not combine with ibuprofen at the same time. Increases bleeding risk with warfarin.'
    },
    'lisinopril': {
        'use': 'Lisinopril is an ACE inhibitor used for high blood pressure, heart failure, and kidney protection in diabetes.',
        'side_effects': 'Dry cough (very common), dizziness, headache, high potassium. Rare: angioedema (swelling of face/throat — seek emergency care).',
        'timing': 'Once daily, can be taken with or without food.',
        'avoid': 'Avoid potassium supplements unless prescribed. Avoid NSAIDs (ibuprofen) regularly.',
        'interaction': 'Do not take with ARBs (valsartan/losartan) together. Avoid in pregnancy.'
    },
    'warfarin': {
        'use': 'Warfarin prevents blood clots in conditions like atrial fibrillation, DVT, and after valve replacement.',
        'side_effects': 'Bleeding (major risk). Signs: unusual bruising, blood in urine/stool, prolonged bleeding from cuts.',
        'timing': 'Take at the same time each day. Requires regular INR blood tests.',
        'avoid': 'Many drug and food interactions. Consistent vitamin K intake (green vegetables). Avoid cranberry juice.',
        'interaction': 'Interacts with MANY medications including aspirin, NSAIDs, antibiotics, and supplements.'
    },
    'omeprazole': {
        'use': 'Omeprazole reduces stomach acid and is used for GERD, ulcers, and stomach protection with NSAIDs.',
        'side_effects': 'Headache, diarrhea, nausea. Long-term: low magnesium, vitamin B12 deficiency.',
        'timing': 'Take 30-60 minutes before meals for best effect.',
        'avoid': 'Do not take long-term without doctor supervision. May reduce effectiveness of clopidogrel.',
        'interaction': 'May reduce effectiveness of some HIV medications and clopidogrel.'
    }
}

GENERAL_RESPONSES = {
    'missed_dose': (
        "If you miss a dose, take it as soon as you remember — unless it's almost time for your next dose. "
        "In that case, skip the missed dose and continue with your regular schedule. "
        "Never double up on doses. If unsure, contact your doctor or pharmacist."
    ),
    'blood_pressure': (
        "A healthy blood pressure is generally below 120/80 mmHg. "
        "High blood pressure (hypertension) is 130/80 or above. "
        "If consistently high, consult your doctor. "
        "Tips: reduce salt, exercise regularly, manage stress, avoid smoking and excess alcohol."
    ),
    'blood_sugar': (
        "Normal fasting blood sugar is 70-100 mg/dL. "
        "Pre-diabetes: 100-125 mg/dL. Diabetes: 126+ mg/dL. "
        "Signs of low blood sugar (hypoglycemia): shakiness, sweating, confusion, dizziness. "
        "Treat low sugar with 15g fast-acting carbs (glucose tablets, juice). "
        "Signs of high blood sugar: increased thirst, frequent urination, fatigue."
    ),
    'diet': (
        "For elderly patients with chronic conditions: "
        "• Limit sodium (< 2300mg/day for hypertension) "
        "• Maintain consistent carbohydrate intake for diabetes "
        "• Eat fiber-rich foods: fruits, vegetables, whole grains "
        "• Stay well-hydrated (6-8 glasses of water) "
        "• Limit processed foods, sugar, and saturated fats "
        "• Consider consulting a registered dietitian"
    ),
    'adherence': (
        "Tips to improve medication adherence: "
        "• Use a pill organizer (weekly box) "
        "• Set daily reminders on phone "
        "• Link medication time with daily habits (meals, bedtime) "
        "• Keep a medication log "
        "• Ask for blister packs from pharmacist "
        "• Involve family or caretakers in reminders "
        "• Discuss side effects with doctor if causing you to skip doses"
    ),
    'side_effects': (
        "Common medication side effects in elderly: nausea, dizziness, fatigue, constipation. "
        "Seek immediate medical attention for: severe allergic reactions (rash, difficulty breathing, swelling), "
        "chest pain, sudden weakness, or unusual bleeding. "
        "Always report new symptoms to your doctor — they may need to adjust your dosage or change medication."
    )
}

GENERAL_RESPONSES_TE = {
    'missed_dose': (
        "మీరు మందు మిస్ అయితే, వెంటనే గుర్తుచేసుకున్నప్పుడు తీసుకోండి, కానీ తర్వాతి డోస్ సమీపంలో ఉన్నట్లయితే మిస్ అయిన డోస్‌ను వదిలి తరువాతి షెడ్యూల్‌ను కొనసాగించండి. "
        "ఒకేచోట రెండు డోస్‌లను తీసుకోరు. మీకు సందేహం ఉంటే డాక్టర్ లేదా ఫార్మసిస్టును సంప్రదించండి."
    ),
    'blood_pressure': (
        "ఆరోగ్యకరమైన రక్తపోటు సాధారణంగా 120/80 mmHg కంటే తక్కువ. "
        "రక్తపోటు 130/80 లేదా ఎక్కువగా ఉంటే ఇది అధిక రక్తపోటు. "
        "ఉప్పు తగ్గించండి, వ్యాయామం చేయండి, ఒత్తిడి తగ్గించండి, పొగ త్రాగవద్దు, మద్యం పరిమితం చేయండి."
    ),
    'blood_sugar': (
        "సాధారణ ఫాస్టింగ్ బ్లడ్ షుగర్ 70-100 mg/dL. "
        "డయాబెటిస్ ఉన్నవారు చక్కెరను నియంత్రించడానికి తరచుగా వైద్యుడి సూచనలను పాటించాలి. "
        "తక్కువ షుగర్ చిటుకు, వాంతులు, తలనొప్పి, మంట వంటి లక్షణాలను కలిగిస్తుంది."
    ),
    'diet': (
        "వృద్ధుల ఆహారంలో వెజిటబుల్స్‌, పూర్తి ధాన్యాలు, లీవ్ ప్రోటీన్‌, ఆరోగ్యకరమైన కొవ్వులు ఉండాలి. "
        "ఉప్పు, ఫ్రైడ్ ఫుడ్స్, అధిక చక్కెర ఆహారాలను తగ్గించండి. "
        "ప్రతిరోజూ చాలా నీరు తాగండి."
    ),
    'adherence': (
        "మందులను రకసరంగా తీసుకోవడానికి: పిల్ ఆర్గనైజర్ ఉపయోగించండి, రోజువారీ రిమైండర్లు పెట్టండి, ఆహారపు అలవాట్లతో ముడిపడి తీసుకోండి, డోస్‌లను నమోదు చేయండి, మీ కుటుంబ సభ్యులను సహాయం కోసం కలుపుకోండి."
    ),
    'side_effects': (
        "మందుల వల్ల సాధారణంగా వాంతులు, తలనొప్పి, అలసట, వాంతులు, డైజెస్టివ్ సమస్యలు ఉంటాయి. "
        "తీవ్రమైన అంశాలు: శరీరంలో పెద్ద చాపలు, శ్వాస తీసుకోవటంలో ఇబ్బంది, ఉబ్బసం. "
        "ఇలాంటి అంశాలు ఉంటే వెంటనే వైద్యుడిని సంప్రదించండి."
    )
}


COMPANION_RESPONSES = {
    'lonely': [
        "I'm always here with you! You're not alone. Tell me, how was your day today?",
        "I understand feeling lonely can be hard. Would you like to talk? I'm listening.",
        "You matter so much to the people around you. How are you feeling right now?",
    ],
    'sad': [
        "I'm sorry to hear you're feeling sad. It's okay to feel that way sometimes. Would you like to talk about it?",
        "I'm here for you. Sometimes just talking helps. What's on your mind?",
        "Your feelings are valid. Is there anything I can do to help you feel better?",
    ],
    'happy': [
        "That's wonderful! Your happiness brightens the day! What made you feel happy?",
        "So glad to hear you're feeling good! Keep that positive spirit!",
        "Excellent! A happy heart is healthy too! What's the good news?",
    ],
    'pain': [
        "I'm sorry you're in pain. Please let your caretaker or doctor know right away.",
        "Pain should never be ignored. Have you informed your caretaker? They need to know.",
        "Your health comes first. Please describe your pain to your doctor. Is it severe?",
    ],
    'sleep': [
        "Good sleep is very important for health. Try to sleep and wake at the same time every day.",
        "Some tips for better sleep: avoid screens before bed, keep the room cool and dark.",
        "If sleep problems continue, please mention it to your doctor.",
    ],
    'family': [
        "Family is such a blessing. Have you spoken to them recently? I'm sure they miss you!",
        "Your family cares deeply about you. Would you like me to remind you to call them?",
        "Staying connected with family is so important. How are they doing?",
    ],
    'bored': [
        "Let's make the day more interesting! You can try some gentle stretches or deep breathing.",
        "How about listening to some music or calling a family member?",
        "Being active — even a short walk — can lift your mood greatly!",
    ],
    'thanks': [
        "You're very welcome! I'm always here whenever you need me.",
        "It's my pleasure to help! Take care of yourself.",
        "Anytime! Stay healthy and happy!",
    ],
    'good_morning': [
        "Good morning! I hope you slept well. Don't forget your morning medications!",
        "Good morning! A new day brings new blessings. How are you feeling today?",
        "Good morning! Remember to take your medicines after breakfast.",
    ],
    'good_night': [
        "Good night! Sleep well and take care. Remember your evening medications!",
        "Good night! Rest well. I'll be here in the morning.",
        "Sweet dreams! Don't forget your night medicines before sleeping.",
    ],
}

COMPANION_RESPONSES_TE = {
    'lonely': [
        "నేను మీతోనే ఉన్నాను. మీరు ఒంటరిగా లేరు. ఈరోజు మీ రోజు ఎలా గడిచింది?",
        "ఒంటరిగా అనిపించడం కష్టం. మీరు మాట్లాడాలనుకుంటే నేను వినడానికి సిద్ధంగా ఉన్నాను.",
    ],
    'sad': [
        "మీకు బాధగా ఉందని వినడం బాధగా ఉంది. కొంచెం మాట్లాడితే మనసు తేలిక అవుతుంది. ఏమైంది?",
        "నేను మీతో ఉన్నాను. మీ భావాలు ముఖ్యమైనవి.",
    ],
    'happy': [
        "చాలా బాగుంది! మీరు సంతోషంగా ఉండటం ఆనందంగా ఉంది.",
        "అద్భుతం! ఆ మంచి ఆనందాన్ని కొనసాగించండి.",
    ],
    'pain': [
        "నొప్పిని నిర్లక్ష్యం చేయకండి. దయచేసి వెంటనే మీ సంరక్షకుడు లేదా వైద్యుడికి చెప్పండి.",
        "మీ ఆరోగ్యం ముఖ్యం. నొప్పి ఎక్కువగా ఉంటే వెంటనే సహాయం కోరండి.",
    ],
    'sleep': [
        "మంచి నిద్ర ఆరోగ్యానికి చాలా ముఖ్యం. ప్రతిరోజూ ఒకే సమయానికి నిద్రపోవడానికి ప్రయత్నించండి.",
        "నిద్ర సమస్య కొనసాగితే దయచేసి మీ వైద్యుడికి చెప్పండి.",
    ],
    'thanks': [
        "మీకు స్వాగతం. మీకు అవసరం ఉన్నప్పుడు నేను ఇక్కడే ఉంటాను.",
        "సంతోషంగా సహాయం చేస్తాను. జాగ్రత్తగా ఉండండి.",
    ],
    'hello': [
        "నమస్కారం! నేను మీ ఆరోగ్య సహాయకుడిని. మందులు, ఆరోగ్యం లేదా మీ భావాల గురించి మాట్లాడవచ్చు.",
        "నమస్కారం! ఈరోజు మీరు ఎలా ఉన్నారు?",
    ],
    'adherence': [
        "మందులు సమయానికి తీసుకోవడం మీ ఆరోగ్యానికి చాలా ముఖ్యం. మీరు మందు తీసుకున్న తర్వాత Taken నొక్కండి.",
    ],
}

class ChatbotService:
    """
    AI Chatbot service with rule-based responses and optional OpenAI integration.
    """

    def __init__(self, openai_api_key: str = ''):
        self.openai_api_key = openai_api_key
        self.use_openai = bool(openai_api_key and openai_api_key != 'your-openai-api-key')

    def get_response(self, message: str, history: list = None,
                     elder_context: dict = None, language: str = 'en') -> dict:
        """
        Get chatbot response for a message.
        Tries OpenAI first if available, falls back to an enhanced rule-based engine.
        Caches rule-based responses for common queries.
        """
        # Try to get cached response for rule-based queries (skip cache for personalized context)
        if not elder_context or elder_context.get('skip_cache'):
            cache_key = self._get_cache_key(message, language)
            if cache_key in _response_cache:
                logger.debug(f"Cache hit for: {message[:30]}")
                return _response_cache[cache_key]
        
        if self.use_openai:
            try:
                return self._get_openai_response(message, history, elder_context, language)
            except Exception as e:
                logger.warning(f"OpenAI failed, using enhanced rule-based: {e}")

        # Get rule-based response and cache it
        response = self._get_rule_based_response(message, elder_context, language, history)
        
        # Cache rule-based responses (not personalized ones)
        if not elder_context or elder_context.get('skip_cache') is False:
            cache_key = self._get_cache_key(message, language)
            if len(_response_cache) >= _cache_max_size:
                # Simple LRU: remove first item when cache is full
                _response_cache.pop(next(iter(_response_cache)))
            _response_cache[cache_key] = response
        
        return response

    def _get_cache_key(self, message: str, language: str) -> str:
        """Generate a cache key from message and language."""
        normalized = self._normalize_text(message.lower().strip())
        key_str = f"{normalized}:{language}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def _extract_history_context(self, history: list = None) -> str | None:
        if not history:
            return None
        for item in reversed(history):
            if not isinstance(item, dict):
                continue
            content = item.get('content', '')
            role = item.get('role', '')
            if role == 'assistant' and content:
                lower_content = content.lower()
                for medicine in HEALTH_KNOWLEDGE_BASE:
                    if medicine in lower_content:
                        return medicine
        return None

    def _is_follow_up_prompt(self, normalized_message: str) -> bool:
        follow_up_phrases = [
            'what about', 'tell me more', 'more about', 'explain it', 'explain that',
            'how about', 'can you explain', 'can you tell', 'more info', 'more information'
        ]
        if any(phrase in normalized_message for phrase in follow_up_phrases):
            return True

        if normalized_message in [
            'side effects', 'how to take', 'when to take', 'what is it', 'what is this',
            'purpose', 'use', 'how to use', 'what is the use'
        ]:
            return True

        tokens = normalized_message.split()
        if len(tokens) <= 4 and any(token in tokens for token in ['it', 'that', 'this', 'again', 'also']):
            return any(token in tokens for token in ['what', 'how', 'when', 'why', 'can', 'tell', 'explain'])

        return False

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ''
        normalized = re.sub(r'[^a-z0-9\s]', ' ', text.lower())
        return re.sub(r'\s+', ' ', normalized).strip()

    def _match_medicine(self, normalized_text: str) -> str | None:
        for medicine_key in HEALTH_KNOWLEDGE_BASE:
            if medicine_key in normalized_text:
                return medicine_key
        return None

    def _get_symptom_response(self, normalized_message: str) -> dict | None:
        if any(word in normalized_message for word in ['headache', 'migraine', 'head hurts', 'head pain', 'pressure in head']):
            return {
                'text': (
                    "I'm sorry you're experiencing a headache. "
                    "Try resting in a quiet, dark room, stay hydrated, and avoid strong smells. "
                    "If the pain is severe, sudden, or does not improve, contact your doctor."
                ),
                'suggestions': ["When should I see a doctor?", "How can I relieve a headache?"]
            }

        if any(word in normalized_message for word in ['dizzy', 'dizziness', 'lightheaded', 'faint']):
            return {
                'text': (
                    "Dizziness can be uncomfortable. Sit or lie down until it passes, "
                    "drink water, and avoid sudden movements. If it happens often, please tell your doctor."
                ),
                'suggestions': ["What causes dizziness?", "When is dizziness serious?"]
            }

        if any(word in normalized_message for word in ['nausea', 'nauseous', 'vomit', 'vomiting', 'sick to my stomach']):
            return {
                'text': (
                    "I'm sorry you feel nauseous. Sip small amounts of water, eat light bland foods, "
                    "and rest. If nausea continues or you vomit repeatedly, contact a healthcare provider."
                ),
                'suggestions': ["What helps nausea?", "When should I call a doctor?"]
            }

        if any(word in normalized_message for word in ['pain', 'ache', 'hurt', 'hurts', 'sore']):
            return {
                'text': (
                    "I understand you're in pain. Try to rest, keep comfortable, and avoid activities that make it worse. "
                    "If the pain is severe, new, or getting worse, please seek medical advice."
                ),
                'suggestions': ["What can I do for pain?", "When should I see a doctor?"]
            }

        return None

    def _get_diabetes_diet_response(self, normalized_message: str) -> dict | None:
        if any(word in normalized_message for word in ['diabetes', 'blood sugar', 'glucose', 'hypoglycemia', 'hyperglycemia']):
            if any(word in normalized_message for word in ['sweet', 'sweets', 'dessert', 'candy', 'candies', 'pie', 'cake', 'ice cream', 'cookies', 'sugar']):
                return {
                    'text': (
                        "Heavy sweets are not recommended for people with diabetes. "
                        "Choose small portions, low-sugar alternatives, or fresh fruit instead. "
                        "Keep your blood sugar steady by eating balanced meals, taking medicines on time, and checking with your doctor before you change your diet."
                    ),
                    'suggestions': ["What foods should I avoid with diabetes?", "How much sugar is safe?", "What are low-sugar dessert options?"]
                }

            if any(word in normalized_message for word in ['eat', 'food', 'diet', 'meal', 'drink', 'what can i eat', 'what should i eat', 'can i eat']):
                return {
                    'text': (
                        "For diabetes, eat regular meals with moderate carbohydrates, plenty of vegetables, lean protein, and healthy fats. "
                        "Limit sugary snacks, white bread, and processed foods. "
                        "Staying hydrated and following your medicine schedule helps keep blood sugar stable."
                    ),
                    'suggestions': ["Diet tips for diabetes", "What are low glycemic foods?", "How to control blood sugar?"]
                }

        if any(word in normalized_message for word in ['sugar', 'sweet', 'dessert', 'candy', 'cake', 'ice cream']) and any(word in normalized_message for word in ['diet', 'eat', 'food', 'meal']):
            return {
                'text': (
                    "If you have diabetes, it is best to limit sweets and choose low-sugar options. "
                    "Small portions of dessert are okay sometimes, but always balance them with your regular medicines and meals."
                ),
                'suggestions': ["What are healthy dessert ideas?", "How to keep blood sugar steady?", "Can I eat fruit with diabetes?"]
            }

        return None

    def _get_general_health_response(self, normalized_message: str, elder_context: dict = None) -> dict | None:
        if any(word in normalized_message for word in ['diet', 'nutrition', 'what should i eat', 'food', 'eat healthy', 'healthy food']):
            response = (
                "A healthy diet for older adults includes regular meals with vegetables, whole grains, lean protein, and healthy fats. "
                "Limit salty, fried, and high-sugar foods. "
                "Drink plenty of water and try to eat consistent portions each day."
            )
            if elder_context and elder_context.get('medical_conditions'):
                response += f" For {elder_context['name']}, who has {elder_context['medical_conditions']}, it is especially important to follow your doctor’s advice and keep medications on schedule."
            return {
                'text': response,
                'suggestions': ["Diet tips for blood pressure", "Foods to avoid with diabetes", "How much water should I drink?"]
            }

        if any(word in normalized_message for word in ['exercise', 'walk', 'physical activity', 'movement', 'strength', 'fitness']):
            return {
                'text': (
                    "Gentle daily activity is important for overall health. "
                    "Try short walks, light stretching, or chair exercises, and avoid sudden heavy activity. "
                    "Always check with a doctor before starting a new exercise routine."
                ),
                'suggestions': ["What exercises are safe for elderly?", "How often should I walk?", "Can I do light stretching?" ]
            }

        if any(word in normalized_message for word in ['water', 'hydration', 'dehydration', 'thirst']):
            return {
                'text': (
                    "Staying hydrated is very important, especially for older adults. "
                    "Drink water regularly throughout the day and aim for 6-8 glasses unless your doctor advises otherwise. "
                    "If you feel dizzy, very thirsty, or your urine is dark, drink water and tell your doctor."
                ),
                'suggestions': ["How much water should I drink?", "What are dehydration signs?", "Can I drink tea or coffee?" ]
            }

        if any(word in normalized_message for word in ['sleep', 'insomnia', 'rest', 'sleep better', 'sleeping problem']):
            return {
                'text': (
                    "Good sleep helps health. Try to keep a regular bedtime, avoid screens before bed, and make the bedroom cool and quiet. "
                    "If you still have trouble sleeping, talk to your doctor about safe sleep strategies."
                ),
                'suggestions': ["Tips for better sleep", "How many hours should I sleep?", "When should I see a doctor about sleep?" ]
            }

        if any(word in normalized_message for word in ['interaction', 'drug interaction', 'medicine interaction', 'interact with medicine', 'alcohol with medicine', 'grapefruit', 'painkiller']):
            return {
                'text': (
                    "Some medicines can interact with other drugs, foods, or drinks. "
                    "Always tell your doctor and pharmacist about every medicine, vitamin, and supplement you take. "
                    "Ask before combining medicines with alcohol, grapefruit juice, or OTC pain relievers."
                ),
                'suggestions': ["Can I mix medicines?", "What interacts with my pills?", "How to avoid drug interactions?"]
            }

        if any(word in normalized_message for word in ['when to see a doctor', 'urgent', 'emergency', 'call doctor', 'seek medical', 'hospital', 'serious']):
            return {
                'text': (
                    "If you have sudden chest pain, trouble breathing, severe dizziness, sudden weakness, severe swelling, or uncontrolled bleeding, seek medical help right away. "
                    "For ongoing symptoms like high fever, persistent pain, or confusion, contact your doctor as soon as possible."
                ),
                'suggestions': ["When is dizziness serious?", "What are emergency signs?", "How do I prepare for a doctor visit?"]
            }

        if any(word in normalized_message for word in ['blood pressure', 'hypertension', 'bp', 'high blood pressure']):
            return {
                'text': (
                    "A healthy blood pressure is generally below 120/80 mmHg. "
                    "Control blood pressure by limiting salt, staying active, taking medicines regularly, and following your doctor’s advice. "
                    "Monitor it often and report any large changes to your healthcare provider."
                ),
                'suggestions': ["Blood pressure diet tips", "What is a healthy BP?", "How can I lower BP?"]
            }

        if any(word in normalized_message for word in ['diabetes', 'blood sugar', 'glucose', 'insulin']):
            return {
                'text': (
                    "Managing diabetes means balancing food, activity, and medicines. "
                    "Eat regular, moderate-carb meals, check your blood sugar as your doctor advises, and never skip your diabetes medicines without talking to a doctor."
                ),
                'suggestions': ["What is a healthy blood sugar?", "Diet tips for diabetes", "How often should I test?"]
            }

        return None

    def _get_rule_based_response(self, message: str, elder_context: dict = None,
                                   language: str = 'en', history: list = None) -> dict:
        """Enhanced rule-based response engine with intent matching and context awareness."""
        msg_lower = message.lower().strip()
        response_text = None
        suggestions = []

        if not msg_lower:
            return {
                'text': 'I can help with medicines, health tips, or companionship. What would you like to know?',
                'source': 'rule_based',
                'suggestions': ['What is Metformin?', 'How to improve adherence?', 'I feel lonely']
            }

        normalized = self._normalize_text(msg_lower)
        history_context = self._extract_history_context(history)

        # ── Telugu language ───────────────────────────────────────────────────
        if language == 'te':
            telugu_response = self._get_telugu_companion_response(msg_lower)
            if telugu_response:
                return telugu_response

            telugu_general = self._get_telugu_general_response(msg_lower, normalized, elder_context)
            if telugu_general:
                return telugu_general

        # ── Priority 1: Greetings and symptom handling (check BEFORE context) ─
        symptom_response = self._get_symptom_response(normalized)
        if symptom_response:
            response_text = symptom_response['text']
            suggestions = symptom_response['suggestions']

        # ── Priority 1.1: Diabetes and diet guidance ─────────────────────────────
        if not response_text:
            diabetes_response = self._get_diabetes_diet_response(normalized)
            if diabetes_response:
                response_text = diabetes_response['text']
                suggestions = diabetes_response['suggestions']

        # ── Priority 1.2: General health topics ─────────────────────────────────
        if not response_text:
            general_health_response = self._get_general_health_response(normalized, elder_context)
            if general_health_response:
                response_text = general_health_response['text']
                suggestions = general_health_response['suggestions']

        if not response_text and any(w in normalized for w in ['good morning', 'subhodayam', 'శుభోదయం']):
            response_text = random.choice(COMPANION_RESPONSES['good_morning'])
            suggestions = ["What are my medicines today?", "Health tip for today"]
        elif any(w in normalized for w in ['good night', 'good evening', 'subharatri', 'శుభరాత్రి']):
            response_text = random.choice(COMPANION_RESPONSES['good_night'])
            suggestions = ["Evening medicines reminder", "Tips for good sleep"]
        elif any(w in normalized for w in ['hello', 'hi', 'hey', 'good day', 'start', 'help me', 'help']):
            response_text = (
                "Hello! I'm your AI Healthcare Assistant. I can help you with:\n"
                "• 💊 Medication information and side effects\n"
                "• 🩺 Health tips for blood pressure, diabetes\n"
                "• 🥗 Diet and nutrition guidance\n"
                "• 💬 Emotional support and companionship\n\n"
                "What would you like to know?"
            )
            suggestions = ["What is Metformin?", "Blood pressure tips",
                           "I feel lonely", "Side effects of Amlodipine"]

        # ── Priority 2: Medicine confirmation ────────────────────────────────
        if not response_text:
            if any(w in normalized for w in ['i took', 'i have taken', 'took medicine',
                                             'taken medicine', 'medicine taken', 'dose taken', 'took my medicine']):
                response_text = (
                    "Great! I've noted that you've taken your medicine. 👍\n\n"
                    "Please also mark it as **Taken** in the Adherence Tracker so your caretaker is notified.\n\n"
                    "Taking medicines regularly keeps you healthy!"
                )
                suggestions = ["Mark as taken in tracker", "What's my next medicine?", "How am I doing?"]

        # ── Priority 3: Schedule questions ───────────────────────────────────
        if not response_text:
            if any(w in normalized for w in ['my medicines today', 'today medicines',
                                             'what medicines', 'pending medicines',
                                             'which medicines', 'medicines today',
                                             'what medicine', 'medicines for today',
                                             'ఈరోజు మందులు', 'మందులు ఏమిటి']):
                if elder_context:
                    meds = elder_context.get('medicines', [])
                    names = ', '.join(f"{m['name']} {m['dosage']}" for m in meds[:5]) if meds else 'none on record'
                    response_text = (
                        f"**{elder_context['name']}'s medicines:**\n{names}\n\n"
                        "Please check the **Schedules** page for exact times and the "
                        "**Adherence Tracker** to mark doses as taken."
                    )
                else:
                    response_text = (
                        "Please select a patient from the Patient Context panel on the right "
                        "to see their specific medicines and schedules."
                    )
                suggestions = ["Mark a dose as taken", "What is my next medicine?"]

            elif any(w in normalized for w in ['next medicine', 'next dose', 'next reminder',
                                               'what is next', 'what comes next', 'తదుపరి మందు', 'next']):
                if elder_context:
                    meds = elder_context.get('medicines', [])
                    response_text = (
                        f"For {elder_context['name']}, the scheduled medicines are: "
                        + (', '.join(m['name'] for m in meds[:3]) if meds else 'none on record')
                        + ". Check the Schedules page for exact times."
                    )
                else:
                    response_text = "Please select a patient to see their next scheduled medicine."
                suggestions = ["Show today's schedule", "Mark medicine as taken"]

        # ── Priority 4: Specific medicine queries ─────────────────────────────
        if not response_text:
            medicine_key = self._match_medicine(normalized)
            if medicine_key:
                info = HEALTH_KNOWLEDGE_BASE[medicine_key]
                if any(w in normalized for w in ['side effect', 'adverse', 'risk', 'reaction', 'side effects']):
                    response_text = f"**{medicine_key.title()} — Side Effects:**\n{info['side_effects']}"
                elif any(w in normalized for w in ['when', 'time', 'how to take', 'how do i', 'when to take', 'dosage', 'dose']):
                    response_text = f"**{medicine_key.title()} — How to Take:**\n{info['timing']}"
                elif any(w in normalized for w in ['avoid', 'food', 'interact', 'drug', 'interaction', 'grapefruit', 'alcohol']):
                    response_text = (
                        f"**{medicine_key.title()} — Avoid:**\n{info['avoid']}\n\n"
                        f"**Interactions:**\n{info['interaction']}"
                    )
                else:
                    response_text = (
                        f"**{medicine_key.title()}:**\n"
                        f"**Use:** {info['use']}\n\n"
                        f"**Timing:** {info['timing']}\n\n"
                        f"**Side Effects:** {info['side_effects']}"
                    )
                suggestions = [f"Side effects of {medicine_key}?",
                               f"How to take {medicine_key}?",
                               "Medication adherence tips"]

        # ── Priority 5: Follow-up / context-aware prompts ────────────────────
        if not response_text and history_context and self._is_follow_up_prompt(normalized):
            response_text = (
                f"You were asking about {history_context.title()}. "
                "I can explain its purpose, timing, side effects, or how to stay consistent with it."
            )
            suggestions = [f"How to take {history_context}?", f"Side effects of {history_context}?", "Medication adherence tips"]

        # ── Priority 6: Emotional support ────────────────────────────────────
        if not response_text:
            if any(w in normalized for w in ['lonely', 'alone', 'no one', 'isolated']):
                response_text = random.choice(COMPANION_RESPONSES['lonely'])
                suggestions = ["Tell me about your day", "How are you feeling?"]
            elif any(w in normalized for w in ['sad', 'upset', 'crying', 'depressed', 'unhappy']):
                response_text = random.choice(COMPANION_RESPONSES['sad'])
                suggestions = ["I want to talk", "Give me tips to feel better"]
            elif any(w in normalized for w in ['pain', 'hurt', 'ache', 'chest pain', 'fever', 'breathless']):
                response_text = random.choice(COMPANION_RESPONSES['pain'])
                suggestions = ["When to call a doctor?", "What are emergency symptoms?"]
            elif any(w in normalized for w in ['cant sleep', 'insomnia', 'not sleeping', 'sleep problem', 'sleeping problem']):
                response_text = random.choice(COMPANION_RESPONSES['sleep'])
                suggestions = ["Tips for better sleep", "Diet tips for elderly"]
            elif any(w in normalized for w in ['family', 'son', 'daughter', 'child', 'wife', 'husband']):
                response_text = random.choice(COMPANION_RESPONSES['family'])
                suggestions = ["How to stay connected?"]
            elif any(w in normalized for w in ['bored', 'boring', 'nothing to do', 'idle']):
                response_text = random.choice(COMPANION_RESPONSES['bored'])
                suggestions = ["Simple exercises", "Health tip for today"]
            elif any(w in normalized for w in ['thank', 'thanks', 'thank you', 'dhanyavaad']):
                response_text = random.choice(COMPANION_RESPONSES['thanks'])
                suggestions = ["How are you?", "Tell me a health tip"]
            elif any(w in normalized for w in ['how are you', 'how do you do', 'whats up', 'how r u', 'how are u']):
                response_text = "I'm doing great! I'm here to help you stay healthy and happy. How are YOU feeling today? 😊"
                suggestions = ["I'm feeling good", "I'm not feeling well", "Tell me a health tip"]
            elif any(w in normalized for w in ['happy', 'great', 'wonderful', 'excellent', 'feeling good', 'feeling well']):
                response_text = random.choice(COMPANION_RESPONSES['happy'])
                suggestions = ["Health tip for today?", "What's my next medicine?"]

        # ── Priority 7: Health topics ─────────────────────────────────────────
        if not response_text:
            if any(w in normalized for w in ['missed dose', 'forgot dose', 'miss medicine', 'skip', 'forgot my medicine']):
                response_text = GENERAL_RESPONSES['missed_dose']
                suggestions = ["Signs of low blood sugar?", "Set medication reminders"]
            elif any(w in normalized for w in ['blood pressure', 'hypertension', 'bp', 'high pressure']):
                response_text = GENERAL_RESPONSES['blood_pressure']
                suggestions = ["BP medications?", "Diet tips for hypertension"]
            elif any(w in normalized for w in ['blood sugar', 'diabetes', 'glucose', 'hypoglycemia', 'sugar level']):
                response_text = GENERAL_RESPONSES['blood_sugar']
                suggestions = ["Diet tips for diabetes", "What is Metformin?"]
            elif any(w in normalized for w in ['diet', 'food', 'eat', 'nutrition', 'what should i eat']):
                response_text = GENERAL_RESPONSES['diet']
                suggestions = ["Foods to avoid with BP medicine", "Foods for diabetics"]
            elif any(w in normalized for w in ['adherence', 'reminder', 'remember medicine', 'forget medicine']):
                response_text = GENERAL_RESPONSES['adherence']
                suggestions = ["How app helps with reminders?", "What if I miss a dose?"]
            elif any(w in normalized for w in ['side effect', 'adverse effect', 'reaction to medicine']):
                response_text = GENERAL_RESPONSES['side_effects']
                suggestions = ["Side effects of Metformin", "Side effects of Amlodipine"]

        # ── Priority 8: Fallback ──────────────────────────────────────────────
        if not response_text:
            response_text = (
                "I can help with:\n"
                "• 💊 **Medicine info** — Ask about Metformin, Amlodipine, etc.\n"
                "• 🩺 **Health tips** — Blood pressure, diabetes, diet\n"
                "• 📅 **My medicines** — Ask 'what are my medicines today?'\n"
                "• 💬 **Emotional support** — Tell me how you're feeling\n\n"
                "⚕️ *Always consult your doctor for medical decisions.*"
            )
            suggestions = ["What is Metformin?", "Blood pressure tips",
                           "What are my medicines today?", "I feel lonely"]

        # Append elder context if provided
        if elder_context and elder_context.get('name'):
            if any(w in normalized for w in ['my', 'i', 'me']) and elder_context.get('medicines'):
                response_text += (
                    f"\n\n---\n📋 *Patient: {elder_context['name']} (Age: {elder_context['age']})*\n"
                    f"Medicines: {', '.join(m['name'] for m in elder_context.get('medicines', [])[:3])}"
                )
            if elder_context.get('allergies'):
                response_text += f"\n⚠️ Allergies: {elder_context['allergies']}"

        return {'text': response_text, 'source': 'rule_based', 'suggestions': suggestions}

    def _get_telugu_companion_response(self, msg_lower: str) -> dict:
        """Small Telugu-first companion mode for voice conversations."""
        response_text = None
        suggestions = []

        if any(word in msg_lower for word in ['lonely', 'alone', 'ఒంటరి', 'ఒంటరిగా']):
            response_text = random.choice(COMPANION_RESPONSES_TE['lonely'])
            suggestions = ["ఈరోజు గురించి చెప్పండి", "మీరు ఎలా ఉన్నారు?"]
        elif any(word in msg_lower for word in ['sad', 'బాధ', 'దుఃఖం']):
            response_text = random.choice(COMPANION_RESPONSES_TE['sad'])
            suggestions = ["నేను మాట్లాడాలనుకుంటున్నాను", "నాకు మంచి మాట చెప్పండి"]
        elif any(word in msg_lower for word in ['happy', 'good', 'సంతోషం', 'బాగుంది']):
            response_text = random.choice(COMPANION_RESPONSES_TE['happy'])
            suggestions = ["ఆరోగ్య సూచన చెప్పండి", "నా మందులు ఏమిటి?"]
        elif any(word in msg_lower for word in ['pain', 'hurt', 'నొప్పి']):
            response_text = random.choice(COMPANION_RESPONSES_TE['pain'])
            suggestions = ["ఎప్పుడు డాక్టర్‌ను సంప్రదించాలి?", "అత్యవసర లక్షణాలు ఏమిటి?"]
        elif any(word in msg_lower for word in ['sleep', 'నిద్ర']):
            response_text = random.choice(COMPANION_RESPONSES_TE['sleep'])
            suggestions = ["నిద్ర కోసం సూచనలు", "ఆరోగ్య సూచన చెప్పండి"]
        elif any(word in msg_lower for word in ['thank', 'thanks', 'ధన్యవాదాలు']):
            response_text = random.choice(COMPANION_RESPONSES_TE['thanks'])
            suggestions = ["మీరు ఎలా ఉన్నారు?", "నా మందులు చెప్పండి"]
        elif any(word in msg_lower for word in ['reminder', 'forgot', 'miss']) and not any(w in msg_lower for w in ['ఏమిటి', 'what', 'какие']):
            # Adherence/reminder but NOT "what are my medicines"
            response_text = random.choice(COMPANION_RESPONSES_TE['adherence'])
            suggestions = ["నా మందులు ఏమిటి?", "మందు మిస్ అయితే ఏమి చేయాలి?"]
        elif any(word in msg_lower for word in ['hello', 'hi', 'hey', 'నమస్కారం', 'హాయ్', 'help']):
            response_text = random.choice(COMPANION_RESPONSES_TE['hello'])
            suggestions = ["నా మందులు ఏమిటి?", "నేను ఒంటరిగా ఉన్నాను", "ఆరోగ్య సూచన చెప్పండి"]

        if not response_text:
            return None

        return {
            'text': response_text,
            'source': 'rule_based_telugu',
            'suggestions': suggestions
        }

    def _get_telugu_general_response(self, msg_lower: str, normalized_message: str, elder_context: dict = None) -> dict | None:
        if any(word in msg_lower for word in ['missed dose', 'forgot dose', 'miss medicine', 'skip', 'forgot my medicine', 'మిస్', 'మరచి', 'వదిలి']):
            return {
                'text': GENERAL_RESPONSES_TE['missed_dose'],
                'source': 'rule_based_telugu',
                'suggestions': ["మందు మిస్ అయితే ఏమి చేయాలి?", "డాక్టర్‌ను ఎప్పుడు సంప్రదించాలి?"]
            }

        if any(word in msg_lower for word in ['blood pressure', 'hypertension', 'bp', 'high pressure', 'రక్తపోటు']):
            return {
                'text': GENERAL_RESPONSES_TE['blood_pressure'],
                'source': 'rule_based_telugu',
                'suggestions': ["రక్తపోటు కోసం ఆహార సూచనలు", "BP ఎలా తగ్గించాలి?"]
            }

        if any(word in msg_lower for word in ['blood sugar', 'diabetes', 'glucose', 'insulin', 'షుగర్', 'డయాబెటిస్']):
            return {
                'text': GENERAL_RESPONSES_TE['blood_sugar'],
                'source': 'rule_based_telugu',
                'suggestions': ["డయాబెటిస్ ఆహార సూచనలు", "షుగర్‌ను ఎలా నియంత్రించాలి?"]
            }

        if any(word in msg_lower for word in ['diet', 'food', 'eat', 'nutrition', 'what should i eat', 'ఆహారం', 'ఏం తినాలి']):
            return {
                'text': GENERAL_RESPONSES_TE['diet'],
                'source': 'rule_based_telugu',
                'suggestions': ["ఆరోగ్యకరమైన ఆహార సూచనలు", "వృద్ధుల ఆహారం ఎలా ఉండాలి?"]
            }

        if any(word in msg_lower for word in ['side effect', 'adverse effect', 'reaction to medicine', 'పార్శ్వ ఫలితం', 'పార్శ్వ']):
            return {
                'text': GENERAL_RESPONSES_TE['side_effects'],
                'source': 'rule_based_telugu',
                'suggestions': ["పార్శ్వ ఫలితాలు ఏమిటి?", "డాక్టర్‌ను ఎప్పుడు సంప్రదించాలి?"]
            }

        if any(word in msg_lower for word in ['doctor', 'డాక్టర్', 'సంప్రదించాలి', 'వైద్యుడిని', 'ఎప్పుడు']):
            return {
                'text': (
                    "మీకు డాక్టర్‌ను సంప్రదించవలసినప్పుడు: \n"
                    "- శ్వాస తీసుకోవటంలో ఇబ్బంది ఉంటే, \n"
                    "- గట్టిగా తలనొప్పి లేదా వాంతులు వస్తే, \n"
                    "- రక్తపోటు లేదా షుగర్ అధికంగా లేదా తక్కువగా మారితే, \n"
                    "- కొత్త లేదా తీవ్రమైన లక్షణాలు ఉంటే. \n"
                    "అన్ని సందర్భాల్లో, వెంటనే మీ వైద్యుడిని లేదా సంరక్షకుడిని సంప్రదించండి."
                ),
                'source': 'rule_based_telugu',
                'suggestions': ["డాక్టర్‌ను ఎప్పుడు కలవాలి?", "అత్యవసర లక్షణాలు ఏమిటి?"]
            }

        # Check for medicine query (WITH or WITHOUT elder context)
        if any(word in msg_lower for word in ['my medicines today', 'today medicines', 'what medicines', 'pending medicines', 'which medicines', 'medicines today', 'what medicine', 'medicines for today', 'ఈరోజు మందులు', 'మందులు ఏమిటి', 'నా మందులు', 'తదుపరి మందు', 'next medicine', 'next dose', 'తదుపరి']):
            if elder_context and elder_context.get('medicines'):
                meds = elder_context.get('medicines', [])
                names = ', '.join(f"{m['name']} {m['dosage']}" for m in meds[:5]) if meds else 'సెట్ చేయబడలేదు'
                return {
                    'text': (
                        f"**{elder_context['name']}** మందులు: {names}. "
                        "ఖచ్చిత సమయాల కోసం షెడ్యూల్ పేజీని చూడండి."
                    ),
                    'source': 'rule_based_telugu',
                    'suggestions': ["అదే తీసుకున్నా చేర్చండి", "తదుపరి మందు ఏమిటి?"]
                }
            else:
                # No elder context selected - provide helpful guidance
                return {
                    'text': (
                        "మీ మందులను చూడటానికి, దయచేసి కుడివైపున ఉన్న '**రోగి సందర్భం**' నుండి రోగిని ఎంచుకోండి. "
                        "తరువాత, నేను మీ వ్యక్తిగత మందుల యొక్క సమాచారం చూపుతాను."
                    ),
                    'source': 'rule_based_telugu',
                    'suggestions': ["డాక్టర్‌ను సంప్రదించండి", "మందు సమాచారం"]
                }

        return None

    def _get_openai_response(self, message: str, history: list = None,
                              elder_context: dict = None, language: str = 'en') -> dict:
        """Get response from OpenAI GPT with optimized timeout and token limits."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_api_key)

            system_prompt = (
                "You are a helpful healthcare assistant for elderly patients. "
                "Provide accurate, clear, and empathetic information about medications, "
                "health conditions, and wellness. Always remind users to consult their "
                "doctor for medical decisions. Keep responses concise and easy to understand. "
                "If the user asks in Telugu, answer in Telugu. Use simple, calm language."
            )

            if elder_context:
                system_prompt += (
                    f"\n\nCurrent patient context: {elder_context['name']}, age {elder_context['age']}. "
                    f"Medical conditions: {elder_context.get('medical_conditions', 'Not specified')}. "
                    f"Allergies: {elder_context.get('allergies', 'None known')}. "
                    f"Current medications: {', '.join(m['name'] for m in elder_context.get('medicines', []))}."
                )

            if language == 'te':
                system_prompt += (
                    "\n\nThe user selected Telugu. Answer in Telugu even if the question is written in English. "
                    "Use simple, empathetic Telugu and keep medical guidance clear."
                )
            else:
                system_prompt += "\n\nAnswer in English."

            messages = [{'role': 'system', 'content': system_prompt}]
            if history:
                messages.extend(history[-4:])  # Reduced from 6 to 4 for faster processing
            messages.append({'role': 'user', 'content': message})

            response = client.chat.completions.create(
                model='gpt-3.5-turbo',
                messages=messages,
                max_tokens=280,  # Reduced from 320 for faster responses
                temperature=0.25,
                top_p=0.95,  # Slightly reduced for consistency
                frequency_penalty=0.1,
                presence_penalty=0.0,
                timeout=12  # Reduced from 15 to 12 seconds
            )

            reply = getattr(response.choices[0].message, 'content', '')
            if not reply or not reply.strip():
                raise ValueError('Received empty response from OpenAI')

            return {
                'text': reply.strip(),
                'source': 'openai',
                'suggestions': [
                    "What are the side effects?",
                    "How to improve adherence?",
                    "Diet recommendations?"
                ]
            }
        except Exception as e:
            logger.warning(f"OpenAI API error (using fallback): {str(e)}")
            raise  # Re-raise so caller can fall back to rule-based
