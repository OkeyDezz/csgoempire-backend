#!/usr/bin/env python3
"""
Entry point for Railway deployment
"""

if __name__ == '__main__':
    # Import and run the license backend
    from license_backend import app, start_background_scheduler
    import os
    
    # Garante que o scheduler em background seja iniciado
    try:
        start_background_scheduler()
    except Exception as e:
        print(f"[WARN] Falha ao iniciar scheduler em background: {e}")
    
    port = int(os.getenv('PORT', 8080))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    print(f"🚀 Starting CSGOEmpire Backend on port {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
