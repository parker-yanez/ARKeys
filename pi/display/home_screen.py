#!/usr/bin/env python3
import time, threading, json, os
from datetime import datetime
from websocket import create_connection
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V4

# ——— CONFIG —————————————————————————————————————————————————————————————————
WS_URL              = "ws://192.168.1.225:8765"
IDLE_UI_THRESHOLD   = 60.0    # seconds after last word → back to Idle
FONT_NAME           = "Tahoma"
FONT_SIZE_IDLE      = 48      # big clock in Idle
FONT_SIZE_TYPE      = 12      # small clock in Typing
FONT_SIZE_WPM       = 36      # wpm in Typing
FONT_SIZE_ACC       = 24      # accuracy in Typing
CLOCK_MARGIN_RIGHT  = 15
CLOCK_MARGIN_TOP    = 5
SPACING             = 5       # vertical gap between WPM and ACC

ROOT      = os.path.expanduser('~/ARKeys')
ASSETS    = os.path.join(ROOT, 'assets')
STATICUI  = os.path.join(ASSETS, 'static_ui.png')
TAHOMA    = os.path.join(ASSETS, 'Tahoma.ttf')

# ——— GLOBAL STATE ———————————————————————————————————————————————————————————————
metrics       = {"wpm":0.0, "accuracy":100.0, "total_words":0}
last_total    = 0
freeze_wpm    = 0.0
freeze_acc    = 100.0
last_word_ts  = None

# ——— E-INK SETUP ——————————————————————————————————————————————————————————————
epd = epd2in13_V4.EPD()
epd.init(); epd.Clear(0xFF)
w, h = epd.height, epd.width

# static background
base = Image.open(STATICUI).convert('1')
epd.display(epd.getbuffer(base))
epd.displayPartBaseImage(epd.getbuffer(base))

# load fonts helper
def load_font(size):
    if os.path.exists(TAHOMA):
        return ImageFont.truetype(TAHOMA, size)
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)

font_time_idle = load_font(FONT_SIZE_IDLE)
font_time_type = load_font(FONT_SIZE_TYPE)
font_wpm       = load_font(FONT_SIZE_WPM)
font_acc       = load_font(FONT_SIZE_ACC)

# ——— WEBSOCKET LISTENER ————————————————————————————————————————————————————————
def ws_listener():
    global metrics, last_total, freeze_wpm, freeze_acc, last_word_ts
    while True:
        try:
            ws = create_connection(WS_URL)
            while True:
                msg = ws.recv()
                data = json.loads(msg)
                metrics = data
                # freeze on new word
                if data.get("total_words",0) > last_total:
                    last_total   = data["total_words"]
                    freeze_wpm   = data["wpm"]
                    freeze_acc   = data["accuracy"]
                    last_word_ts = time.time()
        except Exception:
            time.sleep(5)

threading.Thread(target=ws_listener, daemon=True).start()

# ——— MAIN RENDER LOOP —————————————————————————————————————————————————————————
try:
    while True:
        now = datetime.now()
        idle = not (last_word_ts and time.time() - last_word_ts < IDLE_UI_THRESHOLD)

        img  = Image.new('1', (w, h), 255)
        draw = ImageDraw.Draw(img)

        if idle:
            # Idle mode: big centered clock
            time_str = now.strftime("%H:%M")
            bx, by = draw.textbbox((0,0), time_str, font=font_time_idle)[2:]
            x = (w - bx)//2
            y = (h - by)//2
            draw.text((x,y), time_str, font=font_time_idle, fill=0)

        else:
            # Typing mode: small clock top-right
            time_str = now.strftime("%H:%M")
            bx, by = draw.textbbox((0,0), time_str, font=font_time_type)[2:]
            x = w - bx - CLOCK_MARGIN_RIGHT
            y = CLOCK_MARGIN_TOP
            draw.text((x,y), time_str, font=font_time_type, fill=0)

            # Big WPM centered
            wpm_str = f"{int(freeze_wpm)} WPM"
            bx, by = draw.textbbox((0,0), wpm_str, font=font_wpm)[2:]
            x = (w - bx)//2
            # shift up a bit to make room for ACC below
            y = (h - (by + SPACING + font_acc.getsize("0")[1]))//2
            draw.text((x,y), wpm_str, font=font_wpm, fill=0)

            # Accuracy below WPM
            acc_str = f"{int(freeze_acc)}% ACC"
            bx2, by2 = draw.textbbox((0,0), acc_str, font=font_acc)[2:]
            x2 = (w - bx2)//2
            y2 = y + by + SPACING
            draw.text((x2,y2), acc_str, font=font_acc, fill=0)

        # partial update
        epd.displayPartial(epd.getbuffer(img))
        time.sleep(1)

except KeyboardInterrupt:
    epd.init(); epd.Clear(0xFF); epd.sleep()
