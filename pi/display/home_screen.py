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
API_URL = "http://localhost:8000"  # Your Bottle API
UPDATE_INTERVAL = 10  # Update every 10 seconds

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

# Initialize partial update mode
epd.init_fast()

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

# Define update regions (x, y, width, height)
REGIONS = {
    'date': {'bounds': None, 'last_text': ''},
    'time': {'bounds': None, 'last_text': ''},
    'session': {'bounds': None, 'last_text': ''},
    'wpm': {'bounds': None, 'last_text': ''}
}

def get_avg_wpm():
    """Fetch average WPM from API"""
    try:
        response = requests.get(f"{API_URL}/metrics/stats", timeout=2)
        if response.status_code == 200:
            return int(response.json().get('avg_wpm', 0))
    except:
        pass
    return 0

def calculate_text_bounds(draw, text, font, x, y):
    """Calculate the bounding box for text"""
    bbox = draw.textbbox((x, y), text, font=font)
    # Add padding for clean updates
    return (bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2)

def update_region(region_name, text, x, y, font, draw):
    """Update a specific region if text has changed"""
    global REGIONS
    
    if REGIONS[region_name]['last_text'] != text:
        # Calculate bounds for this text
        bounds = calculate_text_bounds(draw, text, font, x, y)
        
        # If we have previous bounds, clear that area first
        if REGIONS[region_name]['bounds']:
            old_bounds = REGIONS[region_name]['bounds']
            # Create a clean image for the old region (from base)
            old_x, old_y, old_x2, old_y2 = old_bounds
            clean_region = base.crop((old_x, old_y, old_x2, old_y2))
            # Display the clean region
            epd.display_Partial_Wait(epd.getbuffer(clean_region), old_x, old_y, old_x2 - old_x, old_y2 - old_y)
        
        # Create image for the new text
        new_x, new_y, new_x2, new_y2 = bounds
        text_img = Image.new('1', (new_x2 - new_x, new_y2 - new_y), 255)
        text_draw = ImageDraw.Draw(text_img)
        text_draw.text((x - new_x, y - new_y), text, font=font, fill=0)
        
        # Update the display
        epd.display_Partial_Wait(epd.getbuffer(text_img), new_x, new_y, new_x2 - new_x, new_y2 - new_y)
        
        # Store the new bounds and text
        REGIONS[region_name]['bounds'] = bounds
        REGIONS[region_name]['last_text'] = text
        
        return True
    return False

try:
    # Do an initial full update to establish all elements
    img = base.copy()
    draw = ImageDraw.Draw(img)
    
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
        avg_wpm = get_avg_wpm()
        avg_str = f"avg {avg_wpm}"
        
        # Calculate positions
        # Date (centered)
        bbox_d = draw.textbbox((0,0), date_str, font=font_header)
        x_d = (w - (bbox_d[2] - bbox_d[0])) // 2
        
        # Time (right-aligned)
        bbox_t = draw.textbbox((0,0), time_str, font=font_header)
        x_t = w - bbox_t[2] - 5
        
        # Session timer (left)
        x_s = 5
        y_s = h - 20
        
        # WPM (right)
        bbox_a = draw.textbbox((0,0), avg_str, font=font_avg)
        x_a = w - bbox_a[2] - 5
        y_a = h - bbox_a[3] - 2
        
        # Update only changed regions
        update_region('date', date_str, x_d, 2, font_header, draw)
        update_region('time', time_str, x_t, 2, font_header, draw)
        update_region('session', sess_str, x_s, y_s, font_footer, draw)
        
        # Only update WPM if it changed by 5+
        if abs(avg_wpm - last_wpm) >= 5:
            update_region('wpm', avg_str, x_a, y_a, font_avg, draw)
            last_wpm = avg_wpm
        
        time.sleep(UPDATE_INTERVAL)

except KeyboardInterrupt:
    # Clean exit
    epd.init()
    epd.Clear(0xFF)
    epd.sleep()