#!/usr/bin/env python3
import time
from PIL import Image, ImageDraw
from eink_driver import EInkDisplay
from segments import SevenSegmentDisplay

def main():
    # 1) Initialize display
    disp = EInkDisplay()
    disp.clear()

    # 2) Create a blank image to draw on (mode '1' = 1-bit BW)
    image = Image.new('1', (disp.width, disp.height), 255)
    draw  = ImageDraw.Draw(image)

    # 3) Create our seven-segment renderer at position (10,10)
    seg = SevenSegmentDisplay(draw, origin_x=10, origin_y=10,
                              segment_length=40, thickness=8)

    # 4) For digits 0–9, draw each for 1 second
    for digit in map(str, range(10)):
        seg.display_digit(digit)
        # Send full image once (will clear only what changed)
        disp.display_full(image)
        print(f"Displayed {digit}")
        time.sleep(1)

    # 5) Sleep the display
    disp.sleep()
    print("Demo complete. Display sleeping.")

if __name__ == "__main__":
    main()
