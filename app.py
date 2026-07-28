from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import uuid
import time
import logging
import gc
from datetime import datetime
from instagram_bot import InstagramBot

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store active sessions
active_sessions = {}

# ==================== ROUTES ====================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'active_sessions': len(active_sessions),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/login', methods=['POST'])
def login():
    """Login using cookie string - returns session_id and username"""
    try:
        data = request.json
        cookie_string = data.get('cookie_string')
        
        if not cookie_string:
            return jsonify({'error': 'cookie_string required'}), 400
        
        # Parse cookies
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
        username = bot.get_username()
        
        active_sessions[session_id] = {
            'bot': bot,
            'created_at': datetime.now().isoformat(),
            'cookies': cookies,
            'username': username,
            'connected': False
        }
        
        logger.info(f"Login successful for session: {session_id} (Username: {username})")
        
        return jsonify({
            'session_id': session_id,
            'username': username,
            'status': 'success',
            'message': 'Login successful'
        })
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/connect-business', methods=['POST'])
def connect_business():
    """Full flow: Connect to Facebook Business Suite - matches boost script exactly"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        
        if session_id not in active_sessions:
            return jsonify({'error': 'Invalid or expired session'}), 401
        
        bot = active_sessions[session_id]['bot']
        username = active_sessions[session_id].get('username', 'Unknown')
        
        logger.info(f"Starting Business Suite connection for session: {session_id} (Username: {username})")
        
        # Connect to Business Suite
        result = bot.connect_to_business_suite()
        
        if result:
            active_sessions[session_id]['connected'] = True
            
            # Get final URL with asset_id
            current_url = bot.get_current_url()
            
            # Extract asset_id and business_id from URL
            asset_id = None
            business_id = None
            if current_url:
                import re
                asset_match = re.search(r'asset_id=(\d+)', current_url)
                if asset_match:
                    asset_id = asset_match.group(1)
                business_match = re.search(r'business_id=(\d+)', current_url)
                if business_match:
                    business_id = business_match.group(1)
            
            return jsonify({
                'status': 'success',
                'connected': True,
                'username': username,
                'asset_id': asset_id,
                'business_id': business_id,
                'message': 'Successfully connected to Meta Business Suite',
                'url': current_url
            })
        else:
            return jsonify({
                'status': 'failed',
                'connected': False,
                'username': username,
                'message': 'Failed to connect to Meta Business Suite'
            }), 500
            
    except Exception as e:
        logger.error(f"Connect Business error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ad-picker', methods=['POST'])
def ad_picker():
    """Navigate to ad picker"""
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
        username = active_sessions[session_id].get('username', 'Unknown')
        
        logger.info(f"Getting ad picker for session: {session_id} (Username: {username})")
        
        url = bot.navigate_to_ad_picker(asset_id, business_id)
        
        if url:
            return jsonify({
                'status': 'success',
                'username': username,
                'url': url
            })
        else:
            return jsonify({
                'status': 'failed',
                'username': username,
                'message': 'Failed to navigate to ad picker'
            }), 500
            
    except Exception as e:
        logger.error(f"Ad picker error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['POST'])
def status():
    """Check session status with username"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if not session_id:
            return jsonify({'error': 'session_id required'}), 400
        
        if session_id not in active_sessions:
            return jsonify({'error': 'Invalid or expired session'}), 401
        
        bot = active_sessions[session_id]['bot']
        session_data = active_sessions[session_id]
        
        return jsonify({
            'status': 'active',
            'session_id': session_id,
            'username': session_data.get('username', 'Unknown'),
            'url': bot.get_current_url(),
            'title': bot.get_page_title(),
            'created_at': session_data['created_at'],
            'connected': session_data.get('connected', False)
        })
        
    except Exception as e:
        logger.error(f"Status error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout and cleanup with full memory free"""
    try:
        data = request.json
        session_id = data.get('session_id')
        
        if session_id and session_id in active_sessions:
            bot = active_sessions[session_id]['bot']
            username = active_sessions[session_id].get('username', 'Unknown')
            
            bot.quit()  # This now clears everything
            del active_sessions[session_id]
            
            logger.info(f"Session {session_id} logged out and cleaned up (Username: {username})")
            
            # Force garbage collection
            gc.collect()
        
        return jsonify({'status': 'success', 'message': 'Logged out and cleaned up'})
        
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """List all active sessions with usernames"""
    sessions_list = []
    for sid, session in active_sessions.items():
        sessions_list.append({
            'session_id': sid,
            'username': session.get('username', 'Unknown'),
            'created_at': session['created_at'],
            'connected': session.get('connected', False)
        })
    
    return jsonify({
        'sessions': sessions_list,
        'count': len(sessions_list)
    })

@app.route('/api/cleanup', methods=['POST'])
def cleanup():
    """Force cleanup of all sessions and resources"""
    try:
        cleared_count = len(active_sessions)
        
        # Close and clean up all sessions
        for session_id in list(active_sessions.keys()):
            try:
                bot = active_sessions[session_id]['bot']
                bot.quit()
            except:
                pass
            del active_sessions[session_id]
        
        # Force garbage collection
        gc.collect()
        
        logger.info(f"Force cleanup completed: {cleared_count} sessions cleared")
        
        return jsonify({
            'status': 'success',
            'message': f'All sessions cleaned up',
            'sessions_cleared': cleared_count
        })
        
    except Exception as e:
        logger.error(f"Cleanup error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'error': 'Method not allowed'}), 405

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

# ==================== HELPER FUNCTIONS ====================

def parse_cookie_string(cookie_str):
    """Parse cookie string into list of cookie dicts"""
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

# ==================== MAIN ====================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
