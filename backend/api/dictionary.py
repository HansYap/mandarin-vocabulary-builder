# backend/api/dictionary.py
from flask import Blueprint, request, jsonify
from backend.services.dictionary_handler import get_dictionary_service

dictionary_bp = Blueprint('dictionary', __name__)

@dictionary_bp.route('/lookup', methods=['POST'])
def lookup_word():
    """
    Lookup a single Chinese word
    
    Request body:
    {
        "word": "预订",
        "prefer_longer": true  // optional, default true
    }
    
    Response:
    {
        "success": true,
        "word": "预订",
        "entry": {
            "found": true,
            "simplified": "预订",
            "traditional": "預訂",
            "pinyin": "yu4 ding4",
            "definitions": ["to place an order", "to book ahead"]
        }
    }
    """
    try:
        data = request.get_json()
        word = data.get('word', '').strip()
        prefer_longer = data.get('prefer_longer', True)
        
        if not word:
            return jsonify({
                'success': False,
                'error': 'No word provided'
            }), 400
        
        dict_service = get_dictionary_service()
        result = dict_service.lookup(word, prefer_longer=prefer_longer)
        
        if result.get("found"):
            return jsonify({
                'success': True,
                'word': word,
                'entry': result
            }), 200
        else:
            return jsonify({
                'success': False,
                'word': word,
                'error': result.get("message", "Word not found"),
                'entry': result
            }), 404
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


