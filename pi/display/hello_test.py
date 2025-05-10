#!/usr/bin/env python3
import time
from PIL import Image, ImageDraw, ImageFont
from waveshare_epd import epd2in13_V2

def main():
    epd = epd2in13_V2.EPD()
    # Initialize for a full update
    epd.init(epd.FULL_UPDATE)
    epd.Clear(0xFF)

    # Note: width and height are swapped intentionally
    width, height = epd.height, epd.width
    image = Image.new('1', (width, height), 255)
    draw  = ImageDraw.Draw(image)

    # Draw text in center
    font = ImageFont.load_default()
    text = "Hello Arkkeys!"
    w, h = draw.textsize(text, font=font)
    draw.text(((width-w)//2, (height-h)//2), text, font=font, fill=0)

    epd.display(epd.getbuffer(image))
    time.sleep(2)

    epd.sleep()
    print("Hello test done.")

if __name__ == "__main__":
    main()
