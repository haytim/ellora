"""Drive the Ellora65 OLED from your PC: live clock + streamed GIFs.

Needs the "display" firmware from firmware/keymaps/display. Fn + \\ on the
keyboard switches the OLED between the clock and the GIF.

    python ellora_display.py                       # clock + tools/input.gif (if present)
    python ellora_display.py cat.gif               # clock + another GIF
    python ellora_display.py gifs/ --switch-every 60 --12h
    python ellora_display.py cat.gif --preview cat_preview.png   # no keyboard needed

Close this app before using VIA: both talk over the same USB interface, and
VIA can get confused by this app's replies.
"""

import argparse
import datetime
import sys
import time
from pathlib import Path

import hid
from PIL import Image, ImageOps, ImageSequence

VENDOR_ID = 0x04D8
PRODUCT_ID = 0xE88F
RAW_USAGE_PAGE = 0xFF60
RAW_USAGE = 0x61
REPORT_SIZE = 32

CMD_STATUS = 0xE0
CMD_SET_TIME = 0xE1
CMD_GIF_CHUNK = 0xE2

MODE_CLOCK, MODE_GIF = 0, 1
TIME_FLAG_12H = 0x01

WIDTH, HEIGHT = 32, 128  # the OLED as mounted (rotated portrait strip)
FRAME_BYTES = WIDTH * HEIGHT // 8
CHUNK_BYTES = 30
MIN_FRAME_MS = 20

DEFAULT_GIF = Path(__file__).with_name("input.gif")


# ---------------------------------------------------------------- GIF -> frames

def to_oled_bytes(img):
    """Pack a 32x128 1-bit image into the OLED buffer layout.

    The buffer is 16 pages of 8 pixel rows; each byte is one column of a page
    with the top pixel in bit 0.
    """
    px = img.load()
    out = bytearray(FRAME_BYTES)
    for page in range(HEIGHT // 8):
        for x in range(WIDTH):
            byte = 0
            for bit in range(8):
                if px[x, page * 8 + bit]:
                    byte |= 1 << bit
            out[page * WIDTH + x] = byte
    return bytes(out)


def load_gif(path, fill=False, rotate=0, invert=False, threshold=None):
    """Return [(oled_bytes, duration_ms), ...] for every frame of a GIF/image."""
    frames = []
    with Image.open(path) as gif:
        for frame in ImageSequence.Iterator(gif):
            duration = frame.info.get("duration") or 100
            img = frame.convert("RGBA")
            background = Image.new("RGBA", img.size, (0, 0, 0, 255))
            img = Image.alpha_composite(background, img).convert("L")
            if rotate:
                img = img.rotate(rotate, expand=True)
            if fill:
                img = ImageOps.fit(img, (WIDTH, HEIGHT), Image.LANCZOS)
            else:
                img = ImageOps.pad(img, (WIDTH, HEIGHT), Image.LANCZOS, color=0)
            if invert:
                img = ImageOps.invert(img)
            if threshold is None:
                img = img.convert("1")  # Floyd-Steinberg dithering
            else:
                img = img.point(lambda v: 255 if v >= threshold else 0).convert("1")
            frames.append((to_oled_bytes(img), max(int(duration), MIN_FRAME_MS)))
    return frames


def frame_to_image(data):
    img = Image.new("1", (WIDTH, HEIGHT))
    px = img.load()
    for page in range(HEIGHT // 8):
        for x in range(WIDTH):
            byte = data[page * WIDTH + x]
            for bit in range(8):
                px[x, page * 8 + bit] = 1 if byte & (1 << bit) else 0
    return img


def write_preview(frames, path, scale=3, max_frames=24):
    """Save a contact sheet of the frames exactly as the OLED will show them."""
    shown = frames[:max_frames]
    gap = 4
    sheet = Image.new("L", ((WIDTH * scale + gap) * len(shown) + gap, HEIGHT * scale + 2 * gap), 60)
    for i, (data, _) in enumerate(shown):
        img = frame_to_image(data).convert("L").resize((WIDTH * scale, HEIGHT * scale), Image.NEAREST)
        sheet.paste(img, (gap + i * (WIDTH * scale + gap), gap))
    sheet.save(path)


def collect_gif_paths(inputs):
    paths = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            paths += sorted(q for q in p.iterdir() if q.suffix.lower() in (".gif", ".png", ".jpg", ".jpeg", ".webp", ".bmp"))
        else:
            paths.append(p)
    return paths


# ---------------------------------------------------------------- keyboard link

class Keyboard:
    def __init__(self):
        self.dev = None
        self.mode = MODE_CLOCK

    def connect(self):
        for info in hid.enumerate(VENDOR_ID, PRODUCT_ID):
            if info["usage_page"] == RAW_USAGE_PAGE and info["usage"] == RAW_USAGE:
                dev = hid.device()
                dev.open_path(info["path"])
                self.dev = dev
                if self.command(CMD_STATUS) is None:
                    self.close()
                    raise RuntimeError(
                        "Keyboard found, but it is not running the display firmware "
                        "(flash kikoslab_ellora65_display.hex)."
                    )
                return True
        return False

    def close(self):
        if self.dev:
            try:
                self.dev.close()
            except OSError:
                pass
        self.dev = None

    def command(self, cmd, payload=b""):
        """Send one report and wait for its reply. Returns the reply or None."""
        report = bytes([cmd]) + bytes(payload)
        report = report.ljust(REPORT_SIZE, b"\x00")
        # Leading 0x00 is the (unused) HID report ID.
        if self.dev.write(b"\x00" + report) < 0:
            raise OSError("HID write failed")
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            reply = self.dev.read(REPORT_SIZE, 100)
            # Skip replies meant for VIA if it happens to be open too.
            if reply and reply[0] == cmd:
                self.mode = reply[1]
                return reply
            if reply and reply[0] == 0xFF:  # id_unhandled: stock firmware
                return None
        raise OSError("No reply from keyboard")

    def send_time(self, now, use_12h):
        lines = [
            now.strftime("%a").upper(),
            f"{now.day}{now.strftime('%b').upper()}",
            now.strftime("%p") if use_12h else "",
        ]
        text = b"".join(line.center(5)[:5].encode("ascii") for line in lines)
        flags = TIME_FLAG_12H if use_12h else 0
        self.command(CMD_SET_TIME, bytes([now.hour, now.minute, now.second, flags]) + text)

    def send_frame(self, data):
        for chunk in range((FRAME_BYTES + CHUNK_BYTES - 1) // CHUNK_BYTES):
            part = data[chunk * CHUNK_BYTES:(chunk + 1) * CHUNK_BYTES]
            self.command(CMD_GIF_CHUNK, bytes([chunk]) + part)
            if self.mode != MODE_GIF:
                return  # user switched to the clock mid-frame


# ---------------------------------------------------------------- main loop

def run(kb, gifs, args):
    gif_index, frame_index = 0, 0
    gif_started = time.monotonic()
    last_second = None
    next_frame_at = 0.0

    while True:
        now = datetime.datetime.now()
        if now.second != last_second:
            kb.send_time(now, args.twelve_hour)
            last_second = now.second

        if kb.mode == MODE_GIF and gifs:
            if len(gifs) > 1 and time.monotonic() - gif_started > args.switch_every:
                gif_index = (gif_index + 1) % len(gifs)
                frame_index, gif_started = 0, time.monotonic()
            frames = gifs[gif_index][1]
            if time.monotonic() >= next_frame_at:
                data, duration = frames[frame_index]
                next_frame_at = time.monotonic() + duration / 1000
                kb.send_frame(data)
                frame_index = (frame_index + 1) % len(frames)
            time.sleep(0.005)
        else:
            # Wake shortly after the next second ticks over, but poll the mode
            # often enough that Fn + \ feels instant.
            time.sleep(min(0.1, 1.0 - datetime.datetime.now().microsecond / 1e6 + 0.01))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("gifs", nargs="*",
                        help="GIF/image files or folders to show in GIF mode (default: tools/input.gif)")
    parser.add_argument("--12h", dest="twelve_hour", action="store_true", help="12-hour clock (default 24-hour)")
    parser.add_argument("--fill", action="store_true", help="crop to fill the screen instead of letterboxing")
    parser.add_argument("--rotate", type=int, choices=(0, 90, 180, 270), default=0,
                        help="rotate the GIF first (90/270 suit wide GIFs on the tall screen)")
    parser.add_argument("--invert", action="store_true", help="swap black and white")
    parser.add_argument("--threshold", type=int, metavar="0-255",
                        help="plain black/white cut-off instead of dithering (try 128)")
    parser.add_argument("--switch-every", type=float, default=30, metavar="SECONDS",
                        help="with several GIFs, move to the next one this often (default 30)")
    parser.add_argument("--preview", metavar="PNG", help="save how the first GIF will look, then exit")
    args = parser.parse_args()

    if not args.gifs and DEFAULT_GIF.exists():
        args.gifs = [DEFAULT_GIF]

    gifs = []
    for path in collect_gif_paths(args.gifs):
        frames = load_gif(path, args.fill, args.rotate, args.invert, args.threshold)
        gifs.append((path.name, frames))
        print(f"Loaded {path.name}: {len(frames)} frame(s)")

    if args.preview:
        if not gifs:
            parser.error("--preview needs a GIF")
        write_preview(gifs[0][1], args.preview)
        print(f"Preview saved to {args.preview}")
        return

    kb = Keyboard()
    waiting_shown = False
    while True:
        try:
            if not kb.connect():
                if not waiting_shown:
                    print("Waiting for the Ellora65...")
                    waiting_shown = True
                time.sleep(2)
                continue
            waiting_shown = False
            print("Connected. Press Fn + \\ to switch between the clock and the GIF.")
            run(kb, gifs, args)
        except OSError as e:
            print(f"Keyboard disconnected ({e}); reconnecting...")
            kb.close()
            time.sleep(2)
        except RuntimeError as e:
            sys.exit(str(e))
        except KeyboardInterrupt:
            kb.close()
            return


if __name__ == "__main__":
    main()
