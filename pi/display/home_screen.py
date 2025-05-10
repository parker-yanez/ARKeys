#!/usr/bin/env python3
# Home screen renderer: overlay dynamic elements on static background

import time
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V4

# Utility: ordinal suffix for dates
def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"

# Paths
ROOT     = os.path.expanduser('~/ARKeys')
ASSETS   = os.path.join(ROOT, 'assets')
STATICUI = os.path.join(ASSETS, 'static_ui.png')
TAHOMA   = os.path.join(ASSETS, 'Tahoma.ttf')

# Initialize E-Ink display
epd = epd2in13_V4.EPD()
epd.init()
epd.Clear(0xFF)
w, h = epd.height, epd.width  # 122×250

# Load static background once
base = Image.open(STATICUI).convert('1')
# Display static background full refresh
epd.display(epd.getbuffer(base))

# Load fonts, prefer Tahoma
ttf = TAHOMA if os.path.exists(TAHOMA) else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font_header = ImageFont.truetype(ttf, 16)
font_footer = ImageFont.truetype(ttf, 16)
font_avg    = ImageFont.truetype(ttf, 20)

# Track session start
t0 = time.time()

try:
    while True:
        # Composite a new image from the static background
        img = base.copy()
        draw = ImageDraw.Draw(img)

        # ----- HEADER: centered date -----
        now = datetime.now()
        date_str = now.strftime('%B ') + ordinal(now.day)
        bbox_d = draw.textbbox((0,0), date_str, font=font_header)
        x_d = (w - (bbox_d[2] - bbox_d[0])) // 2
        draw.text((x_d, 2), date_str, font=font_header, fill=0)
        # ----- HEADER: time right-aligned -----
        time_str = now.strftime('%H:%M')
        bbox_t = draw.textbbox((0,0), time_str, font=font_header)
        draw.text((w - bbox_t[2] - 5, 2), time_str, font=font_header, fill=0)

        # ----- FOOTER: session timer left -----
        elapsed = int(time.time() - t0)
        hrs, rem = divmod(elapsed, 3600)
        mins, secs = divmod(rem, 60)
        sess_str = f"{hrs:02d}:{mins:02d}:{secs:02d}"
        bbox_s = draw.textbbox((0,0), sess_str, font=font_footer)
        draw.text((5, h - bbox_s[3] - 2), sess_str, font=font_footer, fill=0)

        # ----- FOOTER: avg WPM right -----
        avg_wpm = 75  # Placeholder for real API
        avg_str = f"avg {avg_wpm}"
        bbox_a = draw.textbbox((0,0), avg_str, font=font_avg)
        draw.text((w - bbox_a[2] - 5, h - bbox_a[3] - 2), avg_str, font=font_avg, fill=0)

        # Full refresh with overlay
        epd.display(epd.getbuffer(img))
        time.sleep(1)

except KeyboardInterrupt:
    epd.init()
    epd.Clear(0xFF)
    epd.sleep()
