import time
from PIL import Image
from waveshare_epd import epd2in13_V2

class EInkDisplay:
    def __init__(self):
        # Initialize the driver
        self.epd = epd2in13_V2.EPD()
        self.epd.init(self.epd.FULL_UPDATE)
        self.width  = self.epd.height
        self.height = self.epd.width

    def clear(self):
        self.epd.Clear(0xFF)

    def sleep(self):
        self.epd.sleep()

    def display_full(self, image: Image.Image):
        """Full refresh with a black/white PIL image."""
        self.epd.display(self.epd.getbuffer(image))

    def display_partial(self, image: Image.Image, x: int, y: int):
        """
        Partial update at position (x, y).
        x, y are the top-left coordinates.
        """
        buf = self.epd.getbuffer(image)
        self.epd.displayPartial(buf)  # uses internal busy/power handling
        # Note: some versions require epd.init(epd.PART_UPDATE) first.
        # If partial doesn’t work, switch to FULL_UPDATE for the first demo.
