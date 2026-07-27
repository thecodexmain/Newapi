from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import uuid
import time
import logging
from datetime import datetime
from instagram_bot import InstagramBot

app = Flask(__name__)
CORS(app)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store active sessions
active_sessions = {}

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'active_sessions': len(active_sessions),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/login', methods=['POST'])
def login():
    """Login using cookie string - exactly like the script"""
    try:
        data = request.json
        cookie_string = data.get('cookie_string')
        
        if not cookie_string:
            return jsonify({'error': 'cookie_string required'}), 400
        
        # Parse cookies exactly like the script
        cookies = parse_cookie_string(cookie_string)
        
        if not cookies:
            return jsonify({'error': 'No valid cookies found'}), 400
        
        # Create bot instance
        bot = InstagramBot(headless=True)
        
        # Perform cookie login
        success = bot.perform_cookie_login(cookies)
        
        if not success:
            bot.quit()
            return jsonify({'error': 'Cookie login failed - cookies may be expired'}), 401
        
        # Create session
        session_id = str(uuid.uuid4())
        active_sessions[session_id] = {
            'bot': bot,
            'created_at': datetime.now().isoformat(),
            'cookies': cookies
        }
        
        logger.info(f"Login successful for session: {session_id}")
        
        return jsonify({
            'session_id': session_id,
            'status': 'success',
            'message': 'Login successful'
        })
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/connect-business', methods=['POST'])
def connect_business():
    """Full flow: Connect to Facebook Business Suite - exactly like the script"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        
        if session_id not in active_sessions:
            return jsonify({'error': 'Invalid or expired session'}), 401
        
        bot = active_sessions[session_id]['bot']
        
        logger.info(f"Starting Business Suite connection for session: {session_id}")
        
        # Step 1: Navigate to Facebook Business Suite - exactly like the script
        result = bot.connect_to_business_suite()
        
        if result:
            # Store connection status
            active_sessions[session_id]['connected'] = True
            
            return jsonify({
                'status': 'success',
                'connected': True,
                'message': 'Successfully connected to Meta Business Suite',
                'url': bot.get_current_url()
            })
        else:
            return jsonify({
                'status': 'failed',
                'connected': False,
                'message': 'Failed to connect to Meta Business Suite'
            }), 500
            
    except Exception as e:
        logger.error(f"Connect Business error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ad-picker', methods=['POST'])
def ad_picker():
    """Navigate to ad picker - exactly like the script"""
    try:
        data = request.json
        session_id = data.get('session_id')
        asset_id = data.get('asset_id')
        business_id = data.get('business_id')
        
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        
        if session_id not in active_sessions:
            return jsonify({'error': 'Invalid or expired session'}), 401
        
        if not asset_id:
            return jsonify({'error': 'asset_id required'}), 400
        
        bot = active_sessions[session_id]['bot']
        
        # Navigate to ad picker - exactly like the script
        url = bot.navigate_to_ad_picker(asset_id, business_id)
        
        if url:
            return jsonify({
                'status': 'success',
                'url': url
            })
        else:
            return jsonify({
                'status': 'failed',
                'message': 'Failed to navigate to ad picker'
            }), 500
            
    except Exception as e:
        logger.error(f"Ad picker error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['POST'])
def status():
    """Check session status - exactly like the script"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        
        if session_id not in active_sessions:
            return jsonify({'error': 'Invalid or expired session'}), 401
        
        bot = active_sessions[session_id]['bot']
        
        return jsonify({
            'status': 'active',
            'session_id': session_id,
            'url': bot.get_current_url(),
            'title': bot.get_page_title(),
            'created_at': active_sessions[session_id]['created_at'],
            'connected': active_sessions[session_id].get('connected', False)
        })
        
    except Exception as e:
        logger.error(f"Status error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout and cleanup - exactly like the script"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if session_id and session_id in active_sessions:
            bot = active_sessions[session_id]['bot']
            bot.quit()
            del active_sessions[session_id]
            logger.info(f"Session {session_id} logged out")
        
        return jsonify({'status': 'success', 'message': 'Logged out'})
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """List all active sessions"""
    sessions_list = []
    for sid, session in active_sessions.items():
        sessions_list.append({
            'session_id': sid,
            'created_at': session['created_at'],
            'connected': session.get('connected', False)
        })
    
    return jsonify({
        'sessions': sessions_list,
        'count': len(sessions_list)
    })

def parse_cookie_string(cookie_str):
    """Parse cookie string - exactly like the script"""
    cookies = []
    if not cookie_str:
        return cookies
    
    pairs = cookie_str.strip().split(';')
    for pair in pairs:
        pair = pair.strip()
        if not pair or '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        cookies.append({
            'name': key.strip(),
            'value': value.strip(),
            'domain': '.instagram.com',
            'path': '/'
        })
    
    return cookies

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
