#!/usr/bin/env python3
"""
Pi-side home screen: fetch live WPM & accuracy from host API and render on e-ink.
Uses static background + partial overlay for efficient updates.
"""
import time
import os
import json
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V4

# --- Configuration ---
# Host metrics endpoint (adjust to your Mac's IP)
HOST_IP    = '192.168.1.225'    # <-- replace with your host LAN IP
HOST_PORT  = 8000
METRICS_URL = f'http://{HOST_IP}:{HOST_PORT}/metrics'

# Paths
ROOT     = os.path.expanduser('~/ARKeys')
ASSETS   = os.path.join(ROOT, 'assets')
STATICUI = os.path.join(ASSETS, 'static_ui.png')
TAHOMA   = os.path.join(ASSETS, 'Tahoma.ttf')

# Initialize e-ink display
epd = epd2in13_V4.EPD()
epd.init()
epd.Clear(0xFF)
w, h = epd.height, epd.width  # typically 122×250

# Load and display static background once
base_img = Image.open(STATICUI).convert('1')
buf_base = epd.getbuffer(base_img)
epd.display(buf_base)
# Prepare for partial updates using this base
epd.displayPartBaseImage(buf_base)

# Load fonts
def load_font(path, size):
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    else:
        fd = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        return ImageFont.truetype(fd, size)

font_header = load_font(TAHOMA, 16)
font_footer = load_font(TAHOMA, 16)
font_avg    = load_font(TAHOMA, 20)

# Utility: ordinal suffix
def ordinal(n):
    return f"{n}{'th' if 11<=n%100<=13 else {1:'st',2:'nd',3:'rd'}.get(n%10,'th')}"

# Session timer state
t0 = time.time()

try:
    last_wpm = 0.0
    last_acc = 100.0
    while True:
        # 1) Fetch metrics
        try:
            r = requests.get(METRICS_URL, timeout=0.3)
            data = r.json()
            last_wpm = data.get('wpm', last_wpm)
            last_acc = data.get('accuracy', last_acc)
        except Exception:
            # keep last known values on failure
            pass

        # 2) Create overlay image for dynamic parts
        dyn = Image.new('1', (w, h), 255)
        draw = ImageDraw.Draw(dyn)

        # HEADER: date centered
        now = datetime.now()
        date_str = now.strftime('%B ') + ordinal(now.day)
        bbox = draw.textbbox((0,0), date_str, font=font_header)
        x = (w - (bbox[2]-bbox[0])) // 2
        draw.text((x, 2), date_str, font=font_header, fill=0)
        # HEADER: time top-right
        time_str = now.strftime('%H:%M')
        tb = draw.textbbox((0,0), time_str, font=font_header)
        draw.text((w - tb[2] - 5, 2), time_str, font=font_header, fill=0)

        # FOOTER LEFT: session timer
        elapsed = int(time.time() - t0)
        hrs, rem = divmod(elapsed, 3600)
        mins, secs = divmod(rem, 60)
        session_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        sb = draw.textbbox((0,0), session_str, font=font_footer)
        draw.text((5, h - sb[3] - 2), session_str, font=font_footer, fill=0)

        # FOOTER RIGHT: WPM
        wpm_str = f"{last_wpm:.1f} WPM"
        wb = draw.textbbox((0,0), wpm_str, font=font_avg)
        draw.text((w - wb[2] - 5, h - wb[3] - 2), wpm_str, font=font_avg, fill=0)
        # Above it: Accuracy
        acc_str = f"{last_acc:.1f}% ACC"
        ab = draw.textbbox((0,0), acc_str, font=font_footer)
        draw.text((w - ab[2] - 5, h - wb[3] - ab[3] - 4), acc_str, font=font_footer, fill=0)

        # 3) Partial update
        epd.displayPartial(epd.getbuffer(dyn))
        time.sleep(1)

except KeyboardInterrupt:
    epd.init()
    epd.Clear(0xFF)
    epd.sleep()
