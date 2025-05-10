#!/usr/bin/env python3
# Proof-of-concept UI test for ARKkeys on Waveshare 2.13" V4 E-Ink

import time
import random
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V4

# Initialize display
epd = epd2in13_V4.EPD()
epd.init()
epd.Clear(0xFF)
width, height = epd.height, epd.width  # width=122, height=250

# Load fonts (adjust paths if needed)
FONT_DIR = '/usr/share/fonts/truetype/dejavu'
font_header = ImageFont.truetype(f'{FONT_DIR}/DejaVuSans-Bold.ttf', 24)
font_wpm    = ImageFont.truetype(f'{FONT_DIR}/DejaVuSansMono.ttf', 40)
font_acc    = ImageFont.truetype(f'{FONT_DIR}/DejaVuSans.ttf', 20)
font_footer = font_acc

# Run a few iterations with random data
for _ in range(5):
    # Create fresh canvas
    image = Image.new('1', (width, height), 255)
    draw  = ImageDraw.Draw(image)

    # 1) Static header
    draw.text((5, 0), 'ARKkeys Tracker', font=font_header, fill=0)

    # 2) Boxes for metrics and history
    draw.rectangle((2, 30, width-2, 100), outline=0)   # WPM box
    draw.rectangle((2, 105, width-2, 135), outline=0)  # ACC box
    draw.rectangle((2, 140, width-2, 230), outline=0)  # History box

    # 3) Simulate dynamic data
    wpm = random.randint(30, 120)
    acc = random.uniform(90.0, 100.0)
    history = [random.randint(30, 120) for _ in range(width-6)]
    now = datetime.now().strftime('%H:%M:%S')
    status = 'OK'

    # 4) Draw WPM using textbbox instead of textsize
    wpm_str = f'{wpm:3d}'
    bbox = draw.textbbox((0, 0), wpm_str, font=font_wpm)
    text_width = bbox[2] - bbox[0]
    w_x = (width - text_width) // 2
    draw.text((w_x, 35), wpm_str, font=font_wpm, fill=0)

    # 5) Draw Accuracy using textbbox
    acc_str = f'{acc:.1f}%'
    bbox = draw.textbbox((0, 0), acc_str, font=font_acc)
    text_width = bbox[2] - bbox[0]
    a_x = (width - text_width) // 2
    draw.text((a_x, 108), acc_str, font=font_acc, fill=0)

    # 6) Draw Sparkline
    hx0, hy0 = 5, 143
    box_w = width - 10
    box_h = 230 - 143
    # Scale history to box_h
    for i, val in enumerate(history[:box_w]):
        y0 = hy0 + box_h
        y1 = hy0 + box_h - int((val/120) * box_h)
        draw.line((hx0 + i, y0, hx0 + i, y1), fill=0)

    # 7) Draw Footer (time/status) using textbbox
    footer_str = f'{now}  {status}'
    bbox = draw.textbbox((0, 0), footer_str, font=font_footer)
    text_width = bbox[2] - bbox[0]
    draw.text(((width - text_width) // 2, 235), footer_str, font=font_footer, fill=0)

    # 8) Display full image
    epd.display(epd.getbuffer(image))
    print(f"[*] Iteration: WPM={wpm}, ACC={acc:.1f}%, TIME={now}")
    time.sleep(2)

# Put display to sleep
epd.init()
epd.Clear(0xFF)
epd.sleep()
