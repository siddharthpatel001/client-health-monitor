"""
WSGI entry point for production deployment with Gunicorn.

Usage:
    # Single worker (recommended for APScheduler compatibility)
    gunicorn -w 1 -b 0.0.0.0:5001 --timeout 120 wsgi:app

    # Or use the config file
    gunicorn -c gunicorn_config.py wsgi:app
"""

from app import app

# Just export the app - scheduler is already initialized in app.py
# No additional setup needed here

if __name__ == '__main__':
    # For development/testing
    app.run(host='0.0.0.0', debug=True, port=5001)

