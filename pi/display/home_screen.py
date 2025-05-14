#!/usr/bin/env python3
import time
import threading
import json
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V4
from websocket import WebSocketApp

# ─── CONFIG ───────────────────────────────────────────────────────────────────

# how long to wait after last word before going back to Idle mode
IDLE_THRESHOLD = 10.0

# your host WebSocket URL
WS_URL = "ws://192.168.1.225:8765"

# display dimensions (will be flipped by the driver)
epd = epd2in13_V4.EPD()
epd.init()
epd.Clear(0xFF)
W, H = epd.height, epd.width  # note: height and width are swapped in the driver

# font sizes
FONT_BIG   = 48  # idle‐mode clock + typing WPM
FONT_SMALL = 12  # typing‐mode clock + ACC

# pixel spacing between WPM and ACC
SPACING = 5

# optional Tahoma fallback
ASSETS     = os.path.expanduser('~/ARKeys/assets')
TAHOMA_TTF = os.path.join(ASSETS, 'Tahoma.ttf')

# ─── GLOBAL METRICS STATE ─────────────────────────────────────────────────────

metrics_data     = {"wpm": 0.0, "accuracy": 100.0, "total_words": 0}
freeze_wpm       = 0.0
freeze_acc       = 100.0
last_total_words = 0
last_word_ts     = 0.0

# ─── WEBSOCKET CALLBACK ───────────────────────────────────────────────────────

def on_ws_message(ws, message):
    global metrics_data, freeze_wpm, freeze_acc, last_total_words, last_word_ts

    data = json.loads(message)
    metrics_data = data

    new_tw = data.get("total_words", 0)
    # whenever total_words increases, freeze the new WPM & ACC
    if new_tw > last_total_words:
        freeze_wpm       = data.get("wpm", 0.0)
        freeze_acc       = data.get("accuracy", 100.0)
        last_total_words = new_tw
        last_word_ts     = time.time()

# start the WebSocket client in a background thread
def start_ws():
    ws = WebSocketApp(WS_URL, on_message=on_ws_message)
    ws.run_forever()

threading.Thread(target=start_ws, daemon=True).start()

# ─── PREPARE FONTS ─────────────────────────────────────────────────────────────

def load_font(size):
    if os.path.exists(TAHOMA_TTF):
        return ImageFont.truetype(TAHOMA_TTF, size)
    # fallback to DejaVu
    return ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size
    )

font_big   = load_font(FONT_BIG)
font_small = load_font(FONT_SMALL)

# ─── MAIN LOOP ────────────────────────────────────────────────────────────────

try:
    while True:
        now = time.time()
        idle = (now - last_word_ts) > IDLE_THRESHOLD

        # create an all-white overlay
        img  = Image.new("1", (W, H), 255)
        draw = ImageDraw.Draw(img)

        if idle:
            # ── Idle Mode: big clock HH:MM centered ────────────────────
            tstr = datetime.now().strftime("%H:%M")
            bb   = draw.textbbox((0,0), tstr, font=font_big)
            tw   = bb[2] - bb[0]
            th   = bb[3] - bb[1]
            x    = (W - tw)//2
            y    = (H - th)//2
            draw.text((x, y), tstr, font=font_big, fill=0)

        else:
            # ── Typing Mode ────────────────────────────────────────────
            # 1) small clock in top-right corner (15px from right, 5px down)
            tstr = datetime.now().strftime("%H:%M")
            bb   = draw.textbbox((0,0), tstr, font=font_small)
            tw   = bb[2] - bb[0]
            draw.text((W - tw - 15, 5), tstr, font=font_small, fill=0)

            # 2) frozen WPM in big font, centered vertically above ACC
            wpm_str = f"{int(freeze_wpm)} WPM"
            bb      = draw.textbbox((0,0), wpm_str, font=font_big)
            wpw     = bb[2] - bb[0]
            wph     = bb[3] - bb[1]
            # measure ACC height via a dummy "0"
            bb0     = draw.textbbox((0,0), "0", font=font_small)
            acc_h   = bb0[3] - bb0[1]
            y0      = (H - (wph + SPACING + acc_h)) // 2
            x0      = (W - wpw)//2
            draw.text((x0, y0), wpm_str, font=font_big, fill=0)

            # 3) frozen ACC below
            acc_str = f"{int(freeze_acc)}% ACC"
            bb2     = draw.textbbox((0,0), acc_str, font=font_small)
            aw      = bb2[2] - bb2[0]
            x2      = (W - aw)//2
            y2      = y0 + wph + SPACING
            draw.text((x2, y2), acc_str, font=font_small, fill=0)

        # Partial‐update only what changed
        epd.displayPartial(epd.getbuffer(img))
        time.sleep(1.0)

except KeyboardInterrupt:
    # clean shutdown
    epd.init()
    epd.Clear(0xFF)
    epd.sleep()
