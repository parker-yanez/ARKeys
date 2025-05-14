#!/usr/bin/env python3
"""
host_ws.py — Host-side keystroke listener + WebSocket server
Streams real-time typing metrics with smart mode switching and burst metrics
to any connected WebSocket client at ws://<host_ip>:8765

Features:
- Smart mode switching between idle and typing
- Sliding window WPM calculation that prevents decay when inactive
- Peak WPM tracking for each typing burst
- Continuous streaming of metrics to connected clients
"""

import asyncio
import json
import threading
import time
import signal
import logging
import os
from spellchecker import SpellChecker
from pynput import keyboard
import websockets
from datetime import datetime
from collections import deque

# ─── CONFIGURATION ─────────────────────────────────────────────────────────────

WS_PORT = 8765          # WebSocket server port
IDLE_THRESHOLD = 30.0   # Seconds without typing before entering idle mode
UPDATE_INTERVAL = 1.0   # Seconds between updates to clients
SLIDING_WINDOW = 60.0   # Seconds to look back for WPM calculation
MAX_WORD_EVENTS = 500   # Maximum number of timestamps to store
INACTIVE_WPM_FREEZE = 5.0  # Seconds after last word before freezing WPM calculation

# ─── LOGGING SETUP ──────────────────────────────────────────────────────────────

os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/typing_tracker.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("typing_tracker")

# ─── APPLICATION STATE ─────────────────────────────────────────────────────────

# Metrics state (guarded by lock)
total_words = 0          # Total words typed in session
correct_words = 0        # Words that passed spell check
word_buffer = []         # Current word being typed
word_events = deque(maxlen=MAX_WORD_EVENTS)  # Timestamps of completed words
session_start = None     # When typing first began
last_ts = None           # Timestamp of most recent keystroke
idle_time = 0.0          # Cumulative idle time to subtract

# Mode state
current_mode = "idle"    # Current typing state: "idle" or "typing"
peak_wpm = 0.0           # Highest WPM in current burst
last_wpm = 0.0           # Last calculated WPM (to prevent decay)
last_word_time = 0.0     # Time of most recent word completion
refresh_flag = False     # Indicates mode switch (for full refresh)
running = True           # Global running state

# Thread safety
metrics_lock = threading.Lock()
active_connections = set()

# ─── SPELL CHECKER ──────────────────────────────────────────────────────────────

spell = SpellChecker()

# ─── KEYSTROKE HANDLING ─────────────────────────────────────────────────────────

def on_press(key):
    """Pynput callback for each keypress."""
    global total_words, correct_words, word_buffer, session_start, last_ts, idle_time
    global current_mode, peak_wpm, refresh_flag, last_word_time

    now = time.time()
    
    # Start the session timer on first keystroke
    if session_start is None:
        session_start = now
    
    # Check for idle gap
    if last_ts is not None:
        gap = now - last_ts
        if gap > IDLE_THRESHOLD:
            idle_time += gap
            # Coming back from idle
            with metrics_lock:
                if current_mode == "idle":
                    # Transition: idle -> typing
                    current_mode = "typing"
                    peak_wpm = 0.0
                    refresh_flag = True
                    # Clear old word events when resuming from idle
                    word_events.clear()
                    logger.info("Mode transition: idle -> typing")
    
    # Update last keystroke time
    last_ts = now
    
    try:
        # Handle regular character keys
        ch = key.char
        if ch:  # Only append if character is not None
            word_buffer.append(ch)
            
    except AttributeError:
        # Handle special keys
        if key in (keyboard.Key.space, keyboard.Key.enter):
            w = ''.join(word_buffer).strip()
            if w:
                with metrics_lock:
                    # Count word and check spelling
                    total_words += 1
                    if w in spell:
                        correct_words += 1
                    
                    # Record word completion timestamp
                    word_events.append(now)
                    last_word_time = now
                    
                    # Ensure we're in typing mode
                    if current_mode == "idle":
                        # Transition: idle -> typing on word completion
                        current_mode = "typing"
                        peak_wpm = 0.0
                        refresh_flag = True
                        logger.info("Mode transition: idle -> typing (word completion)")
            
            # Clear buffer for next word
            word_buffer.clear()
            
        elif key == keyboard.Key.backspace:
            if word_buffer:
                word_buffer.pop()

def keyboard_listener():
    """Run the keyboard listener in a separate thread."""
    logger.info("Starting keyboard listener")
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    
    while running:
        time.sleep(0.1)
    
    listener.stop()
    logger.info("Keyboard listener stopped")

# ─── METRICS CALCULATION ─────────────────────────────────────────────────────────

def calculate_metrics():
    """Calculate current typing metrics with stable WPM during inactivity"""
    with metrics_lock:
        now = time.time()
        
        # Calculate active typing time
        active_time = 0.0
        if session_start:
            active_time = now - session_start - idle_time
        
        # Calculate WPM using sliding window of recent word events
        wpm = 0.0
        global last_wpm
        
        recent_words = [ts for ts in word_events if now - ts <= SLIDING_WINDOW]
        
        if recent_words:
            # Check if we've had any activity in the last few seconds
            most_recent_word = max(recent_words)
            time_since_last_word = now - most_recent_word
            
            # If we have enough words in the window, calculate WPM
            word_count = len(recent_words)
            if word_count >= 2:  # Need at least 2 words for meaningful rate
                # Time span from first to last word in window
                span = most_recent_word - recent_words[0]
                
                # If idle for more than INACTIVE_WPM_FREEZE seconds, freeze the WPM calculation
                # This prevents WPM decay when you stop typing
                if time_since_last_word > INACTIVE_WPM_FREEZE:
                    # Keep using the last active calculation
                    wpm = last_wpm
                elif span > 0:
                    # Normal WPM calculation during active typing
                    wpm = (word_count / span) * 60.0
                    # Remember this WPM for when we go inactive
                    last_wpm = wpm
        
        # Update peak WPM if this is higher
        global peak_wpm
        if wpm > peak_wpm and wpm > 0:
            peak_wpm = wpm
        
        # Calculate accuracy
        accuracy = 100.0
        if total_words > 0:
            accuracy = (correct_words / total_words) * 100.0
        
        # Handle mode transition: typing -> idle
        global current_mode, refresh_flag
        if current_mode == "typing" and (now - last_ts > IDLE_THRESHOLD if last_ts else True):
            current_mode = "idle"
            refresh_flag = True
            logger.info("Mode transition: typing -> idle")
        
        # Prepare the metrics payload
        metrics = {
            "mode": current_mode,
            "wpm": round(wpm, 1),
            "accuracy": round(accuracy, 1),
            "active_time": round(active_time, 1),
            "total_words": total_words,
            "correct_words": correct_words,
            "peak_wpm": round(peak_wpm, 1),
            "refresh": refresh_flag
        }
        
        # Reset the refresh flag after using it
        if refresh_flag:
            refresh_flag = False
        
        return metrics

# ─── WEBSOCKET SERVER ────────────────────────────────────────────────────────────

async def metrics_producer(websocket):
    """
    Sends a JSON payload of current metrics every UPDATE_INTERVAL seconds
    to the connected client.
    """
    client_id = id(websocket)
    logger.info(f"Client {client_id} connected")
    active_connections.add(websocket)
    
    try:
        # Initial metrics send right away
        metrics = calculate_metrics()
        await websocket.send(json.dumps(metrics))
        
        # Main update loop
        while running:
            await asyncio.sleep(UPDATE_INTERVAL)
            
            # Calculate current metrics
            metrics = calculate_metrics()
            
            # Send to client
            await websocket.send(json.dumps(metrics))
            
    except websockets.ConnectionClosed:
        logger.info(f"Client {client_id} disconnected")
    except Exception as e:
        logger.error(f"Error in metrics_producer for client {client_id}: {e}")
    finally:
        # Clean up
        if websocket in active_connections:
            active_connections.remove(websocket)
        logger.info(f"Client {client_id} removed. {len(active_connections)} clients remaining")

async def start_server():
    """Start and run the WebSocket server."""
    stop = asyncio.Future()  # Future to signal shutdown
    
    # Signal handler setup
    def handle_stop():
        if not stop.done():
            stop.set_result(None)
    
    # Set up signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        asyncio.get_event_loop().add_signal_handler(sig, handle_stop)
    
    # Start the server
    logger.info(f"Starting WebSocket server on port {WS_PORT}")
    async with websockets.serve(metrics_producer, "0.0.0.0", WS_PORT):
        logger.info(f"Server running at ws://0.0.0.0:{WS_PORT}")
        await stop  # Wait until stop is set
    
    logger.info("WebSocket server stopped")

# ─── SIGNAL HANDLERS ─────────────────────────────────────────────────────────────

def signal_handler(sig, frame):
    """Handle interrupt signals."""
    global running
    logger.info(f"Received signal {sig}, shutting down...")
    running = False

# ─── MAIN ENTRY POINT ────────────────────────────────────────────────────────────

def main():
    """Main entry point for the application."""
    global running
    
    logger.info("Typing metrics server starting")
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start keyboard listener thread
        keyboard_thread = threading.Thread(target=keyboard_listener, daemon=True)
        keyboard_thread.start()
        
        # Run the WebSocket server in the main thread
        asyncio.run(start_server())
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        # Clean shutdown
        running = False
        logger.info("Application shutting down")

if __name__ == "__main__":
    main()