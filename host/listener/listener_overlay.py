#!/usr/bin/env python3
"""
Keystroke listener + Tkinter overlay showing WPM & accuracy.
250×122 px, bottom-right (adjustable), semi-transparent, always-on-top.
"""
import time
import threading
import os
from datetime import datetime
from pynput import keyboard
from spellchecker import SpellChecker
import tkinter as tk
from tkinter import font

# --- Configuration ---
IDLE_THRESHOLD = 10.0  # seconds to subtract when idle
WINDOW_W, WINDOW_H = 250, 122
ALPHA = 0.6
FONT_NAME = 'Tahoma'
ASSETS = os.path.expanduser('~/ARKeys/assets')
TAHOMA_PATH = os.path.join(ASSETS, 'Tahoma.ttf')

# --- State ---
total_words = 0
correct_words = 0
word_buffer = []
session_start = None
last_ts = None
idle_time = 0.0
metrics_lock = threading.Lock()

# Spellchecker
spell = SpellChecker()
# spell.word_frequency.add('ARKkeys')

# Utility
def ordinal(n):
    return f"{n}{'th' if 11<=n%100<=13 else {1:'st',2:'nd',3:'rd'}.get(n%10,'th')}"

# Keystroke handler
def on_press(key):
    global total_words, correct_words, word_buffer, session_start, last_ts, idle_time
    now = time.time()
    if session_start is None:
        session_start = now
    if last_ts is not None:
        gap = now - last_ts
        if gap > IDLE_THRESHOLD:
            idle_time += gap
    last_ts = now
    try:
        k = key.char
    except AttributeError:
        if key in (keyboard.Key.space, keyboard.Key.enter):
            word = ''.join(word_buffer).strip()
            if word:
                total_words += 1
                if word in spell:
                    correct_words += 1
            word_buffer.clear()
        elif key == keyboard.Key.backspace:
            if word_buffer:
                word_buffer.pop()
    else:
        word_buffer.append(k)

# Listener thread
def start_listener():
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

# Overlay UI
class OverlayApp:
    def __init__(self):
        self.root = tk.Tk()
        self.visible = True
        self.setup_window()
        self.load_fonts()
        self.create_widgets()
        self.update_ui()
        self.root.bind('<Control-o>', self.toggle)

    def setup_window(self):
        self.root.overrideredirect(True)
        self.root.lift()
        # always on top & alpha via wm_attributes
        self.root.wm_attributes('-topmost', True)
        self.root.wm_attributes('-alpha', ALPHA)
        self.root.configure(bg='black')
        # reposition -- test at top-left first
        # x, y = sw - WINDOW_W - 10, sh - WINDOW_H - 40  # bottom-right
        x, y = 0, 0  # debugging at top-left
        self.root.geometry(f"{WINDOW_W}x{WINDOW_H}+{x}+{y}")
        self.root.update()  # force window draw

    def load_fonts(self):
        if os.path.exists(TAHOMA_PATH):
            self.font_large = font.Font(file=TAHOMA_PATH, size=48)
            self.font_small = font.Font(file=TAHOMA_PATH, size=20)
        else:
            self.font_large = font.Font(family=FONT_NAME, size=48)
            self.font_small = font.Font(family=FONT_NAME, size=20)

    def create_widgets(self):
        self.wpm_label = tk.Label(self.root, text="0.0 WPM", font=self.font_large, fg='white', bg='black')
        self.wpm_label.place(x=5, y=5)
        self.acc_label = tk.Label(self.root, text="100.0% ACC", font=self.font_small, fg='white', bg='black')
        self.acc_label.place(x=5, y=65)
        self.date_label = tk.Label(self.root, text="", font=self.font_small, fg='white', bg='black')
        self.date_label.place(x=5, y=95)

    def update_ui(self):
        now_ts = time.time()
        with metrics_lock:
            if session_start:
                elapsed = now_ts - session_start - idle_time
            else:
                elapsed = 0.0
            minutes = elapsed/60 if elapsed>0 else 1
            wpm = total_words/minutes
            accuracy = (correct_words/total_words*100) if total_words>0 else 100.0
        self.wpm_label.config(text=f"{wpm:.1f} WPM")
        self.acc_label.config(text=f"{accuracy:.1f}% ACC")
        dt = datetime.now()
        date_str = dt.strftime('%b ')+ordinal(dt.day)
        self.date_label.config(text=date_str)
        self.root.after(1000, self.update_ui)

    def toggle(self, event=None):
        if self.visible:
            self.root.withdraw()
        else:
            self.root.deiconify()
        self.visible = not self.visible

    def run(self):
        self.root.mainloop()

if __name__=='__main__':
    t = threading.Thread(target=start_listener, daemon=True)
    t.start()
    app=OverlayApp()
    app.run()
