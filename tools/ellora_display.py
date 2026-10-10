"""Drive the Ellora65 OLED from your PC: clock, GIF, PC stats and now playing.

Needs the "display" firmware from firmware/keymaps/display. Fn + \\ on the
keyboard cycles the OLED through Clock -> GIF -> Stats -> Music. Changing the
volume pops up a volume screen over any of them.

    python ellora_display.py                       # uses tools/input.gif (if present)
    python ellora_display.py cat.gif --12h
    python ellora_display.py gifs/ --switch-every 60
    python ellora_display.py --preview out.png     # save the screens as an image, no keyboard needed

CPU temperature is read from ThrottleStop's log file (tick "Log File" in
ThrottleStop); without it the Stats screen shows CPU load. Close this app before using VIA: both talk over the same USB
interface, and VIA can get confused by this app's replies.
"""

import argparse
import datetime
import sys
import time
from pathlib import Path

import hid
from PIL import Image, ImageOps, ImageSequence

import screens
from screens import FRAME_BYTES, HEIGHT, WIDTH, frame_to_image, to_oled_bytes
from sources import MediaSource, StatsSource, VolumeWatcher

VENDOR_ID = 0x04D8
PRODUCT_ID = 0xE88F
RAW_USAGE_PAGE = 0xFF60
RAW_USAGE = 0x61
REPORT_SIZE = 32

CMD_STATUS = 0xE0
CMD_SET_TIME = 0xE1
CMD_GIF_CHUNK = 0xE2
CMD_RELEASE = 0xE3
CMD_NOTIFY = 0xE4  # sent by the keyboard on its own when the mode or screen state changes

MODE_CLOCK, MODE_GIF, MODE_STATS, MODE_MUSIC = range(4)
TIME_FLAG_12H = 0x01

CHUNK_BYTES = 30
CHUNK_COUNT = (FRAME_BYTES + CHUNK_BYTES - 1) // CHUNK_BYTES
KEEPALIVE_S = 0.5  # the keyboard drops back to the clock after 1.5 s without frames
VOLUME_POPUP_S = 1.5
STATUS_CHECK_S = 10  # safety net in case a keyboard notification is missed
ACTIVE_TICK_S = 0.03  # while streaming a screen
IDLE_TICK_S = 0.05  # otherwise; only needed to notice volume changes quickly
MIN_FRAME_MS = 20

DEFAULT_GIF = Path(__file__).with_name("input.gif")


# ---------------------------------------------------------------- GIF -> frames

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


def collect_gif_paths(inputs):
    paths = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            paths += sorted(q for q in p.iterdir() if q.suffix.lower() in (".gif", ".png", ".jpg", ".jpeg", ".webp", ".bmp"))
        else:
            paths.append(p)
    return paths


class GifPlayer:
    def __init__(self, gifs, switch_every):
        self.gifs = gifs  # [(name, frames)]
        self.switch_every = switch_every
        self.gif_index = self.frame_index = 0
        self.gif_started = time.monotonic()
        self.next_frame_at = 0.0

    def current(self):
        if not self.gifs:
            return None
        now = time.monotonic()
        if len(self.gifs) > 1 and now - self.gif_started > self.switch_every:
            self.gif_index = (self.gif_index + 1) % len(self.gifs)
            self.frame_index, self.gif_started, self.next_frame_at = 0, now, 0.0
        frames = self.gifs[self.gif_index][1]
        if now >= self.next_frame_at:
            if self.next_frame_at:
                self.frame_index = (self.frame_index + 1) % len(frames)
            self.next_frame_at = now + frames[self.frame_index][1] / 1000
        return frames[self.frame_index][0]


# ---------------------------------------------------------------- keyboard link

class Keyboard:
    def __init__(self):
        self.dev = None
        self.mode = MODE_CLOCK
        self.screen_on = True

    def _update(self, report):
        """Take the mode and screen state from a reply or notification."""
        self.mode, self.screen_on = report[1], bool(report[3])

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
            if reply and reply[0] in (cmd, CMD_NOTIFY):
                self._update(reply)
                if reply[0] == cmd:
                    return reply
            if reply and reply[0] == 0xFF:  # id_unhandled: stock firmware
                return None
        raise OSError("No reply from keyboard")

    def wait(self, timeout):
        """Idle for up to `timeout` s, returning early if the keyboard reports a change."""
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            report = self.dev.read(REPORT_SIZE, max(1, round(remaining * 1000)))
            if report and report[0] == CMD_NOTIFY:
                self._update(report)
                return

    def send_time(self, now, use_12h):
        lines = [
            now.strftime("%a").upper(),
            f"{now.day}{now.strftime('%b').upper()}",
            now.strftime("%p") if use_12h else "",
        ]
        text = b"".join(line.center(5)[:5].encode("ascii") for line in lines)
        flags = TIME_FLAG_12H if use_12h else 0
        self.command(CMD_SET_TIME, bytes([now.hour, now.minute, now.second, flags]) + text)


class Streamer:
    """Keeps the keyboard's screen showing a frame, sending only changed chunks."""

    def __init__(self, kb):
        self.kb = kb
        self.shown = None  # what the keyboard's screen holds, if streaming
        self.last_send = 0.0

    def _send_chunk(self, data, chunk):
        part = data[chunk * CHUNK_BYTES:(chunk + 1) * CHUNK_BYTES]
        return self.kb.command(CMD_GIF_CHUNK, bytes([chunk]) + part)

    def show(self, data):
        full = self.shown is None
        if full:
            todo = range(CHUNK_COUNT)
        else:
            todo = [c for c in range(CHUNK_COUNT)
                    if data[c * CHUNK_BYTES:(c + 1) * CHUNK_BYTES] != self.shown[c * CHUNK_BYTES:(c + 1) * CHUNK_BYTES]]
            if not todo:
                if time.monotonic() - self.last_send < KEEPALIVE_S:
                    return
                todo = [0]
        for chunk in todo:
            reply = self._send_chunk(data, chunk)
            if not reply[2] and not full:
                # The keyboard had gone back to the clock (cleared screen):
                # a partial update isn't enough, send the whole frame.
                self.shown = None
                return self.show(data)
        self.shown = data
        self.last_send = time.monotonic()

    def release(self):
        if self.shown is not None:
            if self.kb.screen_on:
                self.kb.command(CMD_RELEASE)
            self.shown = None  # a sleeping screen has dropped the frame already


# ---------------------------------------------------------------- main loop

class CachedRender:
    """Re-draws a screen only when its input changes or `max_age` seconds pass."""

    def __init__(self, render, max_age=None):
        self.render = render
        self.max_age = max_age
        self.key = self.frame = None
        self.at = 0.0

    def get(self, *key):
        expired = self.max_age is not None and time.monotonic() - self.at >= self.max_age
        if self.frame is None or expired or key != self.key:
            self.frame, self.key, self.at = self.render(*key), key, time.monotonic()
        return self.frame


def run(kb, gif_player, stats, media, volume, args):
    streamer = Streamer(kb)
    stats_screen = CachedRender(screens.render_stats)
    music_screen = CachedRender(screens.render_music, max_age=0.25)  # scrolling + progress bar
    volume_screen = CachedRender(screens.render_volume)
    next_sync = next_status = 0.0
    popup_until = 0.0

    while True:
        # The keyboard keeps time itself, so syncing once a minute (on the
        # minute, so the date rolls over on time) is plenty.
        if time.monotonic() >= next_sync:
            now = datetime.datetime.now()
            kb.send_time(now, args.twelve_hour)
            next_sync = time.monotonic() + 60 - now.second - now.microsecond / 1e6 + 0.05
            next_status = time.monotonic() + STATUS_CHECK_S
        elif time.monotonic() >= next_status:
            kb.command(CMD_STATUS)
            next_status = time.monotonic() + STATUS_CHECK_S

        if volume.poll():
            popup_until = time.monotonic() + VOLUME_POPUP_S

        if kb.mode == MODE_STATS and kb.screen_on:
            stats.wanted.set()
        else:
            stats.wanted.clear()

        if not kb.screen_on:
            frame = None  # the keyboard's screen is asleep: send nothing
        elif time.monotonic() < popup_until:
            frame = volume_screen.get(volume.level, volume.muted)
        elif kb.mode == MODE_GIF:
            frame = gif_player.current()
        elif kb.mode == MODE_STATS:
            frame = stats_screen.get(stats.data)  # data dict is replaced on each poll
        elif kb.mode == MODE_MUSIC:
            frame = music_screen.get(media.data)
        else:
            frame = None

        if frame is None:
            streamer.release()  # back to the keyboard's own clock
        else:
            streamer.show(frame)
        kb.wait(IDLE_TICK_S if frame is None else ACTIVE_TICK_S)


def enable_efficiency_mode():
    """Windows 11 "Efficiency mode": EcoQoS + below-normal priority.

    Windows then runs the app on the most power-efficient clocks and never
    lets it compete with games or other foreground work.
    """
    try:
        import ctypes
        from ctypes import wintypes

        class PowerThrottlingState(ctypes.Structure):
            _fields_ = [("Version", wintypes.ULONG), ("ControlMask", wintypes.ULONG), ("StateMask", wintypes.ULONG)]

        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        process = kernel32.GetCurrentProcess()
        state = PowerThrottlingState(1, 1, 1)  # PROCESS_POWER_THROTTLING_EXECUTION_SPEED on
        kernel32.SetProcessInformation(process, 4, ctypes.byref(state), ctypes.sizeof(state))  # ProcessPowerThrottling
        kernel32.SetPriorityClass(process, 0x4000)  # BELOW_NORMAL_PRIORITY_CLASS
    except (AttributeError, OSError):
        pass  # not Windows 10+; run normally


def write_preview(frames, path, scale=3):
    """Save a strip of frames exactly as the OLED will show them."""
    gap = 4
    sheet = Image.new("L", ((WIDTH * scale + gap) * len(frames) + gap, HEIGHT * scale + 2 * gap), 60)
    for i, data in enumerate(frames):
        img = frame_to_image(data).convert("L").resize((WIDTH * scale, HEIGHT * scale), Image.NEAREST)
        sheet.paste(img, (gap + i * (WIDTH * scale + gap), gap))
    sheet.save(path)


def preview(gifs, args):
    stats, media, volume = StatsSource(), MediaSource(), VolumeWatcher()
    stats.wanted.set()
    time.sleep(2.5)  # let the background sources take a reading
    volume.poll()
    frames = [
        screens.render_stats(stats.data),
        screens.render_music(media.data),
        screens.render_volume(volume.level or 0, False),
        screens.render_volume(0, True),
    ]
    frames += [data for data, _ in gifs[0][1][:6]] if gifs else []
    write_preview(frames, args.preview)
    print(f"Preview (stats, music, volume, muted, GIF frames) saved to {args.preview}")
    print(f"Stats: {stats.data}")
    print(f"Media: {media.data}")
    if stats.data.get("cpu_temp") is None:
        print("CPU temperature unavailable (no recent ThrottleStop log): showing CPU load instead")


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
    parser.add_argument("--preview", metavar="PNG", help="save how the screens will look, then exit")
    args = parser.parse_args()

    if sys.stdout:  # None under pythonw; don't crash printing non-Latin song titles
        sys.stdout.reconfigure(errors="replace")

    if not args.gifs and DEFAULT_GIF.exists():
        args.gifs = [DEFAULT_GIF]

    gifs = []
    for path in collect_gif_paths(args.gifs):
        frames = load_gif(path, args.fill, args.rotate, args.invert, args.threshold)
        gifs.append((path.name, frames))
        print(f"Loaded {path.name}: {len(frames)} frame(s)")

    if args.preview:
        preview(gifs, args)
        return

    enable_efficiency_mode()
    gif_player = GifPlayer(gifs, args.switch_every)
    stats, media, volume = StatsSource(), MediaSource(), VolumeWatcher()

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
            print("Connected. Fn + \\ cycles Clock -> GIF -> Stats -> Music.")
            run(kb, gif_player, stats, media, volume, args)
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
