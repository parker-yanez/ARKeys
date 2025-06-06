#!/usr/bin/env python3
"""
ARKeys E-ink Display Client

This script connects to the ARKeys WebSocket server and displays real-time typing
metrics on a 2.13" Waveshare e-ink display. It shows either a clock (idle mode) or
typing metrics (active mode) with efficient partial refresh updates.

Features:
- Dynamic mode switching (idle/typing) based on server signals
- Ghost-busting full refresh when needed
- Efficient partial updates during continuous use
- Connection monitoring and recovery
- Stable WPM display when transitioning to idle
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
WS_URL = "ws://192.168.1.225:8765"     # WebSocket server address
IDLE_REFRESH = 600                      # Full refresh every 10 minutes in idle mode
CONNECTION_TIMEOUT = 10.0               # Seconds without message before assuming disconnect
REFRESH_RATE = 1.0                      # Display update interval in seconds

# Asset Paths - Simplified
STATIC_UI = "static_ui.png"            # Static background image in working directory
TAHOMA_TTF = "/usr/share/fonts/truetype/msttcorefonts/Tahoma.ttf"  # System font path
FALLBACK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"  # Fallback font

# Font Sizes
FONT_CLOCK_BIG = 48     # Size for idle clock
FONT_CLOCK_SM = 12      # Size for typing-mode clock
FONT_WPM = 40           # Size for WPM display
FONT_ACC = 18           # Size for accuracy display
FONT_PEAK = 10          # Size for peak WPM display
SPACING = 5             # Gap between elements

# Configure logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/display_client.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("display_client")

# ─── APPLICATION STATE ─────────────────────────────────────────────────────────

class DisplayState:
    """Manages the application state and metrics data"""
    def __init__(self):
        # Runtime state
        self.mode = "idle"                   # Current display mode
        self.last_mode = None                # Previous mode to detect transitions
        self.do_full_flash = False           # Whether next update needs full refresh
        self.update_count = 0                # Count updates for periodic refresh
        
        # Metrics from server
        self.metrics = {
            "wpm": 0.0,
            "accuracy": 100.0,
            "active_time": 0.0,
            "total_words": 0,
            "correct_words": 0,
            "peak_wpm": 0.0,
            "refresh": False
        }
        
        # Last known good values (to prevent decay)
        self.last_active_wpm = 0.0
        
        # Connection state
        self.is_connected = False
        self.last_msg_ts = 0.0
        self.running = True
    
    def update_from_message(self, data):
        """Update state based on incoming WebSocket message with stable WPM handling"""
        # Track previous mode for transition detection
        self.last_mode = self.mode
        
        # Get the new mode from server
        new_mode = data.get("mode", "idle")
        
        # Update metrics with WPM stability
        if new_mode == "typing":
            # In typing mode, update WPM if it's a meaningful value
            current_wpm = data.get("wpm", 0.0)
            if current_wpm > 0:
                self.metrics["wpm"] = current_wpm
                # Keep track of last active WPM for idle mode
                self.last_active_wpm = current_wpm
        elif new_mode == "idle" and self.mode == "typing":
            # Just switched to idle mode - display last active WPM
            self.metrics["wpm"] = self.last_active_wpm
        
        # Always update the rest of the metrics
        self.metrics["accuracy"] = data.get("accuracy", self.metrics.get("accuracy", 100.0))
        self.metrics["total_words"] = data.get("total_words", self.metrics.get("total_words", 0))
        self.metrics["correct_words"] = data.get("correct_words", self.metrics.get("correct_words", 0))
        self.metrics["peak_wpm"] = data.get("peak_wpm", self.metrics.get("peak_wpm", 0.0))
        self.metrics["active_time"] = data.get("active_time", self.metrics.get("active_time", 0.0))
        
        # Update mode and timestamps
        self.mode = new_mode
        self.last_msg_ts = time.time()
        
        # Check for mode transition
        if self.mode != self.last_mode:
            logger.info(f"Mode transition: {self.last_mode} -> {self.mode}")
            self.do_full_flash = True
        
        # Check for refresh flag from server
        if data.get("refresh", False):
            logger.info("Server requested refresh")
            self.do_full_flash = True
    
    @property
    def is_stale(self):
        """Check if connection appears to be stale"""
        return time.time() - self.last_msg_ts > CONNECTION_TIMEOUT
    
    def need_periodic_refresh(self):
        """Check if we need a periodic full refresh to prevent ghosting"""
        # Increment update counter
        self.update_count += 1
        
        # Check if we've reached the threshold
        if self.mode == "idle" and self.update_count >= IDLE_REFRESH:
            logger.info("Performing periodic ghost-busting refresh")
            self.update_count = 0
            return True
        
        return False

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
        
        # Load the static background image
        if os.path.exists(STATIC_UI):
            base = Image.open(STATIC_UI).convert('1')
            logger.info(f"Loaded static UI from {STATIC_UI}")
        else:
            # Create blank background if image not found
            logger.warning(f"Static UI image not found at {STATIC_UI}, using blank background")
            base = Image.new('1', (epd.height, epd.width), 255)
        
        # Initial display of background and set as base for partial updates
        epd.display(epd.getbuffer(base))
        epd.displayPartBaseImage(epd.getbuffer(base))
        
        return epd, base, epd.height, epd.width
    except Exception as e:
        logger.error(f"Display initialization failed: {e}")
        raise

# ─── FONT LOADING ─────────────────────────────────────────────────────────────

def load_fonts():
    """Load all required fonts with fallbacks"""
    fonts = {}
    try:
        # Try Tahoma first, then fallback
        font_path = None
        if os.path.exists(TAHOMA_TTF):
            font_path = TAHOMA_TTF
        elif os.path.exists(FALLBACK_FONT):
            font_path = FALLBACK_FONT
        else:
            # If neither font exists, log warning and use default
            logger.warning("Neither Tahoma nor fallback font found, using default")
            return {
                'clock_big': ImageFont.load_default(),
                'clock_sm': ImageFont.load_default(),
                'wpm': ImageFont.load_default(),
                'accuracy': ImageFont.load_default(),
                'peak': ImageFont.load_default()
            }
        
        # Load each font size
        fonts['clock_big'] = ImageFont.truetype(font_path, FONT_CLOCK_BIG)
        fonts['clock_sm'] = ImageFont.truetype(font_path, FONT_CLOCK_SM)
        fonts['wpm'] = ImageFont.truetype(font_path, FONT_WPM)
        fonts['accuracy'] = ImageFont.truetype(font_path, FONT_ACC)
        fonts['peak'] = ImageFont.truetype(font_path, FONT_PEAK)
        
        logger.info(f"Fonts loaded from {font_path}")
        return fonts
    except Exception as e:
        logger.error(f"Font loading error: {e}")
        # Return dictionary with default fonts as fallback
        return {
            'clock_big': ImageFont.load_default(),
            'clock_sm': ImageFont.load_default(),
            'wpm': ImageFont.load_default(),
            'accuracy': ImageFont.load_default(),
            'peak': ImageFont.load_default()
        }

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
    state.is_connected = False

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

# ─── DISPLAY RENDERING ─────────────────────────────────────────────────────────

def render_idle_mode(draw, width, height, fonts):
    """Render the idle mode display with large centered clock"""
    # Ensure we're using the exact screen dimensions
    SCREEN_HEIGHT = 122  # Fixed height for explicit centering
    
    time_str = datetime.now().strftime("%H:%M")
    
    # Get the exact bounding box for the text
    bbox = draw.textbbox((0, 0), time_str, font=fonts['clock_big'])
    
    # Calculate text dimensions
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Calculate position for perfect centering
    x = (width - text_width) // 2
    
    # Explicitly center in the 122 pixel height
    y = (SCREEN_HEIGHT - text_height) // 2
    
    # Lift the clock up by 20 pixels
    y_adjustment = -12  # -2 from before, plus -20 to lift it up
    
    # Draw the clock exactly centered horizontally, but 20px higher
    draw.text((x, y + y_adjustment), time_str, font=fonts['clock_big'], fill=0)



def render_typing_mode(draw, width, height, fonts, metrics):
    """Render the typing mode layout with improved positioning"""
    # 1) Small clock in top-center 
    time_str = datetime.now().strftime("%H:%M")
    clock_bbox = draw.textbbox((0, 0), time_str, font=fonts['clock_sm'])
    clock_width = clock_bbox[2] - clock_bbox[0]
    
    # Position: top-center
    clock_x = (width - clock_width) // 2
    draw.text(
        (clock_x, 8),  # Centered horizontally, 8px from top
        time_str,
        font=fonts['clock_sm'],
        fill=0
    )
    
    # 2) WPM display (large, centered more toward middle)
    wpm_str = f"{int(metrics['wpm'])} WPM"
    wpm_bbox = draw.textbbox((0, 0), wpm_str, font=fonts['wpm'])
    wpm_width = wpm_bbox[2] - wpm_bbox[0]
    wpm_height = wpm_bbox[3] - wpm_bbox[1]
    
    # Center horizontally, place vertically at 40% of screen height
    wpm_x = (width - wpm_width) // 2
    wpm_y = int(height * 0.4) - (wpm_height // 2)  # 40% down the screen
    
    draw.text((wpm_x, wpm_y), wpm_str, font=fonts['wpm'], fill=0)
    
    # 3) Accuracy display (below WPM, closer to it)
    acc_str = f"{int(metrics['accuracy'])}% ACC"
    acc_bbox = draw.textbbox((0, 0), acc_str, font=fonts['accuracy'])
    acc_width = acc_bbox[2] - acc_bbox[0]
    
    # Center horizontally, position 15px below WPM (closer than before)
    acc_x = (width - acc_width) // 2
    acc_y = wpm_y + wpm_height + 15  # Reduced from 20px to 15px
    
    draw.text((acc_x, acc_y), acc_str, font=fonts['accuracy'], fill=0)
    
    # 4) Peak WPM (bottom-left corner, more readable)
    peak_str = f"Peak: {int(metrics['peak_wpm'])}"  # Shorter text
    draw.text((5, height - 15), peak_str, font=fonts['peak'], fill=0)
    
    # 5) Word count (bottom right before connection indicator)
    word_count_str = f"{metrics['total_words']}w"
    word_count_bbox = draw.textbbox((0, 0), word_count_str, font=fonts['peak'])
    word_count_width = word_count_bbox[2] - word_count_bbox[0]
    draw.text((width - word_count_width - 20, height - 15), word_count_str, font=fonts['peak'], fill=0)

def render_connection_indicator(draw, width, height, is_connected):
    """Render a small connection status indicator (bottom right)"""
    if is_connected:
        # Small filled circle in bottom right
        draw.ellipse((width-15, height-15, width-5, height-5), fill=0)
    else:
        # Small empty circle in bottom right
        draw.ellipse((width-15, height-15, width-5, height-5), outline=0)

# ─── MAIN FUNCTION ───────────────────────────────────────────────────────────

def main():
    """Main application entry point"""
    try:
        logger.info("Starting ARKeys E-ink Display Client")
        
        # Initialize display
        epd, base_image, width, height = setup_display()
        
        # Load fonts
        fonts = load_fonts()
        
        # Start WebSocket client in background thread
        ws_thread = threading.Thread(target=start_websocket_client, daemon=True)
        ws_thread.start()
        
        # Main display loop
        while state.running:
            try:
                # Check connection state, force idle mode if disconnected
                if not state.is_connected or state.is_stale:
                    if state.mode != "idle":
                        logger.warning("Connection lost or stale, switching to idle mode")
                        state.mode = "idle"
                        state.do_full_flash = True
                
                # Check if we need a periodic refresh
                if state.need_periodic_refresh():
                    state.do_full_flash = True
                
                # Handle full refresh if needed
                if state.do_full_flash:
                    logger.info("Performing full refresh")
                    
                    # Full refresh sequence
                    epd.init()  # Switch to full refresh waveform
                    epd.display(epd.getbuffer(base_image))  # Redraw static background
                    epd.displayPartBaseImage(epd.getbuffer(base_image))  # Set up for partials
                    
                    # Reset flag
                    state.do_full_flash = False
                    
                    # Short delay after full refresh
                    time.sleep(0.5)
                
                # Create overlay for dynamic elements
                overlay = Image.new('1', (width, height), 255)  # White background
                draw = ImageDraw.Draw(overlay)
                
                # Render appropriate mode
                if state.mode == "idle":
                    render_idle_mode(draw, width, height, fonts)
                else:  # "typing" mode
                    render_typing_mode(draw, width, height, fonts, state.metrics)
                
                # Add connection indicator
                render_connection_indicator(draw, width, height, state.is_connected)
                
                # Display with partial update
                epd.displayPartial(epd.getbuffer(overlay))
                
                # Wait before next update
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