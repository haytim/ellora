"""Live data for the PC-drawn screens: system stats, now playing and volume.

Stats and media are polled on background threads; read `.data` for the latest
snapshot (a dict that is replaced, never mutated).
"""

import asyncio
import ctypes
import datetime
import re
import threading
import time
from pathlib import Path

import psutil

# CPU temperature needs a kernel driver on Windows, so it is read from
# ThrottleStop's log file (tick "Log File" in ThrottleStop). Without a fresh
# log the Stats screen shows CPU load instead.
# ThrottleStop buffers its log and writes a minute of lines at once, so the
# newest line can be up to ~60 s old.
THROTTLESTOP_LOG_MAX_AGE_S = 90


def _number(text):
    match = re.search(r"-?\d+(?:[.,]\d+)?", text or "")
    return float(match.group().replace(",", ".")) if match else None


def throttlestop_log_dirs():
    """ThrottleStop log folders: each install's LogFileDirectory, or its Logs folder."""
    home = Path.home()
    dirs = []
    for base in (home / "Documents", home / "Downloads", home / "Desktop", Path("C:/"),
                 Path("C:/Program Files"), Path("C:/Program Files (x86)")):
        for ini in base.glob("ThrottleStop*/ThrottleStop.ini"):
            log_dir = ini.parent / "Logs"
            try:
                for line in ini.read_text(errors="ignore").splitlines():
                    if line.startswith("LogFileDirectory="):
                        log_dir = Path(line.split("=", 1)[1].strip())
            except OSError:
                pass
            dirs.append(log_dir)
    return dirs


def throttlestop_cpu_temp(log_dirs):
    """CPU temperature from the newest line of the newest ThrottleStop log, if recent."""
    logs = [f for d in log_dirs if d.is_dir() for f in d.glob("*.txt")]
    if not logs:
        return None
    newest = max(logs, key=lambda f: f.stat().st_mtime)
    if time.time() - newest.stat().st_mtime > THROTTLESTOP_LOG_MAX_AGE_S:
        return None  # logging is off or ThrottleStop isn't running
    with open(newest, "rb") as f:
        header = f.readline().decode(errors="ignore").split()
        f.seek(max(0, newest.stat().st_size - 512))
        lines = f.read().decode(errors="ignore").splitlines()
    # Columns before TEMP are single words in both the header and the data rows.
    column = header.index("TEMP")
    for line in reversed(lines):
        fields = line.split()
        if len(fields) > column and re.fullmatch(r"\d{4}-\d{2}-\d{2}", fields[0]):
            return _number(fields[column])
    return None


class NvidiaGpu:
    """First NVIDIA GPU's temperature and load via the driver's NVML library.

    Calling nvml.dll in-process costs microseconds, versus ~60 ms of CPU for
    launching nvidia-smi.
    """

    class _Utilization(ctypes.Structure):
        _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

    def __init__(self):
        self._nvml = ctypes.WinDLL("nvml.dll")  # installed with the NVIDIA driver
        if self._nvml.nvmlInit_v2() != 0:
            raise OSError("nvmlInit failed")
        self._handle = ctypes.c_void_p()
        if self._nvml.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(self._handle)) != 0:
            raise OSError("no NVIDIA GPU")

    def read(self):
        """Return (temp °C, load %)."""
        temp, util = ctypes.c_uint(), self._Utilization()
        if self._nvml.nvmlDeviceGetTemperature(self._handle, 0, ctypes.byref(temp)) != 0:  # 0 = GPU core
            raise OSError("NVML temperature read failed")
        if self._nvml.nvmlDeviceGetUtilizationRates(self._handle, ctypes.byref(util)) != 0:
            raise OSError("NVML utilization read failed")
        return float(temp.value), float(util.gpu)


class StatsSource:
    """Polls system stats, but only while `wanted` is set (the Stats screen is up)."""

    def __init__(self, interval=1.0):
        self.interval = interval
        self.data = {}
        self.wanted = threading.Event()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            gpu = NvidiaGpu()
        except OSError:
            gpu = None
        log_dirs, log_dirs_at = [], 0.0
        while True:
            if not self.wanted.is_set():
                self.wanted.wait()
                psutil.cpu_percent()  # restart the CPU load measurement
                time.sleep(0.25)
            ram = psutil.virtual_memory()
            data = {
                "cpu_load": psutil.cpu_percent(),
                "ram_used_gb": (ram.total - ram.available) / 2**30,
                "ram_total_gb": ram.total / 2**30,
                "cpu_temp": None, "gpu_temp": None, "gpu_load": None,
            }
            if time.monotonic() - log_dirs_at > 60:  # pick up new installs/settings
                log_dirs, log_dirs_at = throttlestop_log_dirs(), time.monotonic()
            try:
                data["cpu_temp"] = throttlestop_cpu_temp(log_dirs)
            except (OSError, ValueError):
                pass
            if gpu:
                try:
                    data["gpu_temp"], data["gpu_load"] = gpu.read()
                except OSError:
                    pass
            self.data = data
            time.sleep(self.interval)


class MediaSource:
    """Now playing info from Windows' media controls (Spotify, browsers, ...)."""

    PLAYING = 4  # GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING

    def __init__(self, interval=1.0):
        self.interval = interval
        self.data = None
        threading.Thread(target=lambda: asyncio.run(self._run()), daemon=True).start()

    async def _run(self):
        from winrt.windows.media.control import \
            GlobalSystemMediaTransportControlsSessionManager as SessionManager

        manager = await SessionManager.request_async()
        while True:
            try:
                self.data = await self._snapshot(manager)
            except Exception:  # player closed mid-query etc.; keep polling
                self.data = None
            await asyncio.sleep(self.interval)

    async def _snapshot(self, manager):
        session = manager.get_current_session()
        if session is None:
            return None
        props = await session.try_get_media_properties_async()
        playing = int(session.get_playback_info().playback_status) == self.PLAYING
        timeline = session.get_timeline_properties()
        duration = timeline.end_time.total_seconds()
        position = timeline.position.total_seconds()
        updated = timeline.last_updated_time
        if playing and updated.year > 2000:
            position += (datetime.datetime.now(datetime.timezone.utc) - updated).total_seconds()

        now = time.monotonic()
        previous = self.data or {}
        artist = re.sub(r" - Topic$", "", props.artist or "")  # YouTube's auto-generated channels
        same_track = (previous.get("title"), previous.get("artist")) == (props.title, artist)

        if duration <= 0 and same_track and previous.get("duration"):
            # Browsers report YouTube's length for the first second or two of a
            # video, then only zeros. Keep the length and count the position here.
            duration = previous["duration"]
            position = previous["position"] + (now - previous["fetched_at"] if previous["playing"] else 0)

        return {
            "title": props.title,
            "artist": artist,
            "playing": playing,
            "position": max(0.0, min(position, duration)) if duration > 0 else 0.0,
            "duration": duration,
            "fetched_at": now,
            # Restart title/artist scrolling when the track changes.
            "changed_at": previous.get("changed_at", now) if same_track else now,
        }


class VolumeWatcher:
    """Polls the default speaker's volume; poll() returns True when it changed."""

    def __init__(self):
        self.level, self.muted = None, None
        self._enumerator = None
        self._endpoint = None
        self._device_id = None
        self._checked_at = 0.0

    def _get_endpoint(self):
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        if self._enumerator is None:
            self._enumerator = AudioUtilities.GetDeviceEnumerator()
        # Follow a switch to headphones etc. Asking for the default device's ID
        # is cheap; opening its volume control only happens when it changes.
        if self._endpoint is None or time.monotonic() - self._checked_at > 2:
            device = self._enumerator.GetDefaultAudioEndpoint(0, 1)  # eRender, eMultimedia
            device_id = device.GetId()
            if device_id != self._device_id or self._endpoint is None:
                self._endpoint = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None) \
                    .QueryInterface(IAudioEndpointVolume)
                self._device_id = device_id
            self._checked_at = time.monotonic()
        return self._endpoint

    def poll(self):
        try:
            endpoint = self._get_endpoint()
            level = round(endpoint.GetMasterVolumeLevelScalar() * 100)
            muted = bool(endpoint.GetMute())
        except Exception:  # no audio device / COM errors: try again next poll
            self._enumerator = self._endpoint = None
            return False
        changed = self.level is not None and (level, muted) != (self.level, self.muted)
        self.level, self.muted = level, muted
        return changed
