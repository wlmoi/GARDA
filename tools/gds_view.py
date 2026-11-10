#!/usr/bin/env python3
"""GARDA-chip GDS helper for humans and agents.  Pure Python (+numpy/matplotlib for render).

  python tools/gds_view.py info   [file.gds]            # JSON: cells, layers, units, top-cell bbox
  python tools/gds_view.py render [file.gds] -o out.png # PNG overview (KLayout if installed, else matplotlib)

Default file: local_build/gds/tt_um_garda_chip.gds
"""
import argparse, json, os, shutil, struct, subprocess, sys
from collections import Counter

DEFAULT = os.path.join(os.path.dirname(__file__), "..", "local_build", "gds", "tt_um_garda_chip.gds")

def _real(b):  # GDSII 8-byte real
    s = -1 if b[0] & 0x80 else 1
    e = (b[0] & 0x7F) - 64
    m = int.from_bytes(b[1:8], "big") / 2**56
    return s * m * 16**e

def parse(path):
    d = open(path, "rb").read(); i = 0
    cells, cur, units, layer, lc = {}, None, None, None, Counter()
    while i < len(d):
        ln, rt = struct.unpack(">HB", d[i:i+3]); p = d[i+4:i+ln]
        if rt == 0x03: units = (_real(p[:8]), _real(p[8:16]))
        elif rt == 0x06:
            cur = {"name": p.rstrip(b"\0").decode(), "boxes": [], "refs": []}; cells[cur["name"]] = cur
        elif rt == 0x0D: layer = struct.unpack(">h", p)[0]
        elif rt in (0x0E,): pass
        elif rt == 0x10 and cur is not None:  # XY
            xy = struct.unpack(f">{len(p)//4}i", p)
            if cur.get("_pending") == "bnd":
                xs, ys = xy[0::2], xy[1::2]
                cur["boxes"].append((layer, min(xs), min(ys), max(xs), max(ys))); lc[layer] += 1
            elif cur.get("_pending") == "ref":
                cur["refs"].append((cur["_sname"], xy[0], xy[1]))
            cur["_pending"] = None
        elif rt == 0x08 and cur is not None: cur["_pending"] = "bnd"
        elif rt == 0x0A and cur is not None: cur["_pending"] = "ref"
        elif rt == 0x12 and cur is not None: cur["_sname"] = p.rstrip(b"\0").decode()
        i += ln
    return units, cells, lc

def top_cell(cells):
    ref = {r[0] for c in cells.values() for r in c["refs"]}
    tops = [n for n in cells if n not in ref]
    return tops[-1] if tops else list(cells)[-1]

def cmd_info(a):
    units, cells, lc = parse(a.gds); top = top_cell(cells); uu = units[1] / 1e-6
    bx = [b for b in cells[top]["boxes"]]
    print(json.dumps({"file": os.path.abspath(a.gds), "top_cell": top, "db_unit_um": units[1] / 1e-6,
        "cells": len(cells), "polygons_with_layer": {str(k): v for k, v in sorted(lc.items())},
        "top_direct_boundaries": len(bx), "top_children": len(cells[top]["refs"])}, indent=2))

def cmd_render(a):
    out = a.output
    k = shutil.which("klayout")
    if k:
        scr = out + ".rb.py"
        open(scr, "w").write(f"import pya\nlv=pya.LayoutView();lv.load_layout(r'{a.gds}',True);lv.max_hierarchy();lv.zoom_fit();lv.save_image(r'{out}',2400,1200)\n")
        subprocess.check_call([k, "-zz", "-r", scr]); os.remove(scr); print(out); return
    import numpy as np, matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    units, cells, lc = parse(a.gds); top = top_cell(cells); s = units[1] / 1e-6
    W, H = 2400, 1200
    bbs = {}
    for n, c in cells.items():
        if c["boxes"]:
            bbs[n] = (min(b[1] for b in c["boxes"]), min(b[2] for b in c["boxes"]),
                      max(b[3] for b in c["boxes"]), max(b[4] for b in c["boxes"]))
    rects = [(x0, y0, x1, y1) for _, x0, y0, x1, y1 in cells[top]["boxes"]]
    for n, x, y in cells[top]["refs"]:
        if n in bbs:
            b = bbs[n]; rects.append((x+b[0], y+b[1], x+b[2], y+b[3]))
    r = np.array(rects, dtype=np.int64)
    X0, Y0, X1, Y1 = r[:, 0].min(), r[:, 1].min(), r[:, 2].max(), r[:, 3].max()
    sx, sy = W / (X1 - X0), H / (Y1 - Y0); sc = min(sx, sy)
    img = np.zeros((H, W), np.float32)
    for x0, y0, x1, y1 in r:
        i0, i1 = int((x0-X0)*sc), max(int((x1-X0)*sc), int((x0-X0)*sc)+1)
        j0, j1 = int((y0-Y0)*sc), max(int((y1-Y0)*sc), int((y0-Y0)*sc)+1)
        img[j0:j1, i0:i1] += 1
    fig, ax = plt.subplots(figsize=(16, 8))
    ax.imshow(np.log1p(img), origin="lower", cmap="viridis",
              extent=(0, (X1-X0)*s, 0, (Y1-Y0)*s), aspect="equal")
    ax.set_title(f"{top} (um) - density overview")
    fig.savefig(out, dpi=150, bbox_inches="tight"); print(out)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    for n, f in (("info", cmd_info), ("render", cmd_render)):
        p = sp.add_parser(n); p.add_argument("gds", nargs="?", default=DEFAULT); p.set_defaults(fn=f)
        if n == "render": p.add_argument("-o", "--output", default="gds_render.png")
    a = ap.parse_args(); a.fn(a)
