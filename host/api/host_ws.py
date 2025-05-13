#!/usr/bin/env python3
"""
host_ws.py — Host-side keystroke listener + WebSocket server
Streams JSON metrics (wpm, accuracy, active_time, total_words, correct_words)
to any connected WebSocket client at ws://<host_ip>:8765
"""

import asyncio
import json
import threading
import time
from spellchecker import SpellChecker
from pynput import keyboard
import websockets

# Configuration
WS_PORT         = 8765
IDLE_THRESHOLD  = 10.0   # seconds
UPDATE_INTERVAL = 1.0    # seconds between pushes

# Metrics state (guarded by lock)
total_words   = 0
correct_words = 0
word_buffer   = []
session_start = None
last_ts       = None
idle_time     = 0.0
metrics_lock  = threading.Lock()

# Spell checker
spell = SpellChecker()

def on_press(key):
    """Pynput callback for each keypress."""
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
        ch = key.char
    except AttributeError:
        if key in (keyboard.Key.space, keyboard.Key.enter):
            w = ''.join(word_buffer).strip()
            if w:
                with metrics_lock:
                    total_words += 1
                    if w in spell:
                        correct_words += 1
            word_buffer.clear()
        elif key == keyboard.Key.backspace:
            if word_buffer:
                word_buffer.pop()
    else:
        word_buffer.append(ch)

def start_listener():
    """Run the keyboard listener in its own thread."""
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

async def metrics_producer(websocket):
    """
    Sends a JSON payload of current metrics every UPDATE_INTERVAL seconds
    to each connected client.
    """
    try:
        while True:
            await asyncio.sleep(UPDATE_INTERVAL)
            with metrics_lock:
                if session_start:
                    active = time.time() - session_start - idle_time
                else:
                    active = 0.0
                minutes = active / 60 if active > 0 else 1e-6
                wpm = total_words / minutes
                accuracy = (correct_words / total_words * 100) if total_words > 0 else 100.0
                payload = {
                    "wpm":           round(wpm, 1),
                    "accuracy":      round(accuracy, 1),
                    "active_time":   round(active, 1),
                    "total_words":   total_words,
                    "correct_words": correct_words
                }
            await websocket.send(json.dumps(payload))
    except websockets.ConnectionClosed:
        pass

async def ws_main():
    """Starts the WebSocket server and keeps it running."""
    print(f"Starting WebSocket metrics server on port {WS_PORT}…")
    async with websockets.serve(metrics_producer, "0.0.0.0", WS_PORT):
        await asyncio.Future()  # run forever

def main():
    # 1) Start the keystroke listener
    threading.Thread(target=start_listener, daemon=True).start()
    # 2) Start the WebSocket server
    asyncio.run(ws_main())

if __name__ == "__main__":
    main()
