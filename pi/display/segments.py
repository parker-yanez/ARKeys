from PIL import ImageDraw

# Map each digit to the segments that should be “on”
DIGIT_TO_SEGMENTS = {
    '0': ['a','b','c','d','e','f'],
    '1': ['b','c'],
    '2': ['a','b','g','e','d'],
    '3': ['a','b','g','c','d'],
    '4': ['f','g','b','c'],
    '5': ['a','f','g','c','d'],
    '6': ['a','f','e','d','c','g'],
    '7': ['a','b','c'],
    '8': ['a','b','c','d','e','f','g'],
    '9': ['a','b','c','d','f','g'],
}

class SevenSegmentDisplay:
    def __init__(self, draw: ImageDraw.Draw, origin_x: int, origin_y: int,
                 segment_length: int = 40, thickness: int = 8, color=0):
        self.draw = draw
        self.ox = origin_x
        self.oy = origin_y
        self.L = segment_length
        self.T = thickness
        self.color = color
        self.current_segments = set()
        o, L, T = self.ox, self.L, self.T
        self.coords = {
            'a': [(o+T, self.oy), (o+T+L, self.oy),
                  (o+T+L-T, self.oy+T), (o+T+T, self.oy+T)],
            'b': [(o+L+T, self.oy+T), (o+L+2*T, self.oy+T),
                  (o+L+2*T, self.oy+T+L), (o+L+T, self.oy+T+L)],
            'c': [(o+L+T, self.oy+L+2*T), (o+L+2*T, self.oy+L+2*T),
                  (o+L+2*T, self.oy+2*L+2*T), (o+L+T, self.oy+2*L+2*T)],
            'd': [(o+T, self.oy+2*L+2*T), (o+T+L, self.oy+2*L+2*T),
                  (o+T+L-T, self.oy+2*L+3*T), (o+T+T, self.oy+2*L+3*T)],
            'e': [(o, self.oy+L+2*T), (o+T, self.oy+L+2*T),
                  (o+T, self.oy+2*L+2*T), (o, self.oy+2*L+2*T)],
            'f': [(o, self.oy+T), (o+T, self.oy+T),
                  (o+T, self.oy+T+L), (o, self.oy+T+L)],
            'g': [(o+T, self.oy+L+T), (o+T+L, self.oy+L+T),
                  (o+T+L-T, self.oy+L+2*T), (o+T+T, self.oy+L+2*T)],
        }

    def draw_segments(self, segments):
        for seg in segments:
            self.draw.polygon(self.coords[seg], fill=self.color)

    def clear_segments(self, segments, background=255):
        for seg in segments:
            self.draw.polygon(self.coords[seg], fill=background)

    def display_digit(self, digit: str):
        target = set(DIGIT_TO_SEGMENTS.get(digit, []))
        to_on  = target - self.current_segments
        to_off = self.current_segments - target
        if to_off:
            self.clear_segments(to_off)
        if to_on:
            self.draw_segments(to_on)
        self.current_segments = target.copy()
