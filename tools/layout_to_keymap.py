"""Convert a VIA layout export into LAYOUT_all(...) blocks for keymap.c.

VIA exports keys in matrix order (row-major); LAYOUT_all takes them in the
physical order listed in the keyboard's info.json.
"""
import json
import sys

via_path, info_path = sys.argv[1], sys.argv[2]
via = json.load(open(via_path))
info = json.load(open(info_path))
cols = len(info["matrix_pins"]["cols"])
order = [k["matrix"] for k in info["layouts"]["LAYOUT_all"]["layout"]]
rows_y = sorted({int(k["y"]) for k in info["layouts"]["LAYOUT_all"]["layout"]})

def qmk_name(kc):
    if kc.startswith("MACRO("):
        return "QK_MACRO_" + kc[6:-1]
    return kc

for n, layer in enumerate(via["layers"]):
    keys = [qmk_name(layer[r * cols + c]) for r, c in order]
    ys = [int(k["y"]) for k in info["layouts"]["LAYOUT_all"]["layout"]]
    lines, cur, last = [], [], ys[0]
    for kc, y in zip(keys, ys):
        if y != last:
            lines.append(cur); cur = []; last = y
        cur.append(kc)
    lines.append(cur)
    body = ",\n".join("    " + ", ".join(f"{k:<8}" for k in l).rstrip() for l in lines)
    print(f"  [{n}] = LAYOUT_all(\n{body}\n  ),\n")
