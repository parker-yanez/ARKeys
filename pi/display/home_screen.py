#!/usr/bin/env python3
# Home screen renderer with partial updates: centered date/time header, session timer + avg WPM footer

import time
import random
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V4
import os

# Utility: ordinal suffix
def ordinal(n):
    return f"{n}{'th' if 11<=n%100<=13 else {1:'st',2:'nd',3:'rd'}.get(n%10,'th')}"

# Paths & Initialization
ROOT   = os.path.expanduser('~/ARKeys')
ASSETS = os.path.join(ROOT, 'assets')
UI_BG  = os.path.join(ASSETS, 'static_ui.png')

# Initialize display
epd = epd2in13_V4.EPD()
epd.init()
epd.Clear(0xFF)
w, h = epd.height, epd.width  # 122×250

# Load static background and set as partial-update base
base = Image.open(UI_BG).convert('1')
epd.display(epd.getbuffer(base))
epd.init(epd.PART_UPDATE)
epd.displayPartBaseImage(epd.getbuffer(base))

# Fonts
FONT_DIR = '/usr/share/fonts/truetype/dejavu'
font_header = ImageFont.truetype(f'{FONT_DIR}/DejaVuSans.ttf', 16)
font_footer = ImageFont.truetype(f'{FONT_DIR}/DejaVuSans.ttf', 16)
font_avg    = ImageFont.truetype(f'{FONT_DIR}/DejaVuSansMono-Bold.ttf', 20)

# Track session start
t0 = time.time()

try:
    while True:
        # Dynamic layer
        dyn = Image.new('1', (w, h), 255)
        draw = ImageDraw.Draw(dyn)

        # Header: centered "Month DayOrdinal HH:MM"
        now = datetime.now()
        date_str = now.strftime('%B ') + ordinal(now.day)
        time_str = now.strftime('%H:%M')
        header = f"{date_str} {time_str}"
        bbox = draw.textbbox((0,0), header, font=font_header)
        x = (w - (bbox[2] - bbox[0])) // 2
        draw.text((x, 2), header, font=font_header, fill=0)

        # Footer left: session elapsed time
        elapsed = int(time.time() - t0)
        hrs, rem = divmod(elapsed, 3600)
        mins, secs = divmod(rem, 60)
        session_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        bbox2 = draw.textbbox((0,0), session_str, font=font_footer)
        draw.text((5, h - bbox2[3] - 2), session_str, font=font_footer, fill=0)

        # Footer right: avg WPM placeholder
        avg_wpm = 75  # replace with API value
        avg_str = f"avg {avg_wpm}"
        bbox3 = draw.textbbox((0,0), avg_str, font=font_avg)
        draw.text((w - bbox3[2] - 5, h - bbox3[3] - 2), avg_str, font=font_avg, fill=0)

        # Partial update only dynamic regions
        epd.displayPartial(epd.getbuffer(dyn))
        time.sleep(1)

except KeyboardInterrupt:
    epd.init()
    epd.Clear(0xFF)
    epd.sleep()
