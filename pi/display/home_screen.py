#!/usr/bin/env python3
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V4
import os

# Paths
ROOT     = os.path.expanduser('~/ARKeys')
ASSETS   = os.path.join(ROOT, 'assets')
STATICUI = os.path.join(ASSETS, 'static_ui.png')

# Initialize E-Ink
epd = epd2in13_V4.EPD()
epd.init(); epd.Clear(0xFF)
w, h = epd.height, epd.width

# Load static background
base = Image.open(STATICUI).convert('1')

# Fonts
FONTDIR = '/usr/share/fonts/truetype/dejavu'
font_h  = ImageFont.truetype(f'{FONTDIR}/DejaVuSans.ttf', 16)
font_f  = ImageFont.truetype(f'{FONTDIR}/DejaVuSans.ttf', 16)

# Track session start
start_ts = time.time()

try:
    while True:
        img  = base.copy()
        draw = ImageDraw.Draw(img)

        # Header date/time
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        bx, by = draw.textbbox((0,0), now, font=font_h)[2:]
        draw.text((w - bx - 2, 2), now, font=font_h, fill=0)

        # Footer session timer
        secs = int(time.time() - start_ts)
        hh, rr = divmod(secs, 3600)
        mm, ss = divmod(rr, 60)
        footer = f'Session {hh:02d}:{mm:02d}:{ss:02d}'
        fx, fy = 5, h - draw.textbbox((0,0), footer, font=font_f)[3] - 2
        draw.text((fx, fy), footer, font=font_f, fill=0)

        # TODO: overlay WPM/ACC by pasting segments or drawing text

        epd.display(epd.getbuffer(img))
        time.sleep(1)

except KeyboardInterrupt:
    epd.init(); epd.Clear(0xFF); epd.sleep()
