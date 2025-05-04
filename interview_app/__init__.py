import os
from flask import Flask
from flask_session import Session
from flask_cors import CORS
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=50)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200 MB upload limit

Session(app)
CORS(app)

# ...existing configuration code (e.g. directory creation)...
BASE_DIR = os.getcwd()
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
INTERVIEW_RESULTS_DIR = os.path.join(BASE_DIR, "interview_results")
CHUNKS_DIR = os.path.join(BASE_DIR, "video_chunks")
FINAL_VIDEO_DIR = os.path.join(BASE_DIR, "videos")

for folder in [UPLOADS_DIR, INTERVIEW_RESULTS_DIR, CHUNKS_DIR, FINAL_VIDEO_DIR]:
    os.makedirs(folder, exist_ok=True)

# Register routes by importing the routes module
from interview_app import routes
