import gc
import psutil
import os

# Add after login endpoint
@app.route('/api/cleanup', methods=['POST'])
def cleanup():
    """Force cleanup of resources"""
    gc.collect()
    
    # Close any zombie browser processes
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if 'chrome' in proc.info['name'].lower() or 'chromedriver' in proc.info['name'].lower():
                proc.kill()
        except:
            pass
    
    return jsonify({'status': 'cleaned'})

# Add session cleanup after each request
@app.after_request
def after_request(response):
    gc.collect()
    return response
