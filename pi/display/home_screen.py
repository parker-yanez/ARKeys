#!/usr/bin/env python3
# Home screen renderer with partial updates: static background + dynamic overlay using Tahoma font

import time
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V4

# Utility: ordinal suffix for dates
def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"

# Paths
ROOT   = os.path.expanduser('~/ARKeys')
ASSETS = os.path.join(ROOT, 'assets')
UI_BG  = os.path.join(ASSETS, 'static_ui.png')
TAHOMA = os.path.join(ASSETS, 'Tahoma.ttf')

# Initialize e-ink display
epd = epd2in13_V4.EPD()
epd.init()
epd.Clear(0xFF)
w, h = epd.height, epd.width  # 122×250

# Load static background
base = Image.open(UI_BG).convert('1')
# Display static UI once
epd.display(epd.getbuffer(base))
# Prepare for partial updates
epd.displayPartBaseImage(epd.getbuffer(base))

# Load fonts (Tahoma preferred, fallback to DejaVu)
if os.path.exists(TAHOMA):
    font_header = ImageFont.truetype(TAHOMA, 16)
    font_footer = ImageFont.truetype(TAHOMA, 16)
    font_avg    = ImageFont.truetype(TAHOMA, 20)
else:
    FONT_DIR = '/usr/share/fonts/truetype/dejavu'
    font_header = ImageFont.truetype(f'{FONT_DIR}/DejaVuSans.ttf', 16)
    font_footer = ImageFont.truetype(f'{FONT_DIR}/DejaVuSans.ttf', 16)
    font_avg    = ImageFont.truetype(f'{FONT_DIR}/DejaVuSansMono-Bold.ttf', 20)

# Track session start
t0 = time.time()

try:
    while True:
        # Create dynamic overlay image
        dyn = Image.new('1', (w, h), 255)
        draw = ImageDraw.Draw(dyn)

        # ----- HEADER: date (left) and time (right) -----
        now = datetime.now()
        date_str = now.strftime('%B ') + ordinal(now.day)
        time_str = now.strftime('%H:%M')
        # draw date
        draw.text((5, 2), date_str, font=font_header, fill=0)
        # draw time
        bbox_t = draw.textbbox((0, 0), time_str, font=font_header)
        draw.text((w - bbox_t[2] - 5, 2), time_str, font=font_header, fill=0)

        # ----- FOOTER LEFT: Session Timer -----
        elapsed = int(time.time() - t0)
        hrs, rem = divmod(elapsed, 3600)
        mins, secs = divmod(rem, 60)
        session_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        bbox_s = draw.textbbox((0, 0), session_str, font=font_footer)
        draw.text((5, h - bbox_s[3] - 2), session_str, font=font_footer, fill=0)

        # ----- FOOTER RIGHT: Avg WPM Placeholder -----
        avg_wpm = 75  # TODO: replace with real API value
        avg_str = f"avg {avg_wpm}"
        bbox_a = draw.textbbox((0, 0), avg_str, font=font_avg)
        draw.text((w - bbox_a[2] - 5, h - bbox_a[3] - 2), avg_str, font=font_avg, fill=0)

        # Partial update only dynamic overlay
        epd.displayPartial(epd.getbuffer(dyn))
        time.sleep(1)

except KeyboardInterrupt:
    # Cleanup on exit
    epd.init()
    epd.Clear(0xFF)
    epd.sleep()
