from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import time
import threading
import uuid
import os
import logging
from datetime import datetime
from instagram_bot import InstagramBot

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Store active sessions
active_sessions = {}
session_lock = threading.Lock()

# Cleanup inactive sessions every 30 minutes
def cleanup_sessions():
    while True:
        time.sleep(1800)  # 30 minutes
        with session_lock:
            now = datetime.now()
            expired_sessions = []
            for sid, session in active_sessions.items():
                created = datetime.fromisoformat(session['created_at'])
                if (now - created).seconds > 1800:  # 30 minutes timeout
                    try:
                        session['bot'].quit()
                    except:
                        pass
                    expired_sessions.append(sid)
            for sid in expired_sessions:
                del active_sessions[sid]
            if expired_sessions:
                logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_sessions, daemon=True)
cleanup_thread.start()

def parse_cookie_string(cookie_str):
    """Parse cookie string format: key1=value1; key2=value2"""
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

@app.route('/health', methods=['GET'])
def health_check():
    with session_lock:
        return jsonify({
            'status': 'healthy',
            'active_sessions': len(active_sessions),
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/login', methods=['POST'])
def login_instagram():
    """Login to Instagram using credentials or cookies"""
    data = request.json
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    session_id = str(uuid.uuid4())
    bot = None
    
    try:
        logger.info(f"New login attempt: {session_id}")
        bot = InstagramBot(headless=True)
        
        # Determine login method
        if data.get('cookie_string'):
            # Handle cookie string directly
            cookie_str = data['cookie_string']
            cookies = parse_cookie_string(cookie_str)
            if not cookies:
                return jsonify({'error': 'Invalid cookie string format'}), 400
            success = bot.login_with_cookies(cookies)
            
        elif data.get('cookies'):
            # Cookie array format
            cookies = data['cookies']
            if isinstance(cookies, str):
                cookies = parse_cookie_string(cookies)
            success = bot.login_with_cookies(cookies)
            
        elif data.get('username') and data.get('password'):
            # Credential-based login
            success = bot.login_with_credentials(
                data['username'], 
                data['password'],
                data.get('two_factor_key')
            )
        else:
            return jsonify({'error': 'Either cookie_string, cookies, or username/password required'}), 400
        
        if not success:
            if bot:
                bot.quit()
            return jsonify({'error': 'Login failed - invalid credentials or cookies expired'}), 401
        
        # Store session info
        with session_lock:
            active_sessions[session_id] = {
                'bot': bot,
                'created_at': datetime.now().isoformat(),
                'status': 'logged_in'
            }
        
        logger.info(f"Login successful: {session_id}")
        
        return jsonify({
            'session_id': session_id,
            'status': 'success',
            'message': 'Login successful'
        })
        
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        if bot:
            try:
                bot.quit()
            except:
                pass
        return jsonify({'error': str(e)}), 500

@app.route('/api/connect-ad-account', methods=['POST'])
def connect_ad_account():
    """Connect Instagram to Meta Business Suite / Ad Account"""
    data = request.json
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'error': 'session_id required'}), 400
    
    with session_lock:
        if session_id not in active_sessions:
            return jsonify({'error': 'Invalid or expired session'}), 401
        
        bot = active_sessions[session_id]['bot']
    
    try:
        logger.info(f"Connecting ad account for session: {session_id}")
        result = bot.connect_to_business_suite()
        
        return jsonify({
            'status': 'success' if result else 'failed',
            'connected': result,
            'url': bot.get_current_url() if result else None
        })
        
    except Exception as e:
        logger.error(f"Connect ad account error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get-ad-picker', methods=['POST'])
def get_ad_picker():
    """Navigate to the Boosted Post Picker page"""
    data = request.json
    session_id = data.get('session_id')
    asset_id = data.get('asset_id')
    business_id = data.get('business_id')
    
    if not session_id:
        return jsonify({'error': 'session_id required'}), 400
    
    if not asset_id:
        return jsonify({'error': 'asset_id required'}), 400
    
    with session_lock:
        if session_id not in active_sessions:
            return jsonify({'error': 'Invalid or expired session'}), 401
        
        bot = active_sessions[session_id]['bot']
    
    try:
        logger.info(f"Getting ad picker for session: {session_id}")
        url = bot.navigate_to_ad_picker(asset_id, business_id)
        
        return jsonify({
            'status': 'success',
            'url': url
        })
        
    except Exception as e:
        logger.error(f"Get ad picker error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['POST'])
def get_status():
    """Get current browser status and URL"""
    data = request.json
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'error': 'session_id required'}), 400
    
    with session_lock:
        if session_id not in active_sessions:
            return jsonify({'error': 'Invalid or expired session'}), 401
        
        bot = active_sessions[session_id]['bot']
    
    try:
        url = bot.get_current_url()
        title = bot.get_page_title()
        
        return jsonify({
            'status': 'active',
            'url': url,
            'title': title,
            'session_id': session_id
        })
        
    except Exception as e:
        logger.error(f"Status check error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """Close browser session"""
    data = request.json
    session_id = data.get('session_id')
    
    if session_id:
        with session_lock:
            if session_id in active_sessions:
                try:
                    active_sessions[session_id]['bot'].quit()
                except:
                    pass
                del active_sessions[session_id]
                logger.info(f"Session logged out: {session_id}")
        
    return jsonify({'status': 'success', 'message': 'Session closed'})

@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """List all active sessions"""
    with session_lock:
        sessions_info = []
        for sid, session in active_sessions.items():
            sessions_info.append({
                'session_id': sid,
                'created_at': session['created_at'],
                'status': session.get('status', 'unknown')
            })
        
        return jsonify({
            'sessions': sessions_info,
            'count': len(sessions_info)
        })

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
