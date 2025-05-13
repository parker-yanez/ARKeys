#!/usr/bin/env python3
import asyncio
import json
import time
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V4
import websockets

# ————— Helpers —————

def ordinal(n):
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1:'st',2:'nd',3:'rd'}.get(n%10,'th')}"

# ————— Config —————

WS_URI        = "ws://192.168.1.225:8765"  # change to your host’s IP
UPDATE_LIMIT  = 10   # seconds to force full refresh (for ghosting)
ROOT          = os.path.expanduser('~/ARKeys')
ASSETS        = os.path.join(ROOT, 'assets')
STATICUI      = os.path.join(ASSETS, 'static_ui.png')
TAHOMA_TTF    = os.path.join(ASSETS, 'Tahoma.ttf')
DEJAVU        = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

# ————— E-Paper init —————

epd = epd2in13_V4.EPD()
epd.init()
epd.Clear(0xFF)
w, h = epd.height, epd.width

# load & display static
base = Image.open(STATICUI).convert('1')
epd.display(epd.getbuffer(base))
epd.displayPartBaseImage(epd.getbuffer(base))

# load fonts
ttf = TAHOMA_TTF if os.path.exists(TAHOMA_TTF) else DEJAVU
font_h = ImageFont.truetype(ttf, 16)
font_f = ImageFont.truetype(ttf, 16)
font_a = ImageFont.truetype(ttf, 20)

# track last‐seen metrics so we only redraw on new words
_last_words = 0
_last_refresh = time.time()

async def consumer():
    global _last_words, _last_refresh

    async with websockets.connect(WS_URI) as ws:
        async for msg in ws:
            data = json.loads(msg)
            total_words = data['total_words']
            # only redraw when a new word has completed
            if total_words > _last_words:
                _last_words = total_words
                # extract
                wpm  = int(data['wpm'])
                acc  = int(data['accuracy'])
                # build overlay
                overlay = Image.new('1',(w,h),255)
                draw    = ImageDraw.Draw(overlay)

                # header: date/time
                now      = datetime.now()
                date_str = now.strftime('%B ') + ordinal(now.day)
                time_str = now.strftime('%H:%M')
                # centered date
                bd = draw.textbbox((0,0), date_str, font=font_h)
                dx = (w - (bd[2]-bd[0]))//2
                draw.text((dx,2), date_str, font=font_h, fill=0)
                # right-align time
                bt = draw.textbbox((0,0), time_str, font=font_h)
                draw.text((w - bt[2] - 5, 2), time_str, font=font_h, fill=0)

                # footer left: session timer (minutes only for stability)
                elapsed = int(data['active_time'])
                hh, rem = divmod(elapsed,3600)
                mm      = rem//60
                sess    = f"{hh:02d}:{mm:02d}"
                bs = draw.textbbox((0,0), sess, font=font_f)
                draw.text((5, h - bs[3] - 2), sess, font=font_f, fill=0)

                # footer right: avg WPM
                avg = f"avg {wpm}"
                ba  = draw.textbbox((0,0), avg, font=font_a)
                draw.text((w - ba[2] - 5, h - ba[3] - 2), avg, font=font_a, fill=0)

                # center bottom: accuracy
                ac = f"{acc}%"
                bc = draw.textbbox((0,0), ac, font=font_f)
                cx = (w - (bc[2]-bc[0]))//2
                draw.text((cx, h - bc[3] - 2), ac, font=font_f, fill=0)

                # partial refresh
                epd.displayPartial(epd.getbuffer(overlay))

                # every UPDATE_LIMIT seconds do a full refresh
                now_t = time.time()
                if now_t - _last_refresh > UPDATE_LIMIT:
                    epd.init()
                    epd.display(epd.getbuffer(base))
                    epd.displayPartBaseImage(epd.getbuffer(base))
                    _last_refresh = now_t

async def main():
    while True:
        try:
            await consumer()
        except (ConnectionRefusedError, websockets.ConnectionClosed):
            # retry after a short pause
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
