#!/usr/bin/env python3
import time, threading, json, os
from datetime import datetime
from websocket import create_connection
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V4

# ——— CONFIG —————————————————————————————————————————————————————————————————
WS_URL             = "ws://192.168.1.225:8765"
IDLE_UI_THRESHOLD  = 60.0    # seconds of “no new word” → go back to Idle
FONT_NAME          = "Tahoma"
FONT_SIZE_TIME     = 48
FONT_SIZE_WPM      = 48
# positions
CLOCK_MARGIN_RIGHT = 15
CLOCK_MARGIN_TOP   = 5

# paths
ROOT      = os.path.expanduser('~/ARKeys')
ASSETS    = os.path.join(ROOT, 'assets')
STATICUI  = os.path.join(ASSETS, 'static_ui.png')
TAHOMA    = os.path.join(ASSETS, 'Tahoma.ttf')

# ——— GLOBAL STATE ———————————————————————————————————————————————————————————————
metrics       = {"wpm":0.0, "total_words":0}
last_total    = 0
freeze_wpm    = 0.0
last_word_ts  = None

# ——— E-INK SETUP ——————————————————————————————————————————————————————————————
epd = epd2in13_V4.EPD()
epd.init()
epd.Clear(0xFF)
w, h = epd.height, epd.width   # 122×250

# load & display static background
base = Image.open(STATICUI).convert('1')
epd.display(epd.getbuffer(base))
epd.displayPartBaseImage(epd.getbuffer(base))

# load fonts
if os.path.exists(TAHOMA):
    font_time = ImageFont.truetype(TAHOMA, FONT_SIZE_TIME)
    font_wpm  = ImageFont.truetype(TAHOMA, FONT_SIZE_WPM)
else:
    font_time = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", FONT_SIZE_TIME)
    font_wpm  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", FONT_SIZE_WPM)

# ——— WEBSOCKET LISTENER ————————————————————————————————————————————————————————
def ws_listener():
    global metrics, last_total, freeze_wpm, last_word_ts
    while True:
        try:
            ws = create_connection(WS_URL)
            while True:
                msg = ws.recv()
                data = json.loads(msg)
                metrics = data
                # on each new word, freeze the wpm
                if data.get("total_words",0) > last_total:
                    last_total   = data["total_words"]
                    freeze_wpm   = data["wpm"]
                    last_word_ts = time.time()
        except Exception:
            # reconnect after a pause
            time.sleep(5)

threading.Thread(target=ws_listener, daemon=True).start()

# ——— MAIN RENDER LOOP —————————————————————————————————————————————————————————
try:
    while True:
        now = datetime.now()
        mode = "typing" if (last_word_ts and time.time()-last_word_ts < IDLE_UI_THRESHOLD) else "idle"

        # build overlay
        img  = Image.new('1',(w,h),255)
        draw = ImageDraw.Draw(img)

        if mode == "idle":
            # center HH:MM
            time_str = now.strftime("%H:%M")
            bx, by = draw.textbbox((0,0), time_str, font=font_time)[2:]
            x = (w - bx)//2
            y = (h - by)//2
            draw.text((x,y), time_str, font=font_time, fill=0)

        else:
            # clock top-right
            time_str = now.strftime("%H:%M")
            bx, by = draw.textbbox((0,0), time_str, font=font_time)[2:]
            x = w - bx - CLOCK_MARGIN_RIGHT
            y = CLOCK_MARGIN_TOP
            draw.text((x,y), time_str, font=font_time, fill=0)

            # WPM centered
            wpm_str = f"{int(freeze_wpm)} WPM"
            bx, by = draw.textbbox((0,0), wpm_str, font=font_wpm)[2:]
            x = (w - bx)//2
            y = (h - by)//2
            draw.text((x,y), wpm_str, font=font_wpm, fill=0)

        # partial update
        epd.displayPartial(epd.getbuffer(img))
        time.sleep(1)

except KeyboardInterrupt:
    epd.init(); epd.Clear(0xFF); epd.sleep()
