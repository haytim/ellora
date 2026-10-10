# Ellora65 OLED: clock, GIFs, PC stats and now playing

Custom VIA firmware for the Kikos Lab Ellora65 plus a small PC app that drives the OLED.

The **key right of the Up arrow** cycles the screen through the four screens below. To move it, assign keycode `0x7E40` to another key in VIA: use *Any*, or `USER00` / *Custom 0*, depending on VIA's version.

1. **Clock**: big hour/minute digits, a seconds bar, the weekday/date (and AM/PM in 12h mode), with Luna the pet underneath.
2. **GIF**: any GIF, streamed full-screen from the PC.
3. **Stats**: CPU temperature (from ThrottleStop) and GPU temperature, each with load as a bar, and RAM in use out of the total. A temperature of 85°C or more is drawn inverted as a warning.
4. **Music**: the title and artist of whatever is playing (Spotify, YouTube in a browser, etc.), a play/pause icon and a progress bar. Long titles scroll.

**Volume pop-up**: turning the knob, or changing the volume any other way, shows the level over the current screen for 1.5 seconds.

Screens 2–4 and the volume pop-up are drawn by the PC app. While it isn't running, those screens show the clock instead.

The mode you pick is remembered after unplugging. The screen turns off after 5 minutes without typing (`OLED_TIMEOUT` in `firmware/keymaps/display/config.h`).

The keyboard has no clock of its own. The app sets the time, and the keyboard keeps counting if the app closes. Until the app has connected once, the clock shows `--:--`.

## Files

| Path | What |
|---|---|
| `kikoslab_ellora65_display.hex` | Firmware to flash |
| `kikoslab_ellora65_via.hex` | Your original stock VIA firmware (to go back) |
| `firmware/keymaps/display/` | Firmware source (QMK keymap) |
| `firmware/build.ps1` | Rebuilds the .hex with QMK MSYS |
| `tools/ellora_display.py` | PC app: talks to the keyboard, runs the screens |
| `tools/screens.py` | Layouts of the Stats, Music and Volume screens |
| `tools/sources.py` | Reads temperatures, RAM, now playing and volume |
| `tools/oled_font.py` | The keyboard's 5×7 font, for PC-drawn text |
| `tools/install_startup.ps1` | Run the PC app hidden at login |
| `tools/layout_to_keymap.py` | Turns a VIA layout export into `LAYOUT_all(...)` code |

## 1. Flash

QMK Toolbox 0.2.2's built-in flasher can't find this keyboard, so flash with QMK MSYS instead (or update QMK Toolbox):

1. Unplug the keyboard, hold **Esc**, and plug it back in. It's now in bootloader mode.
2. In QMK MSYS, run:
   ```
   dfu-programmer atmega32u4 erase --force
   dfu-programmer atmega32u4 flash --force /c/Users/zorig/ellora/kikoslab_ellora65_display.hex
   dfu-programmer atmega32u4 reset
   ```

VIA wipes its saved keymap when the firmware's build date changes. Your layers are compiled into this firmware, so the keys stay the same, but **macros are not**. If they're gone, in VIA go to *Save + Load* → *Load* and choose `ellora65.layout.json`.

To go back to stock, flash `kikoslab_ellora65_via.hex` the same way.

## 2. CPU temperature: ThrottleStop's log

Windows only lets programs with a hardware driver read CPU temperature. The app takes it from ThrottleStop's log instead:

1. Tick **Log File** in ThrottleStop.
2. The app finds the newest log in any `ThrottleStop*` folder under Documents, Downloads, Desktop, `C:\` or Program Files, using the folder set by `LogFileDirectory` in `ThrottleStop.ini`.
3. It reads the `TEMP` column from the latest line.

ThrottleStop writes its log in one-minute batches, so the temperature shown can be up to a minute old. If no log has been written in the last 90 seconds (logging off, or ThrottleStop closed), the CPU section shows **load %** instead of temperature.

ThrottleStop writes one line per second, which adds up to roughly 8 MB of logs per day in its `Logs` folder. It doesn't delete old logs, so clear them out now and then.

GPU temperature and load come from `nvidia-smi` (installed with your NVIDIA driver), and RAM from Windows directly.

## 3. Run the PC app

```powershell
python tools\ellora_display.py                          # uses tools\input.gif
python tools\ellora_display.py my.gif --12h             # a different GIF, 12-hour clock
python tools\ellora_display.py C:\gifs --switch-every 60  # rotate through a folder
python tools\ellora_display.py --preview p.png          # save all screens as an image
```

Requires `pip install hidapi pillow psutil pycaw winrt-runtime winrt-Windows.Media.Control winrt-Windows.Foundation` (already installed on this PC).

GIF options:

- The screen is a tall, thin 32×128 strip, so wide GIFs come out tiny. `--rotate 90` turns them sideways and `--fill` crops them to fill the strip.
- `--threshold 128` gives a plain black-and-white cut-off instead of dithering, which suits line art and text.
- `--invert` swaps black and white.

**Close the app while using VIA.** Both use the same USB channel.

To start the app automatically at login:

```powershell
powershell -ExecutionPolicy Bypass -File tools\install_startup.ps1
```

This uses `tools\input.gif`. To change the GIF, replace that file and restart the app (or log out and back in). Any options go after `--`, e.g. `install_startup.ps1 -- --12h --fill`.

## Rebuilding

Edit the files in `firmware/keymaps/display/`, then run:

```powershell
powershell -ExecutionPolicy Bypass -File firmware\build.ps1
```

Flash space is tight: about 1.3 KB of the 28 KB is free. Mouse keys, Space Cadet and Grave Escape are turned off to make room. Your layout doesn't use them.

New PC-drawn screens need almost no firmware space. Add a layout in `screens.py` and a mode number in both `keymap.c` (`MODE_COUNT`) and `ellora_display.py`.

## How it works

The app sends custom raw HID reports over VIA's interface, which the firmware picks up in `via_command_kb()`:

- `0xE0`: asks for the current status.
- `0xE1`: sets the time and the three text lines.
- `0xE2`: carries a 30-byte chunk of a frame. One 512-byte frame takes 18 reports.
- `0xE3`: hands the screen back to the keyboard's clock.
- `0xE4`: sent by the keyboard **unprompted** when the mode changes (cycle key) or its screen turns on or off.

Every reply, and every `0xE4` message, carries three things: the current mode, whether streamed frames were already showing, and whether the screen is on.

The app only re-sends the chunks of a frame that changed. If the keyboard has fallen back to the clock, it sends the whole frame again.

To stay light, the app:

- waits for the keyboard's messages instead of polling it;
- sends nothing while the keyboard screen is asleep;
- syncs the clock once a minute;
- reads PC stats only while the Stats screen is showing;
- runs in Windows' Efficiency mode.

When idle it uses about 0.05% of the CPU.
