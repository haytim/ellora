/*
Copyright 2021 Kiko <kikosdesignlab@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

/*
 * Ellora65 VIA keymap with a host-driven OLED display.
 *
 * The OLED (128x32, rotated to a 32x128 portrait strip) has two modes,
 * cycled with Fn + \ :
 *   CLOCK - big HH/MM digits, a seconds bar, three text lines from the host
 *           and Luna the keyboard pet underneath.
 *   GIF   - full-screen 1-bit frames streamed from the host app.
 *           Falls back to the clock screen when no frames arrive.
 *
 * The host app (tools/ellora_display.py) talks to the keyboard over VIA's
 * raw HID interface using the command IDs below, which VIA does not use.
 */

#include QMK_KEYBOARD_H
#include <string.h>
#include "raw_hid.h"

enum custom_keycodes {
    DISP_MODE = QK_USER_0, // shows as "Custom 0" / USER00 in VIA
};

// clang-format off
const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {
  [0] = LAYOUT_all(
    KC_MPLY , KC_ESC  , KC_1    , KC_2    , KC_3    , KC_4    , KC_5    , KC_6    , KC_7    , KC_8    , KC_9    , KC_0    , KC_MINS , KC_EQL  , KC_BSPC , KC_BSPC,
    KC_9    , KC_TAB  , KC_Q    , KC_W    , KC_E    , KC_R    , KC_T    , KC_Y    , KC_U    , KC_I    , KC_O    , KC_P    , KC_LBRC , KC_RBRC , KC_BSLS,
    KC_8    , KC_CAPS , KC_A    , KC_S    , KC_D    , KC_F    , KC_G    , KC_H    , KC_J    , KC_K    , KC_L    , KC_SCLN , KC_QUOT , KC_ENT  , KC_ENT  , KC_DEL,
    KC_7    , KC_LSFT , KC_LSFT , KC_Z    , KC_X    , KC_C    , KC_V    , KC_B    , KC_N    , KC_M    , KC_COMM , KC_DOT  , KC_SLSH , KC_RSFT , KC_UP   , QK_MACRO_0,
    MO(1)   , KC_LCTL , KC_LGUI , KC_LALT , MO(1)   , KC_SPC  , MO(1)   , MO(1)   , MO(1)   , KC_LEFT , KC_DOWN , KC_RGHT
  ),

  [1] = LAYOUT_all(
    KC_MPLY , KC_GRV  , KC_F1   , KC_F2   , KC_F3   , KC_F4   , KC_F5   , KC_F6   , KC_F7   , KC_F8   , KC_F9   , KC_F10  , KC_F11  , KC_F12  , KC_BSPC , KC_TRNS,
    KC_6    , KC_BSPC , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , DISP_MODE,
    KC_5    , KC_ENT  , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_PGDN , KC_TRNS , KC_TRNS , KC_BSPC,
    KC_4    , MO(2)   , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , QK_MACRO_1,
    KC_F20  , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS
  ),

  [2] = LAYOUT_all(
    KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , QK_MACRO_0, KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_BSPC , KC_TRNS,
    KC_3    , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS,
    KC_2    , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS,
    KC_1    , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , MAGIC_TOGGLE_NKRO, KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS,
    KC_F20  , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS
  ),

  [3] = LAYOUT_all(
    KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_BSPC , KC_TRNS,
    KC_F17  , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS,
    KC_F18  , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS,
    KC_F19  , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS,
    KC_F20  , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS , KC_TRNS
  )
};
// clang-format on

bool encoder_update_user(uint8_t index, bool clockwise) {
    if (clockwise) {
        tap_code(KC_VOLU);
    } else {
        tap_code(KC_VOLD);
    }

    return false;
}

#ifdef OLED_ENABLE

#    include "luna_sprites.h"

/* DISPLAY STATE START */

enum display_mode { MODE_CLOCK, MODE_GIF, MODE_COUNT };

// Raw HID commands from the host app. Every reply is [cmd, display_mode].
enum host_command {
    HOST_STATUS    = 0xE0, // [cmd]
    HOST_SET_TIME  = 0xE1, // [cmd, hour, min, sec, flags, 3 x 5 chars of text]
    HOST_GIF_CHUNK = 0xE2, // [cmd, chunk, 30 bytes of the 512 byte frame]
};

#    define TIME_FLAG_12H 0x01
#    define GIF_CHUNK_BYTES 30
#    define GIF_STALE_MS 1500
#    define TEXT_LINES 3
#    define TEXT_CHARS 5

static uint8_t  display_mode;
static bool     redraw_screen = true;
static bool     gif_live      = false;
static uint32_t gif_timer;

static bool     time_synced = false;
static uint8_t  time_flags;
static uint32_t time_base_secs; // seconds since midnight when time_timer was taken
static uint32_t time_timer;
static uint32_t shown_secs = UINT32_MAX;
static char     time_text[TEXT_LINES][TEXT_CHARS + 1];

static void cycle_display_mode(void) {
    display_mode = (display_mode + 1) % MODE_COUNT;
    eeconfig_update_user(display_mode);
    redraw_screen = true;
}

void keyboard_post_init_user(void) {
    display_mode = eeconfig_read_user() % MODE_COUNT;
}

void eeconfig_init_user(void) {
    eeconfig_update_user(MODE_CLOCK);
}

bool via_command_kb(uint8_t *data, uint8_t length) {
    switch (data[0]) {
        case HOST_STATUS:
            break;

        case HOST_SET_TIME:
            time_base_secs = data[1] * 3600UL + data[2] * 60UL + data[3];
            time_timer     = timer_read32();
            time_flags     = data[4];
            for (uint8_t line = 0; line < TEXT_LINES; line++) {
                memcpy(time_text[line], &data[5 + line * TEXT_CHARS], TEXT_CHARS);
            }
            time_synced = true;
            shown_secs  = UINT32_MAX; // force a clock redraw
            break;

        case HOST_GIF_CHUNK:
            // Writing to the buffer while the screen is asleep would wake it.
            if (display_mode == MODE_GIF && is_oled_on()) {
                if (!gif_live) {
                    gif_live = true;
                    oled_clear();
                }
                uint16_t index = data[1] * GIF_CHUNK_BYTES;
                for (uint8_t i = 0; i < GIF_CHUNK_BYTES && index < OLED_MATRIX_SIZE; i++, index++) {
                    oled_write_raw_byte(data[2 + i], index);
                }
                gif_timer = timer_read32();
            }
            break;

        default:
            return false; // let VIA handle it
    }

    data[1] = display_mode;
    raw_hid_send(data, length);
    return true;
}

/* DISPLAY STATE END */

/* CLOCK START */

// Digits 0-9 from QMK's 5x7 OLED font, one byte per column, LSB at the top.
static const uint8_t PROGMEM clock_digits[10][5] = {
    {0x3E, 0x51, 0x49, 0x45, 0x3E}, {0x00, 0x42, 0x7F, 0x40, 0x00}, {0x72, 0x49, 0x49, 0x49, 0x46}, {0x21, 0x41, 0x49, 0x4D, 0x33}, {0x18, 0x14, 0x12, 0x7F, 0x10},
    {0x27, 0x45, 0x45, 0x45, 0x39}, {0x3C, 0x4A, 0x49, 0x49, 0x31}, {0x41, 0x21, 0x11, 0x09, 0x07}, {0x36, 0x49, 0x49, 0x49, 0x36}, {0x46, 0x49, 0x49, 0x29, 0x1E},
};

#    define DIGIT_SCALE 3
#    define DIGIT_BLANK 10
#    define HOURS_Y 2
#    define MINUTES_Y 26
#    define SECONDS_BAR_Y 50
#    define TEXT_FIRST_LINE 7

static void fill_block(uint8_t x, uint8_t y, bool on) {
    for (uint8_t dx = 0; dx < DIGIT_SCALE; dx++) {
        for (uint8_t dy = 0; dy < DIGIT_SCALE; dy++) {
            oled_write_pixel(x + dx, y + dy, on);
        }
    }
}

static void draw_big_digit(uint8_t x, uint8_t y, uint8_t digit) {
    for (uint8_t col = 0; col < 5; col++) {
        uint8_t bits = digit < 10 ? pgm_read_byte(&clock_digits[digit][col]) : 0;
        for (uint8_t row = 0; row < 7; row++) {
            fill_block(x + col * DIGIT_SCALE, y + row * DIGIT_SCALE, bits & (1 << row));
        }
    }
}

// Draws a two-digit number as one row of big digits; value > 99 draws "--".
static void draw_big_number(uint8_t y, uint8_t value, bool blank_leading_zero) {
    if (value > 99) {
        for (uint8_t x = 0; x < 32; x++) {
            for (uint8_t dy = 0; dy < 7 * DIGIT_SCALE; dy++) {
                oled_write_pixel(x, y + dy, x != 15 && x != 16 && dy >= 9 && dy < 12);
            }
        }
        return;
    }
    draw_big_digit(0, y, (blank_leading_zero && value < 10) ? DIGIT_BLANK : value / 10);
    draw_big_digit(17, y, value % 10);
}

static void render_clock(void) {
    uint32_t secs = 0;
    if (time_synced) {
        secs = (time_base_secs + timer_elapsed32(time_timer) / 1000) % 86400UL;
    }
    if (secs == shown_secs) {
        return;
    }
    shown_secs = secs;

    if (!time_synced) {
        draw_big_number(HOURS_Y, 0xFF, false);
        draw_big_number(MINUTES_Y, 0xFF, false);
        oled_set_cursor(0, TEXT_FIRST_LINE + 1);
        oled_write_P(PSTR("no  \nsync "), false);
        return;
    }

    uint8_t hours = secs / 3600;
    bool    is_12h = time_flags & TIME_FLAG_12H;
    if (is_12h) {
        hours = hours % 12 ? hours % 12 : 12;
    }
    draw_big_number(HOURS_Y, hours, is_12h);
    draw_big_number(MINUTES_Y, (secs / 60) % 60, false);

    // Seconds progress bar, 2px tall across the full width.
    uint8_t bar_width = (secs % 60 + 1) * 32 / 60;
    for (uint8_t x = 0; x < 32; x++) {
        oled_write_pixel(x, SECONDS_BAR_Y, x < bar_width);
        oled_write_pixel(x, SECONDS_BAR_Y + 1, x < bar_width);
    }

    for (uint8_t line = 0; line < TEXT_LINES; line++) {
        oled_set_cursor(0, TEXT_FIRST_LINE + line);
        oled_write(time_text[line], false);
    }
}

/* CLOCK END */

oled_rotation_t oled_init_user(oled_rotation_t rotation) {
    return OLED_ROTATION_90;
}

/* KEYBOARD PET START */

/* settings */
#    define MIN_WALK_SPEED 10
#    define MIN_RUN_SPEED 40

/* advanced settings */
#    define ANIM_FRAME_DURATION 200 // how long each frame lasts in ms

/* timers */
uint32_t anim_timer = 0;

/* current frame */
uint8_t current_frame = 0;

/* status variables */
int   current_wpm = 0;
led_t led_usb_state;

bool isSneaking = false;
bool isJumping  = false;
bool showedJump = true;

/* logic */
static void render_luna(int LUNA_X, int LUNA_Y) {
    /* animation */
    void animate_luna(void) {
        /* jump */
        if (isJumping || !showedJump) {
            /* clear */
            oled_set_cursor(LUNA_X, LUNA_Y + 2);
            oled_write("     ", false);

            oled_set_cursor(LUNA_X, LUNA_Y - 1);

            showedJump = true;
        } else {
            /* clear */
            oled_set_cursor(LUNA_X, LUNA_Y - 1);
            oled_write("     ", false);

            oled_set_cursor(LUNA_X, LUNA_Y);
        }

        /* switch frame */
        current_frame = (current_frame + 1) % 2;

        /* current status */
        if (led_usb_state.caps_lock) {
            oled_write_raw_P(bark[current_frame], LUNA_ANIM_SIZE);

        } else if (isSneaking) {
            oled_write_raw_P(sneak[current_frame], LUNA_ANIM_SIZE);

        } else if (current_wpm <= MIN_WALK_SPEED) {
            oled_write_raw_P(sit[current_frame], LUNA_ANIM_SIZE);

        } else if (current_wpm <= MIN_RUN_SPEED) {
            oled_write_raw_P(walk[current_frame], LUNA_ANIM_SIZE);

        } else {
            oled_write_raw_P(run[current_frame], LUNA_ANIM_SIZE);
        }
    }

    /* animation timer */
    if (timer_elapsed32(anim_timer) > ANIM_FRAME_DURATION) {
        anim_timer = timer_read32();
        animate_luna();
    }
}

/* KEYBOARD PET END */

bool oled_task_user(void) {
    /* KEYBOARD PET VARIABLES START */

    current_wpm   = get_current_wpm();
    led_usb_state = host_keyboard_led_state();

    /* KEYBOARD PET VARIABLES END */

#    if OLED_TIMEOUT > 0
    /* constant redraws prevent the normal timeout from occuring */
    if (last_input_activity_elapsed() > OLED_TIMEOUT && last_led_activity_elapsed() > OLED_TIMEOUT) {
        if (is_oled_on()) {
            oled_off();
        }
        redraw_screen = true;
        return false;
    }
#    endif

    if (display_mode == MODE_GIF && gif_live && timer_elapsed32(gif_timer) > GIF_STALE_MS) {
        gif_live      = false;
        redraw_screen = true;
    }
    if (redraw_screen) {
        redraw_screen = false;
        gif_live      = false;
        shown_secs    = UINT32_MAX;
        oled_clear();
    }
    if (gif_live) {
        return false; // frames arrive in via_command_kb()
    }

    render_clock();
    render_luna(0, 13);
    return false;
}

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    switch (keycode) {
        case DISP_MODE:
            if (record->event.pressed) {
                cycle_display_mode();
            }
            return false;

        case KC_BSLS:
            // Fn + \ also cycles when layer 1 has KC_TRNS there, e.g. after
            // loading an older layout into VIA.
            if (IS_LAYER_ON(1)) {
                if (record->event.pressed) {
                    cycle_display_mode();
                }
                return false;
            }
            break;

            /* KEYBOARD PET STATUS START */

        case KC_LCTL:
        case KC_RCTL:
            if (record->event.pressed) {
                isSneaking = true;
            } else {
                isSneaking = false;
            }
            break;
        case KC_SPC:
            if (record->event.pressed) {
                isJumping  = true;
                showedJump = false;
            } else {
                isJumping = false;
            }
            break;

            /* KEYBOARD PET STATUS END */
    }
    return true;
}

#endif
