"""
🖥️  Smart Scout Web UI — Flask Application Entry Point
========================================================
Vayne Consulting — Smart Scout Multi-Industry Edition

Run with:
    py -3.10 webapp/app.py

Then open: http://localhost:5000
"""

import sys
import os

# Make smart_scout/ importable from webapp/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from routes.api import api_bp
from routes.stream import stream_bp

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "vayne-scout-ui-2026"

# Register blueprints
app.register_blueprint(api_bp, url_prefix="/api")
app.register_blueprint(stream_bp, url_prefix="/stream")

# Serve the SPA
from flask import render_template

@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    import webbrowser
    import threading

    def open_browser():
        import time
        time.sleep(1.2)
        webbrowser.open("http://localhost:5000")

    threading.Thread(target=open_browser, daemon=True).start()
    app.run(debug=False, host="127.0.0.1", port=5000, threaded=True)
