# Ellora65 OLED: live clock + GIFs

Custom VIA firmware for the Kikos Lab Ellora65 plus a small PC app that drives the OLED.

**Fn + \\** cycles the screen between:

- **Clock**: big hour/minute digits, a seconds bar, the weekday/date (and AM/PM in 12h mode), with Luna the pet underneath.
- **GIF**: any GIF, streamed full-screen from the PC. If the app isn't running, it falls back to the clock screen.

The mode you pick is remembered after unplugging. The screen turns off after 5 minutes without typing (`OLED_TIMEOUT` in `firmware/keymaps/display/config.h`).

The keyboard has no clock of its own. The app sets the time, and the keyboard keeps counting if the app closes. Until the app has connected once, the clock shows `--:--`.

## Files

| Path | What |
|---|---|
| `kikoslab_ellora65_display.hex` | Firmware to flash |
| `kikoslab_ellora65_via.hex` | Your original stock VIA firmware (to go back) |
| `firmware/keymaps/display/` | Firmware source (QMK keymap) |
| `firmware/build.ps1` | Rebuilds the .hex with QMK MSYS |
| `tools/ellora_display.py` | PC app: clock sync + GIF streaming |
| `tools/install_startup.ps1` | Run the PC app hidden at login |
| `tools/layout_to_keymap.py` | Turns a VIA layout export into `LAYOUT_all(...)` code |

## 1. Flash

1. Open QMK Toolbox, select `kikoslab_ellora65_display.hex`, and tick *Auto-Flash*.
2. Unplug the keyboard, hold **Esc**, and plug it back in. It enters the bootloader and flashes.

VIA wipes its saved keymap when new firmware is flashed. Your current layers are compiled into this firmware, so the keys stay the same, but **macros are not**. In VIA, go to *Save + Load* → *Load* and choose `ellora65.layout.json` to restore them. After loading, Fn + \\ still switches modes.

To go back to stock, flash `kikoslab_ellora65_via.hex` the same way.

## 2. Run the PC app

```powershell
python tools\ellora_display.py                          # clock + tools\input.gif
python tools\ellora_display.py my.gif --12h             # a different GIF, 12-hour clock
python tools\ellora_display.py C:\gifs --switch-every 60  # rotate through a folder
python tools\ellora_display.py my.gif --preview p.png   # see how it will look first
```

Requires `pip install hidapi pillow` (already installed on this PC).

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

## How it works

The app sends custom raw HID reports over VIA's interface, which the firmware picks up in `via_command_kb()`:

- `0xE0`: asks for the current status.
- `0xE1`: sets the time and the three text lines.
- `0xE2`: carries a 30-byte chunk of a frame. One 512-byte frame takes 18 reports.

Every reply carries the current mode. That's how the app knows when to start or stop streaming.
