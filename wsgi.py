"""
WSGI Entrypoint for AutoBI Production Deployment.
Supports Gunicorn (Linux/Docker) and Waitress (Windows/Cross-platform).
"""

import os
import sys
import logging
from app import create_app
from config import get_config

config = get_config()
application = create_app(config)
app = application  # Alias for standard WSGI servers

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    threads = int(os.environ.get("THREADS", 4))

    print(f"Starting AutoBI Production Server on http://{host}:{port} with {threads} worker threads...")
    
    try:
        from waitress import serve
        serve(application, host=host, port=port, threads=threads)
    except ImportError:
        # Fallback to standard WSGI simple server or Flask run
        print("Waitress not found. Running via built-in server.")
        application.run(host=host, port=port, debug=False)

