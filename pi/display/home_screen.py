#!/usr/bin/env python3
# Home screen renderer with efficient partial updates: static background + dynamic overlay using Tahoma font

import time
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V4

# Utility: ordinal suffix for dates
def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"

# Paths\ROOT   = os.path.expanduser('~/ARKeys')
ASSETS = os.path.join(ROOT, 'assets')
UI_BG  = os.path.join(ASSETS, 'static_ui.png')
TAHOMA = os.path.join(ASSETS, 'Tahoma.ttf')

# Initialize E-Ink
epd = epd2in13_V4.EPD()
epd.init()
epd.Clear(0xFF)
w, h = epd.height, epd.width  # 122×250

# Load and display static background once
base = Image.open(UI_BG).convert('1')
buf_base = epd.getbuffer(base)
epd.display(buf_base)
# Prepare for partial updates with static base
epd.displayPartBaseImage(buf_base)

# Load fonts (Tahoma preferred)
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
        # Create blank overlay for dynamic parts
        overlay = Image.new('1', (w, h), 255)
        draw = ImageDraw.Draw(overlay)

        # ----- HEADER: centered date -----
        now = datetime.now()
        date_str = now.strftime('%B ') + ordinal(now.day)
        bbox_d = draw.textbbox((0,0), date_str, font=font_header)
        x_date = (w - (bbox_d[2] - bbox_d[0])) // 2
        draw.text((x_date, 2), date_str, font=font_header, fill=0)
        # ----- HEADER: time top-right -----
        time_str = now.strftime('%H:%M')
        bbox_t = draw.textbbox((0,0), time_str, font=font_header)
        draw.text((w - bbox_t[2] - 5, 2), time_str, font=font_header, fill=0)

        # ----- FOOTER LEFT: Session Timer -----
        elapsed = int(time.time() - t0)
        hrs, rem = divmod(elapsed, 3600)
        mins, secs = divmod(rem, 60)
        sess_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        bbox_s = draw.textbbox((0,0), sess_str, font=font_footer)
        draw.text((5, h - bbox_s[3] - 2), sess_str, font=font_footer, fill=0)

        # ----- FOOTER RIGHT: Avg WPM Placeholder -----
        avg_wpm = 75  # TODO: replace with real API value
        avg_str = f"avg {avg_wpm}"
        bbox_a = draw.textbbox((0,0), avg_str, font=font_avg)
        draw.text((w - bbox_a[2] - 5, h - bbox_a[3] - 2), avg_str, font=font_avg, fill=0)

        # Partial refresh: update only dynamic overlay
        epd.displayPartial(epd.getbuffer(overlay))
        time.sleep(1)

except KeyboardInterrupt:
    epd.init()
    epd.Clear(0xFF)
    epd.sleep()
