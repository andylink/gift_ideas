from flask import Blueprint, request, jsonify
from app.services.gift_service import GiftService
from app.services.nlp_service import NLPService
from http import HTTPStatus
from config import Config  # Add this import

api_bp = Blueprint('api', __name__)
gift_service = GiftService()
nlp_service = NLPService(use_openai=Config.USE_OPENAI)

@api_bp.route('/api/find-gifts', methods=['POST'])
def find_gifts():
    try:
        # Make sure we're getting JSON data
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': 'Content-Type must be application/json'
            }), HTTPStatus.BAD_REQUEST

        data = request.get_json()
        
        # Check if data is None or if description is missing
        if not data or 'description' not in data:
            return jsonify({
                'success': False,
                'error': 'Description is required'
            }), HTTPStatus.BAD_REQUEST
            
        description = data['description']  # Using direct dictionary access
        
        # Extract criteria using NLP
        criteria = nlp_service.extract_gift_criteria(description)
        
        # Find gifts based on criteria
        gifts = gift_service.find_gifts(criteria)
        
        return jsonify({
            'success': True,
            'criteria': criteria,
            'gifts': [gift.to_dict() for gift in gifts]
        }), HTTPStatus.OK
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), HTTPStatus.INTERNAL_SERVER_ERROR