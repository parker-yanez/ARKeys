#!/usr/bin/env python3
"""
ARKeys E-ink Display Client

This script connects to a WebSocket server streaming typing metrics
and displays them on a 2.13" Waveshare e-ink display. It toggles
between an idle clock mode and active typing metrics display.

Features:
- Real-time WPM and accuracy display
- Automatic idle/active mode switching
- Efficient partial display updates
- Clean error handling and graceful shutdown
"""

import time
import threading
import json
import os
import logging
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V4
from websocket import WebSocketApp

# ─── CONFIGURATION ───────────────────────────────────────────────────────────────

# WebSocket and App Settings
WS_URL = "ws://192.168.1.225:8765"  # WebSocket server address
IDLE_THRESHOLD = 10.0  # Seconds of inactivity before switching to idle mode
REFRESH_RATE = 1.0     # Screen refresh interval in seconds

# Asset Paths
ASSETS_DIR = os.path.expanduser('~/ARKeys/assets')
TAHOMA_TTF = os.path.join(ASSETS_DIR, 'Tahoma.ttf')
FALLBACK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# Font Sizes
FONT_BIG = 48     # Size for idle clock & WPM display
FONT_CLOCK_SM = 12  # Size for typing-mode clock
FONT_ACC = 18     # Size for accuracy display
SPACING = 5       # Gap between WPM and accuracy display

# Configure logging
os.makedirs(os.path.join(ASSETS_DIR, 'logs'), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(ASSETS_DIR, 'logs', 'display_client.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("display_client")

# ─── APPLICATION STATE ─────────────────────────────────────────────────────────

class DisplayState:
    """Manages the application state and metrics data"""
    def __init__(self):
        # Latest metrics from server
        self.metrics = {
            "wpm": 0.0, 
            "accuracy": 100.0, 
            "total_words": 0,
            "heartbeat": 0
        }
        
        # Values that freeze when a new word is typed
        self.freeze_wpm = 0.0
        self.freeze_acc = 100.0
        
        # Tracking
        self.last_total_words = 0
        self.last_word_ts = 0.0
        self.is_connected = False
        self.running = True
        
    def update_from_message(self, data):
        """Update state based on incoming WebSocket message"""
        self.metrics = data
        new_word_count = data.get("total_words", 0)
        
        # If new words have been typed, update frozen metrics
        if new_word_count > self.last_total_words:
            self.freeze_wpm = data.get("wpm", 0.0)
            self.freeze_acc = data.get("accuracy", 100.0)
            self.last_total_words = new_word_count
            self.last_word_ts = time.time()
            logger.debug(f"New word detected - WPM: {self.freeze_wpm:.1f}, ACC: {self.freeze_acc:.1f}")
            
    @property
    def is_idle(self):
        """Determine if display should be in idle mode"""
        now = time.time()
        return (now - self.last_word_ts) > IDLE_THRESHOLD

# Initialize state
state = DisplayState()

# ─── E-INK DISPLAY SETUP ────────────────────────────────────────────────────────

def setup_display():
    """Initialize and prepare the e-ink display"""
    try:
        logger.info("Initializing e-ink display")
        epd = epd2in13_V4.EPD()
        epd.init()
        epd.Clear(0xFF)  # Clear to white
        return epd, epd.height, epd.width
    except Exception as e:
        logger.error(f"Display initialization failed: {e}")
        raise

# ─── FONT LOADING ─────────────────────────────────────────────────────────────

def load_font(size):
    """Load font with specified size, falling back if needed"""
    try:
        if os.path.exists(TAHOMA_TTF):
            return ImageFont.truetype(TAHOMA_TTF, size)
        return ImageFont.truetype(FALLBACK_FONT, size)
    except Exception as e:
        logger.error(f"Font loading error: {e}")
        # Last resort fallback to default font
        return ImageFont.load_default()

# ─── WEBSOCKET CLIENT ─────────────────────────────────────────────────────────

def on_ws_message(ws, message):
    """Handle incoming WebSocket messages"""
    try:
        data = json.loads(message)
        state.update_from_message(data)
    except json.JSONDecodeError:
        logger.error("Received invalid JSON from server")
    except Exception as e:
        logger.error(f"Error processing WebSocket message: {e}")

def on_ws_error(ws, error):
    """Handle WebSocket errors"""
    logger.error(f"WebSocket error: {error}")

def on_ws_close(ws, close_status_code, close_msg):
    """Handle WebSocket connection close"""
    state.is_connected = False
    logger.warning(f"WebSocket connection closed: {close_msg} (code: {close_status_code})")

def on_ws_open(ws):
    """Handle WebSocket connection open"""
    state.is_connected = True
    logger.info("WebSocket connection established")

def start_websocket_client():
    """Start WebSocket client with automatic reconnection"""
    logger.info(f"Connecting to WebSocket server at {WS_URL}")
    reconnect_delay = 2  # Initial reconnect delay in seconds
    
    while state.running:
        try:
            # Create WebSocket with all callbacks
            ws = WebSocketApp(
                WS_URL,
                on_open=on_ws_open,
                on_message=on_ws_message,
                on_error=on_ws_error,
                on_close=on_ws_close
            )
            
            # Run until connection closes
            ws.run_forever()
            
            # If we get here, connection was closed
            if not state.running:
                break
                
            # Exponential backoff for reconnection attempts (cap at 30 seconds)
            reconnect_delay = min(reconnect_delay * 1.5, 30)
            logger.info(f"Reconnecting in {reconnect_delay:.1f} seconds...")
            time.sleep(reconnect_delay)
            
        except Exception as e:
            logger.error(f"WebSocket client error: {e}")
            time.sleep(reconnect_delay)

# ─── DISPLAY FUNCTIONS ─────────────────────────────────────────────────────────

def render_idle_clock(draw, width, height, font_big):
    """Render the large centered clock in idle mode"""
    time_str = datetime.now().strftime("%H:%M")
    bbox = draw.textbbox((0, 0), time_str, font=font_big)
    
    # Calculate text dimensions
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Center on screen
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    # Draw the clock
    draw.text((x, y), time_str, font=font_big, fill=0)

def render_typing_metrics(draw, width, height, fonts):
    """Render WPM, accuracy and small clock in typing mode"""
    # 1) Small clock in top-right corner
    time_str = datetime.now().strftime("%H:%M")
    clock_bbox = draw.textbbox((0, 0), time_str, font=fonts['clock_sm'])
    clock_width = clock_bbox[2] - clock_bbox[0]
    draw.text(
        (width - clock_width - 15, 5),  # Position in top-right with margin
        time_str,
        font=fonts['clock_sm'],
        fill=0
    )
    
    # 2) WPM display (centered with larger font)
    wpm_str = f"{int(state.freeze_wpm)} WPM"
    wpm_bbox = draw.textbbox((0, 0), wpm_str, font=fonts['big'])
    wpm_width = wpm_bbox[2] - wpm_bbox[0]
    wpm_height = wpm_bbox[3] - wpm_bbox[1]
    
    # Center WPM horizontally, position vertically for accuracy to follow
    wpm_x = (width - wpm_width) // 2
    wpm_y = (height - (wpm_height + SPACING + 20)) // 2  # Account for accuracy below
    
    draw.text((wpm_x, wpm_y), wpm_str, font=fonts['big'], fill=0)
    
    # 3) Accuracy display (smaller, below WPM)
    acc_str = f"{int(state.freeze_acc)}% ACC"
    acc_bbox = draw.textbbox((0, 0), acc_str, font=fonts['accuracy'])
    acc_width = acc_bbox[2] - acc_bbox[0]
    
    # Center accuracy horizontally, position below WPM
    acc_x = (width - acc_width) // 2
    acc_y = wpm_y + wpm_height + SPACING + 20  # Below WPM with extra spacing
    
    draw.text((acc_x, acc_y), acc_str, font=fonts['accuracy'], fill=0)

def render_connection_indicator(draw, width, height, is_connected):
    """Render a small connection status indicator"""
    if is_connected:
        # Small filled circle in bottom left
        draw.ellipse((5, height-10, 10, height-5), fill=0)
    else:
        # Small empty circle in bottom left
        draw.ellipse((5, height-10, 10, height-5), outline=0)

# ─── MAIN FUNCTION ───────────────────────────────────────────────────────────

def main():
    """Main application entry point"""
    try:
        logger.info("Starting ARKeys E-ink Display Client")
        
        # Initialize display
        epd, width, height = setup_display()
        
        # Load fonts
        fonts = {
            'big': load_font(FONT_BIG),
            'clock_sm': load_font(FONT_CLOCK_SM),
            'accuracy': load_font(FONT_ACC)
        }
        
        # Start WebSocket client in background thread
        ws_thread = threading.Thread(target=start_websocket_client, daemon=True)
        ws_thread.start()
        
        # Main display loop
        prev_mode_idle = None  # Track mode changes for full refresh
        
        while True:
            try:
                # Create a new image for this frame
                image = Image.new("1", (width, height), 255)  # 1-bit color, white background
                draw = ImageDraw.Draw(image)
                
                # Check if mode changed (for potential full refresh)
                current_mode_idle = state.is_idle
                mode_changed = prev_mode_idle is not None and prev_mode_idle != current_mode_idle
                prev_mode_idle = current_mode_idle
                
                # Choose display mode based on activity
                if state.is_idle:
                    render_idle_clock(draw, width, height, fonts['big'])
                else:
                    render_typing_metrics(draw, width, height, fonts)
                
                # Add connection indicator
                render_connection_indicator(draw, width, height, state.is_connected)
                
                # If mode switched, do full refresh occasionally to prevent ghosting
                if mode_changed and False:  # Disabled for now - enable if ghosting occurs
                    epd.init()
                    epd.display(epd.getbuffer(image))
                    epd.init_part()  # Switch back to partial mode after full refresh
                else:
                    # Normal partial update (faster, less flicker)
                    epd.displayPartial(epd.getbuffer(image))
                
                # Wait before next refresh
                time.sleep(REFRESH_RATE)
                
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f"Display update error: {e}")
                time.sleep(5)  # Wait longer after error
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        # Clean shutdown
        state.running = False
        
        # Clear display and put to sleep
        try:
            epd.init()
            epd.Clear(0xFF)
            epd.sleep()
            logger.info("Display cleared and put to sleep")
        except Exception as e:
            logger.error(f"Error during display shutdown: {e}")
            
        logger.info("Application terminated")

if __name__ == "__main__":
    main()