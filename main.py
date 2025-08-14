# main.py (Temporary Diagnostic Version)

import os
import logging
from flask import Flask

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

@app.route('/')
def hello():
    """A simple hello world endpoint."""
    app.logger.info("Hello World root page was requested.")
    return "It's alive!", 200

@app.route('/api/health')
def health_check():
    """A minimal health check."""
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))