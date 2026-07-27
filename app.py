from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import time
import uuid
import os
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Store active sessions
active_sessions = {}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Railway"""
    return jsonify({
        'status': 'healthy',
        'active_sessions': len(active_sessions),
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/api/login', methods=['POST'])
def login():
    """Login with cookie string"""
    try:
        data = request.json
        cookie_string = data.get('cookie_string')
        
        if not cookie_string:
            return jsonify({'error': 'cookie_string required'}), 400
        
        # Parse cookies
        cookies = []
        for pair in cookie_string.split(';'):
            pair = pair.strip()
            if '=' in pair:
                key, value = pair.split('=', 1)
                cookies.append({
                    'name': key.strip(),
                    'value': value.strip(),
                    'domain': '.instagram.com',
                    'path': '/'
                })
        
        # Create session
        session_id = str(uuid.uuid4())
        
        # Import InstagramBot here to avoid startup issues
        try:
            from instagram_bot import InstagramBot
            bot = InstagramBot(headless=True)
            success = bot.login_with_cookies(cookies)
            
            if success:
                active_sessions[session_id] = {
                    'bot': bot,
                    'created_at': datetime.now().isoformat()
                }
                return jsonify({
                    'session_id': session_id,
                    'status': 'success'
                })
            else:
                bot.quit()
                return jsonify({'error': 'Login failed'}), 401
                
        except ImportError:
            logger.warning("InstagramBot not available, using mock mode")
            active_sessions[session_id] = {
                'mock': True,
                'created_at': datetime.now().isoformat()
            }
            return jsonify({
                'session_id': session_id,
                'status': 'success',
                'mock': True
            })
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/connect', methods=['POST'])
def connect():
    """Connect to Business Suite"""
    data = request.json
    session_id = data.get('session_id')
    
    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Invalid session'}), 401
    
    session = active_sessions[session_id]
    
    if session.get('mock'):
        return jsonify({
            'status': 'success',
            'connected': True,
            'mock': True
        })
    
    try:
        bot = session['bot']
        result = bot.connect_to_business_suite()
        return jsonify({
            'status': 'success',
            'connected': result
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['POST'])
def status():
    """Get session status"""
    data = request.json
    session_id = data.get('session_id')
    
    if not session_id or session_id not in active_sessions:
        return jsonify({'error': 'Invalid session'}), 401
    
    session = active_sessions[session_id]
    
    if session.get('mock'):
        return jsonify({
            'status': 'active',
            'mock': True,
            'url': 'https://instagram.com'
        })
    
    try:
        bot = session['bot']
        url = bot.get_current_url()
        return jsonify({
            'status': 'active',
            'url': url
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout and cleanup"""
    data = request.json
    session_id = data.get('session_id')
    
    if session_id and session_id in active_sessions:
        session = active_sessions[session_id]
        if not session.get('mock'):
            try:
                session['bot'].quit()
            except:
                pass
        del active_sessions[session_id]
    
    return jsonify({'status': 'success'})

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting server on port {port}")
    # Use simple server for better compatibility
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
