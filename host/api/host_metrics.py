#!/usr/bin/env python3
"""
Host-side keystroke listener, WPM & accuracy tracker, and Bottle API server.
Uses PySpellChecker instead of PyEnchant for dictionary lookup.
Persists session summaries to SQLite.
"""
import time
import threading
import sqlite3
import os
import json
from datetime import datetime
from pynput import keyboard
from bottle import Bottle, response, run
from spellchecker import SpellChecker

# Configuration
ROOT = os.path.expanduser('~/ARKeys')
DB_PATH = os.path.join(ROOT, 'data', 'sessions.db')
IDLE_THRESHOLD = 10.0  # seconds

# Ensure data folder exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Initialize spellchecker
spell = SpellChecker()

# Metrics state
total_words = 0
correct_words = 0
word_buffer = []
last_ts = None
idle_time = 0.0
session_start = None
metrics_lock = threading.Lock()

# SQLite setup
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY,
            start_ts TEXT,
            end_ts TEXT,
            duration REAL,
            words INTEGER,
            correct INTEGER,
            wpm REAL,
            accuracy REAL
        )
    ''')
    conn.commit()
    conn.close()

# Record session summary on exit
def save_session():
    if session_start is None:
        return
    end_ts = time.time()
    active = (end_ts - session_start) - idle_time
    wpm = (total_words / active * 60) if active > 0 else 0.0
    accuracy = (correct_words / total_words * 100) if total_words > 0 else 100.0
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'INSERT INTO sessions (start_ts, end_ts, duration, words, correct, wpm, accuracy) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (datetime.fromtimestamp(session_start).isoformat(),
         datetime.fromtimestamp(end_ts).isoformat(),
         active, total_words, correct_words, wpm, accuracy)
    )
    conn.commit()
    conn.close()

# Keystroke callback
def on_press(key):
    global total_words, correct_words, word_buffer, last_ts, idle_time, session_start
    now = time.time()
    # Initialize session start
    if session_start is None:
        session_start = now
    # Idle handling
    if last_ts is not None:
        gap = now - last_ts
        if gap > IDLE_THRESHOLD:
            idle_time += gap
    last_ts = now
    try:
        char = key.char
    except AttributeError:
        if key in (keyboard.Key.space, keyboard.Key.enter):
            word = ''.join(word_buffer).strip()
            if word:
                total_words += 1
                # robust: only final word state counts
                if word in spell:
                    correct_words += 1
            word_buffer.clear()
        elif key == keyboard.Key.backspace:
            if word_buffer:
                word_buffer.pop()
    else:
        word_buffer.append(char)

# API server setup
app = Bottle()

@app.get('/metrics')
def metrics():
    now = time.time()
    active = ((now - session_start) - idle_time) if session_start else 0.0
    wpm = (total_words / active * 60.0) if active > 0 else 0.0
    accuracy = (correct_words / total_words * 100.0) if total_words > 0 else 100.0
    response.content_type = 'application/json'
    return json.dumps({
        'wpm': round(wpm, 1),
        'accuracy': round(accuracy, 1),
        'active_time': round(active, 1),
        'total_words': total_words,
        'correct_words': correct_words
    })

# Listener thread
def start_listener():
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

if __name__ == '__main__':
    # Initialize database
    init_db()
    # Ensure session saved on exit
    import atexit
    atexit.register(save_session)
    # Start keystroke listener
    t = threading.Thread(target=start_listener, daemon=True)
    t.start()
    # Run Bottle server
    run(app, host='0.0.0.0', port=8000)
