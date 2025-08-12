#!/usr/bin/env python3
"""
Entry point for Railway deployment
"""

if __name__ == '__main__':
    # Import and run the license backend
    from license_backend import app
    import os
    
    port = int(os.getenv('PORT', 8080))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    print(f"🚀 Starting CSGOEmpire Backend on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
