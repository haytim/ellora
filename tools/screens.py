"""Full-screen layouts the PC draws for the Ellora65's 32x128 OLED strip."""

import time
import unicodedata

from PIL import Image

from oled_font import GLYPHS

WIDTH, HEIGHT = 32, 128
FRAME_BYTES = WIDTH * HEIGHT // 8
HOT_TEMP_C = 85


def to_oled_bytes(img):
    """Pack a 32x128 1-bit image into the OLED buffer layout.

    The buffer is 16 pages of 8 pixel rows; each byte is one column of a page
    with the top pixel in bit 0.
    """
    px = img.convert("1").getdata()
    out = bytearray(FRAME_BYTES)
    for page in range(HEIGHT // 8):
        for x in range(WIDTH):
            byte = 0
            for bit in range(8):
                if px[(page * 8 + bit) * WIDTH + x]:
                    byte |= 1 << bit
            out[page * WIDTH + x] = byte
    return bytes(out)


def frame_to_image(data):
    img = Image.new("1", (WIDTH, HEIGHT))
    px = img.load()
    for page in range(HEIGHT // 8):
        for x in range(WIDTH):
            byte = data[page * WIDTH + x]
            for bit in range(8):
                px[x, page * 8 + bit] = 1 if byte & (1 << bit) else 0
    return img


def ascii_only(text):
    """Strip accents and replace anything the 5x7 font can't draw."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "".join(c if c in GLYPHS else "?" for c in text)


def wrap(text, width=5):
    """Word-wrap to lines of at most `width` characters, splitting long words."""
    lines, line = [], ""
    for word in ascii_only(text).split():
        while len(word) > width:
            if line:
                lines.append(line)
                line = ""
            lines.append(word[:width])
            word = word[width:]
        if not line:
            line = word
        elif len(line) + 1 + len(word) <= width:
            line += " " + word
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


class Canvas:
    def __init__(self):
        self.img = Image.new("1", (WIDTH, HEIGHT), 0)
        self.px = self.img.load()

    def pixel(self, x, y, on=1):
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            self.px[x, y] = on

    def fill(self, x0, y0, x1, y1, on=1):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.pixel(x, y, on)

    def box(self, x0, y0, x1, y1):
        for x in range(x0, x1 + 1):
            self.pixel(x, y0)
            self.pixel(x, y1)
        for y in range(y0, y1 + 1):
            self.pixel(x0, y)
            self.pixel(x1, y)

    @staticmethod
    def text_width(text, scale=1, gap=None):
        gap = scale if gap is None else gap
        return len(text) * (5 * scale + gap) - gap if text else 0

    def text(self, x, y, text, scale=1, gap=None, on=1):
        gap = scale if gap is None else gap
        for ch in text:
            for col, bits in enumerate(GLYPHS.get(ch, GLYPHS["?"])):
                for row in range(8):
                    if bits & (1 << row):
                        self.fill(x + col * scale, y + row * scale,
                                  x + col * scale + scale - 1, y + row * scale + scale - 1, on)
            x += 5 * scale + gap

    def text_center(self, y, text, scale=1, gap=None, on=1):
        x = (WIDTH - self.text_width(text, scale, gap)) // 2
        self.text(x, y, text, scale, gap, on)

    def hbar(self, y, height, fraction):
        """Outlined bar across the full width, filled left to right."""
        self.box(0, y, WIDTH - 1, y + height - 1)
        inner = round((WIDTH - 4) * max(0.0, min(1.0, fraction)))
        if inner:
            self.fill(2, y + 2, 1 + inner, y + height - 3)

    def frame(self):
        return to_oled_bytes(self.img)


def scrolled(lines, visible, started, step=0.8, hold=2.0):
    """Pick `visible` lines, scrolling one line per `step` s with pauses at both ends."""
    extra = len(lines) - visible
    if extra <= 0:
        return lines
    cycle = hold + extra * step + hold
    t = (time.monotonic() - started) % cycle
    offset = 0 if t < hold else min(extra, int((t - hold) / step) + 1)
    return lines[offset:offset + visible]


# ---------------------------------------------------------------- stats

def _big_value(c, y, value, unit, hot=False):
    """Two big digits (or '--') followed by a small unit, left-aligned."""
    text = "--" if value is None else str(int(round(value)))
    scale, gap = (2, 2) if len(text) <= 2 else (2, 1)
    if hot:
        c.fill(0, y - 2, WIDTH - 1, y + 15)
    c.text(0, y, text, scale, gap, on=0 if hot else 1)
    x = c.text_width(text, scale, gap) + 2
    if unit == "deg":
        for dx, dy in ((1, 0), (0, 1), (2, 1), (1, 2)):  # tiny degree ring
            c.pixel(x + dx, y + dy, 0 if hot else 1)
    elif x + 5 <= WIDTH:
        c.text(x, y + 7, unit, on=0 if hot else 1)


def _stat_section(c, y, label, value, unit, fraction, caption=None, hot=False):
    """Label, big value, usage bar and optional caption in a 42px tall block."""
    c.text(0, y, label)
    _big_value(c, y + 10, value, unit, hot)
    c.hbar(y + 27, 6, fraction or 0)
    if caption:
        c.text_center(y + 35, caption)


def render_stats(stats):
    c = Canvas()
    cpu_t, gpu_t = stats.get("cpu_temp"), stats.get("gpu_temp")
    ram_used, ram_total = stats.get("ram_used_gb"), stats.get("ram_total_gb")

    # CPU/GPU: temperature, with load as the bar. Without a CPU temperature
    # (ThrottleStop not logging) the CPU shows its load instead.
    cpu_load = stats.get("cpu_load")
    if cpu_t is None:
        _stat_section(c, 0, "CPU", cpu_load, "%", (cpu_load or 0) / 100)
    else:
        _stat_section(c, 0, "CPU", cpu_t, "deg", (cpu_load or 0) / 100, hot=cpu_t >= HOT_TEMP_C)
    _stat_section(c, 43, "GPU", gpu_t, "deg", (stats.get("gpu_load") or 0) / 100,
                  hot=gpu_t is not None and gpu_t >= HOT_TEMP_C)
    # RAM: GB in use, with the bar showing it out of the total.
    ram_fraction = ram_used / ram_total if ram_used is not None and ram_total else 0
    _stat_section(c, 86, "RAM", ram_used, "G", ram_fraction,
                  "--" if ram_total is None else f"/{round(ram_total)}G")

    for y in (38, 81):  # dotted dividers
        for x in range(0, WIDTH, 2):
            c.pixel(x, y)
    return c.frame()


# ---------------------------------------------------------------- music

def _fmt_time(seconds):
    seconds = int(max(0, seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def render_music(media):
    c = Canvas()
    if not media or not media.get("title"):
        # Music note icon
        c.fill(17, 40, 18, 56)
        c.fill(19, 40, 22, 41)
        c.fill(21, 42, 22, 44)
        c.fill(12, 54, 17, 58)
        c.text_center(70, "No")
        c.text_center(80, "music")
        return c.frame()

    # Like a player's button: pause while playing, play while paused.
    if media["playing"]:
        c.fill(12, 0, 13, 6)  # pause bars
        c.fill(17, 0, 18, 6)
    else:
        for dx in range(4):  # play triangle
            c.fill(13 + dx, dx, 13 + dx, 6 - dx)

    started = media["changed_at"]
    for i, line in enumerate(scrolled(wrap(media["title"]), 6, started)):
        c.text(1, 11 + i * 8, line)
    for x in range(0, WIDTH, 2):
        c.pixel(x, 61)
    for i, line in enumerate(scrolled(wrap(media.get("artist") or ""), 4, started)):
        c.text(1, 65 + i * 8, line)

    duration = media.get("duration") or 0
    if duration > 0:
        position = media["position"]
        if media["playing"]:
            position += time.monotonic() - media["fetched_at"]
        position = min(position, duration)
        c.hbar(102, 6, position / duration)
        c.text_center(111, _fmt_time(position))
        c.text_center(120, _fmt_time(duration))
    return c.frame()


# ---------------------------------------------------------------- volume

def render_volume(level, muted):
    c = Canvas()
    # Speaker icon
    c.fill(7, 3, 9, 7)
    for i in range(4):
        c.fill(10 + i, 3 - i, 10 + i, 7 + i)
    if muted:
        for i in range(5):
            c.pixel(17 + i, 3 + i)
            c.pixel(21 - i, 3 + i)
    else:
        c.fill(17, 4, 17, 6)
        c.fill(19, 2, 19, 8)
        c.fill(21, 0, 21, 10)

    if muted:
        c.text_center(17, "MUTE")
    else:
        text = str(level)
        c.text_center(15, text, 2, 2 if len(text) <= 2 else 1)

    c.box(6, 36, 25, 125)
    if not muted:
        height = round(86 * level / 100)
        if height:
            c.fill(8, 124 - height + 1, 23, 123)
    return c.frame()
