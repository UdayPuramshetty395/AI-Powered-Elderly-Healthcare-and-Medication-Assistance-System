from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.chatbot_service import ChatbotService
from app.models.user import User

chatbot_bp = Blueprint('chatbot', __name__)

# In-memory conversation history (keyed by user_id)
conversation_history = {}


def get_current_user():
    user_id = get_jwt_identity()
    return User.query.get(int(user_id))


@chatbot_bp.route('/message', methods=['POST'])
@jwt_required()
def send_message():
    """Send a message to the AI chatbot and get a response."""
    user = get_current_user()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    message = data.get('message', '').strip()
    elder_id = data.get('elder_id')
    language = data.get('language', 'en')

    if not message:
        return jsonify({'error': 'Message is required'}), 400

    user_id = str(user.id)
    if user_id not in conversation_history:
        conversation_history[user_id] = []

    # Get elder context if provided
    elder_context = None
    if elder_id:
        from app.models.elder import Elder
        from app.models.medicine import Medicine
        elder = Elder.query.get(elder_id)
        if elder:
            meds = Medicine.query.filter_by(elder_id=elder_id, is_active=True).all()
            elder_context = {
                'name': elder.name,
                'age': elder.age,
                'medical_conditions': elder.medical_conditions,
                'allergies': elder.allergies,
                'medicines': [{'name': m.name, 'dosage': m.dosage} for m in meds]
            }

    history = conversation_history[user_id][-10:]  # Keep last 10 exchanges
    service = ChatbotService(current_app.config.get('OPENAI_API_KEY', ''))
    response = service.get_response(message, history, elder_context, language)

    # Store conversation
    conversation_history[user_id].append({'role': 'user', 'content': message})
    conversation_history[user_id].append({'role': 'assistant', 'content': response['text']})

    # Keep only last 20 messages
    if len(conversation_history[user_id]) > 20:
        conversation_history[user_id] = conversation_history[user_id][-20:]

    return jsonify({
        'response': response['text'],
        'source': response['source'],
        'suggestions': response.get('suggestions', []),
        'language': language
    }), 200


@chatbot_bp.route('/history', methods=['GET'])
@jwt_required()
def get_history():
    """Get conversation history for current user."""
    user = get_current_user()
    user_id = str(user.id)
    history = conversation_history.get(user_id, [])
    return jsonify({'history': history}), 200


@chatbot_bp.route('/clear', methods=['DELETE'])
@jwt_required()
def clear_history():
    """Clear conversation history."""
    user = get_current_user()
    user_id = str(user.id)
    conversation_history[user_id] = []
    return jsonify({'message': 'Conversation history cleared'}), 200


@chatbot_bp.route('/suggestions', methods=['GET'])
@jwt_required()
def get_suggestions():
    """Get suggested questions."""
    suggestions = [
        "What are the side effects of Metformin?",
        "When should Metformin be taken?",
        "What foods should be avoided with blood pressure medicine?",
        "How to manage diabetes diet?",
        "What are signs of low blood sugar?",
        "Can I take aspirin with blood thinners?",
        "What is a healthy blood pressure range?",
        "How to improve medication adherence?",
        "What are common drug interactions to avoid?",
        "How to handle a missed dose?"
    ]
    return jsonify({'suggestions': suggestions}), 200
