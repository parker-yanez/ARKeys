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

IDLE_THRESHOLD = 10.0
WS_URL         = "ws://192.168.1.225:8765"

# init e-ink
epd = epd2in13_V4.EPD()
epd.init(); epd.Clear(0xFF)
W, H = epd.height, epd.width

# font sizes
FONT_BIG       = 48   # idle clock & WPM
FONT_CLOCK_SM  = 12   # typing-mode clock
FONT_ACC       = 18   # accuracy
SPACING        = 5    # gap between WPM and ACC baseline

ASSETS         = os.path.expanduser('~/ARKeys/assets')
TAHOMA_TTF     = os.path.join(ASSETS, 'Tahoma.ttf')

# ─── STATE ────────────────────────────────────────────────────────────────────

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

    if new_tw > last_total_words:
        freeze_wpm       = data.get("wpm", 0.0)
        freeze_acc       = data.get("accuracy", 100.0)
        last_total_words = new_tw
        last_word_ts     = time.time()

def start_ws():
    ws = WebSocketApp(WS_URL, on_message=on_ws_message)
    ws.run_forever()

threading.Thread(target=start_ws, daemon=True).start()

# ─── FONTS ────────────────────────────────────────────────────────────────────

def load_font(size):
    if os.path.exists(TAHOMA_TTF):
        return ImageFont.truetype(TAHOMA_TTF, size)
    return ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size
    )

font_big        = load_font(FONT_BIG)
font_clock_sm   = load_font(FONT_CLOCK_SM)
font_accuracy   = load_font(FONT_ACC)

# ─── MAIN LOOP ────────────────────────────────────────────────────────────────

try:
    while True:
        now    = time.time()
        idle   = (now - last_word_ts) > IDLE_THRESHOLD

        img    = Image.new("1", (W, H), 255)
        draw   = ImageDraw.Draw(img)

        if idle:
            # Idle: big HH:MM centered
            tstr = datetime.now().strftime("%H:%M")
            bb   = draw.textbbox((0,0), tstr, font=font_big)
            tw   = bb[2] - bb[0]
            th   = bb[3] - bb[1]
            draw.text(
                ((W-tw)//2, (H-th)//2),
                tstr,
                font=font_big,
                fill=0
            )

        else:
            # Typing mode

            # 1) small clock top-right
            tstr = datetime.now().strftime("%H:%M")
            bb   = draw.textbbox((0,0), tstr, font=font_clock_sm)
            tw   = bb[2] - bb[0]
            draw.text(
                (W - tw - 15, 5),
                tstr,
                font=font_clock_sm,
                fill=0
            )

            # 2) frozen WPM centered vertically above ACC
            wpm_str = f"{int(freeze_wpm)} WPM"
            bb_wpm  = draw.textbbox((0,0), wpm_str, font=font_big)
            wpw     = bb_wpm[2] - bb_wpm[0]
            wph     = bb_wpm[3] - bb_wpm[1]
            y0      = (H - (wph + SPACING + 0))//2  # ACC shift handled below
            x0      = (W - wpw)//2
            draw.text((x0, y0), wpm_str, font=font_big, fill=0)

            # 3) frozen ACC below, 20px further down
            acc_str = f"{int(freeze_acc)}% ACC"
            bb_acc  = draw.textbbox((0,0), acc_str, font=font_accuracy)
            aw      = bb_acc[2] - bb_acc[0]
            x2      = (W - aw)//2
            # original baseline would be y0 + wph + SPACING
            y2      = y0 + wph + SPACING + 20
            draw.text((x2, y2), acc_str, font=font_accuracy, fill=0)

        # partial update
        epd.displayPartial(epd.getbuffer(img))
        time.sleep(1.0)

except KeyboardInterrupt:
    epd.init(); epd.Clear(0xFF); epd.sleep()
