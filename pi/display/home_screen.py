#!/usr/bin/env python3
import time
import os
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V4

def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"

# Configuration
API_URL = "http://192.168.1.225:8000"  # Your Bottle API
UPDATE_INTERVAL = 5  # Update every 5 seconds

# Paths
ROOT = os.path.expanduser('~/ARKeys')
ASSETS = os.path.join(ROOT, 'assets')
STATICUI = os.path.join(ASSETS, 'static_ui.png')
TAHOMA = os.path.join(ASSETS, 'Tahoma.ttf')

# Initialize E-Ink display
epd = epd2in13_V4.EPD()
epd.init()
epd.Clear(0xFF)
w, h = epd.height, epd.width  # 122×250

# Load static background once
base = Image.open(STATICUI).convert('1')

# Display static background with full refresh
epd.display(epd.getbuffer(base))

# Set the base image for partial updates
epd.displayPartBaseImage(epd.getbuffer(base))

# Load fonts
ttf = TAHOMA if os.path.exists(TAHOMA) else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font_header = ImageFont.truetype(ttf, 16)
font_footer = ImageFont.truetype(ttf, 16)
font_avg = ImageFont.truetype(ttf, 20)

# Track session start and previous values
t0 = time.time()
last_time = ""
last_date = ""
last_session = ""
last_wpm = 0

def get_metrics():
    """Fetch metrics from API"""
    try:
        response = requests.get(f"{API_URL}/metrics", timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"API error: {e}")
    return {"wpm": 0, "accuracy": 100, "total_words": 0}

def needs_update(current_time, current_date, current_session, current_wpm):
    """Check if any value has changed significantly"""
    global last_time, last_date, last_session, last_wpm
    
    if (current_time != last_time or 
        current_date != last_date or 
        current_session != last_session or 
        abs(current_wpm - last_wpm) >= 3):  # Only update WPM if change >= 3
        return True
    return False

try:
    # Main loop
    while True:
        # Get current values
        now = datetime.now()
        date_str = now.strftime('%B ') + ordinal(now.day)
        time_str = now.strftime('%H:%M')
        
        # Calculate session time
        elapsed = int(time.time() - t0)
        hrs, rem = divmod(elapsed, 3600)
        mins = rem // 60  # Only update minutes, not seconds for less flicker
        sess_str = f"{hrs:02d}:{mins:02d}"
        
        # Get WPM from API
        metrics = get_metrics()
        wpm = int(metrics.get('wpm', 0))
        accuracy = int(metrics.get('accuracy', 100))
        
        # Only update display if something changed
        if needs_update(time_str, date_str, sess_str, wpm):
            # Create transparent overlay image (all white)
            overlay = Image.new('1', (w, h), 255)
            draw = ImageDraw.Draw(overlay)
            
            # Draw date (centered)
            bbox_d = draw.textbbox((0,0), date_str, font=font_header)
            x_d = (w - (bbox_d[2] - bbox_d[0])) // 2
            draw.text((x_d, 2), date_str, font=font_header, fill=0)
            
            # Draw time (right-aligned)
            bbox_t = draw.textbbox((0,0), time_str, font=font_header)
            draw.text((w - bbox_t[2] - 5, 2), time_str, font=font_header, fill=0)
            
            # Draw session timer (left)
            bbox_s = draw.textbbox((0,0), sess_str, font=font_footer)
            draw.text((5, h - bbox_s[3] - 2), sess_str, font=font_footer, fill=0)
            
            # Draw avg WPM (right)
            wpm_str = f"avg {wpm}"
            bbox_a = draw.textbbox((0,0), wpm_str, font=font_avg)
            draw.text((w - bbox_a[2] - 5, h - bbox_a[3] - 2), wpm_str, font=font_avg, fill=0)
            
            # Draw accuracy (center bottom)
            if accuracy > 0:
                acc_str = f"{accuracy}%"
                bbox_acc = draw.textbbox((0,0), acc_str, font=font_footer)
                x_acc = (w - (bbox_acc[2] - bbox_acc[0])) // 2
                draw.text((x_acc, h - bbox_acc[3] - 2), acc_str, font=font_footer, fill=0)
            
            # Update the display with partial refresh
            # This will ONLY update the pixels that differ from the base image
            epd.displayPartial(epd.getbuffer(overlay))
            
            # Update last values
            last_time = time_str
            last_date = date_str
            last_session = sess_str
            last_wpm = wpm
            
            # Occasionally do a full refresh to clear ghosting
            # Every 10 minutes (600 seconds)
            if elapsed % 600 < UPDATE_INTERVAL:
                print("Performing full refresh to clear ghosting")
                epd.init()
                epd.display(epd.getbuffer(base))
                epd.displayPartBaseImage(epd.getbuffer(base))
        
        time.sleep(UPDATE_INTERVAL)

except KeyboardInterrupt:
    # Clean exit
    epd.init()
    epd.Clear(0xFF)
    epd.sleep()