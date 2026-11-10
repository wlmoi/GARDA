#!/usr/bin/env python3
"""Build the assets of the GARDA GDSII Silicon Explorer (site/GDSII/) from the
real layout: per-layer renders of the final GDS, a composite overview, a
magnified chip-art inset, and layout.json with every number the page shows.

    python tools/gdsii_site.py [--def local_build/def/tt_um_garda_chip.def]

Inputs (all from the hardened build): local_build/gds/<top>.gds,
local_build/lef/<top>.lef, local_build/metrics.json, macros/CALVIN_UP/art.json,
and optionally the DEF (ignored by git; when given, the placement extents of the
named registers of each RTL block are recomputed, otherwise the previous
layout.json values are kept).  Needs: pip install klayout pillow numpy.
"""
import argparse, json, os, re, sys
import numpy as np
from PIL import Image
import klayout.db as kdb
import klayout.lay as lay

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(ROOT, 'site', 'GDSII', 'assets')

# IHP SG13CMOS5L GDS layers present in the tile, grouped the way the page toggles them.
GROUPS = [
    ('feol',   'Active + poly (transistors)', [(1, 0), (5, 0), (31, 0), (14, 0)], '#3E4C8A'),
    ('metal1', 'Metal1 (cell wiring, rails)',  [(8, 0)],                            '#315CFF'),
    ('metal2', 'Metal2 (horizontal routing)',  [(10, 0)],                           '#28B5E8'),
    ('metal3', 'Metal3 (vertical routing)',    [(30, 0)],                           '#9D7BFF'),
    ('metal4', 'Metal4 (power grid + chip art)', [(50, 0)],                         '#B7FF35'),
    ('vias',   'Contacts and vias',             [(6, 0), (19, 0), (29, 0), (49, 0)], '#F7F9FF'),
]


def view(gds):
    lv = lay.LayoutView()
    lv.set_config('full-hierarchy-new-cell', 'true')
    lv.set_config('background-color', '#000000')
    lv.set_config('grid-visible', 'false')
    lv.set_config('text-visible', 'false')
    lv.set_config('cell-box-visible', 'false') if hasattr(lv, 'set_config') else None
    lv.load_layout(gds, True)
    lv.max_hierarchy_levels = 99
    return lv


def style(lv, layers, color):
    """Only `layers` visible, solid fill in `color` (an exact layer/datatype match)."""
    lv.clear_layers()
    for (l, d) in layers:
        p = lay.LayerPropertiesNode()
        p.source = f'{l}/{d}@1'
        c = int(color.lstrip('#'), 16)
        p.fill_color = c; p.frame_color = c
        p.dither_pattern = 0          # solid
        p.width = 0
        p.visible = True
        lv.insert_layer(lv.end_layers(), p)
    lv.max_hierarchy_levels = 99


def save(lv, path, w, h, box):
    tmp = path + '.png'
    lv.save_image_with_options(tmp, w, h, 0, 2, 0, box, False)   # oversampling 2
    return tmp


def to_webp(png, out, quality=82):
    im = Image.open(png).convert('RGB')
    im.save(out, 'WEBP', quality=quality, method=6)
    os.remove(png)
    return os.path.getsize(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--def', dest='deff', default=None)
    ap.add_argument('--width', type=int, default=2400)
    a = ap.parse_args()

    manifest = json.load(open(os.path.join(ROOT, 'agent_manifest.json')))
    top = manifest['top_module']
    gds = os.path.join(ROOT, manifest['gds'])
    os.makedirs(OUT, exist_ok=True)
    prev = {}
    pj = os.path.join(OUT, 'layout.json')
    if os.path.exists(pj):
        prev = json.load(open(pj))

    ly = kdb.Layout(); ly.read(gds)
    tc = ly.top_cell(); dbu = ly.dbu
    die = tc.dbbox()
    W = a.width; H = int(round(W * die.height() / die.width()))
    box = kdb.DBox(die.left, die.bottom, die.right, die.top)

    # ---- per-layer renders + composite
    lv = view(gds)
    layers_out = []
    stack = np.zeros((H, W, 3), np.float32)
    for key, label, lds, color in GROUPS:
        present = [ld for ld in lds if ly.find_layer(*ld) is not None]
        if not present:
            continue
        style(lv, present, color)
        png = save(lv, os.path.join(OUT, f'layer-{key}'), W, H, box)
        arr = np.asarray(Image.open(png).convert('RGB')).astype(np.float32) / 255
        weight = {'feol': .30, 'metal1': .30, 'metal2': .34, 'metal3': .38, 'metal4': .80, 'vias': .16}[key]
        stack = 1 - (1 - stack) * (1 - arr * weight)   # screen blend, Metal4 (power grid + art) brightest
        size = to_webp(png, os.path.join(OUT, f'layer-{key}.webp'), 74)
        shapes = sum(kdb.Region(tc.begin_shapes_rec(ly.find_layer(*ld))).count() for ld in present)
        layers_out.append({'id': key, 'label': label, 'gds_layers': [f'{l}/{d}' for l, d in present], 'color': color,
                           'image': f'assets/layer-{key}.webp', 'bytes': size, 'shapes': shapes})
        print(f'layer {key:7s} {present} -> {size // 1024} KB, {shapes} shapes')
    comp = Image.fromarray((np.clip(stack, 0, 1) * 255).astype(np.uint8))
    comp.save(os.path.join(OUT, 'overview.webp'), 'WEBP', quality=82, method=6)
    comp.resize((1600, int(round(1600 * H / W))), Image.LANCZOS).save(os.path.join(OUT, 'overview-1600.webp'), 'WEBP', quality=80, method=6)
    comp.resize((1600, int(round(1600 * H / W))), Image.LANCZOS).save(os.path.join(OUT, 'overview-1600.jpg'), 'JPEG', quality=84, optimize=True)

    # ---- chip art inset (Metal4 only, magnified)
    art = json.load(open(os.path.join(ROOT, 'macros', 'CALVIN_UP', 'art.json')))
    x0, y0, x1, y1 = art['box']
    pad = 6.0
    abox = kdb.DBox(x0 - pad, y0 - pad, x1 + pad, y1 + pad)
    style(lv, [(50, 0)], '#B7FF35')
    aw = 900; ah = int(round(aw * abox.height() / abox.width()))
    png = save(lv, os.path.join(OUT, 'chip-art'), aw, ah, abox)
    to_webp(png, os.path.join(OUT, 'chip-art.webp'), 88)

    # ---- macros, straight from the GDS instances
    friendly = {
        'RM_IHPSG13_1P_512x32_c2_bm_bist': ('sram', 'IHP SRAM 512x32 (PRISM packet FIFO)'),
        'CFGMEM_IHP_LEFT16': ('cfgmem', 'CFGMEM bank A (latch array, pins east)'),
        'CFGMEM_IHP_LEFT16_SRAM': ('cfgmem', 'CFGMEM, left column with SRAM-side pins'),
        'CFGMEM_IHP16': ('cfgmem', 'CFGMEM bank B (latch array, pins west)'),
        'tt_um_pettit_calvin': ('art', 'Chip art: SENO pose, Metal4 on bare oxide'),
    }
    macros = []
    for inst in tc.each_inst():
        c = ly.cell(inst.cell_index)
        if c.name in friendly:
            b = inst.dbbox()
            kind, label = friendly[c.name]
            macros.append({'cell': c.name, 'kind': kind, 'label': label, 'orient': str(inst.trans).split(' ')[0],
                           'x0': round(b.left, 2), 'y0': round(b.bottom, 2), 'x1': round(b.right, 2), 'y1': round(b.top, 2)})
    macros.sort(key=lambda m: (m['kind'], m['x0'], m['y0']))

    # ---- metal usage (area fraction of the die), straight from the GDS
    usage = {}
    for name, ld in (('Metal1', (8, 0)), ('Metal2', (10, 0)), ('Metal3', (30, 0)), ('Metal4', (50, 0))):
        r = kdb.Region(tc.begin_shapes_rec(ly.find_layer(*ld))); r.merge()
        usage[name] = round(100 * r.area() * dbu * dbu / (die.width() * die.height()), 1)
    print('metal area fraction %', usage)

    # ---- RTL blocks: placement extents of their named registers (DEF)
    blocks = prev.get('blocks', [])
    if a.deff:
        groups = {'prism_shards': ('PRISM state-machine shards', r'^i_peripherals\.i_prism\.SH'),
                  'prism_sram': ('PRISM SRAM FIFO wrappers', r'^i_peripherals\.i_prism\.SRAM'),
                  'tinyqv': ('TinyQV RISC-V CPU and QSPI memory controller', r'^i_tinyqv\.'),
                  'cfgmem_if': ('CFGMEM write/read interface', r'^i_peripherals\.i_cfgmem\.'),
                  'uart': ('UART peripheral', r'^i_peripherals\.i_uart\.'),
                  'dma': ('PRISM DMA engines', r'^i_(t?x?dma)\.|^i_dma\.|^i_txdma\.')}
        pts = {k: [] for k in groups}
        # a COMPONENTS entry runs from "- name cell" to ";" and may span lines
        rx = re.compile(r'^-\s+(\S+)\s+(\S+).*?(?:PLACED|FIXED)\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)', re.S)
        unit = 1000.0
        text = open(a.deff).read()
        mu = re.search(r'UNITS DISTANCE MICRONS\s+(\d+)', text)
        if mu:
            unit = float(mu.group(1))
        comps = text[text.find('\nCOMPONENTS'):text.find('\nEND COMPONENTS')]
        for entry in comps.split(';'):
            m = rx.match(entry.strip())
            if not m:
                continue
            name = m.group(1).replace('\\', '')
            for k, (_, pat) in groups.items():
                if re.match(pat, name):
                    pts[k].append((int(m.group(3)) / unit, int(m.group(4)) / unit)); break
        # most cells carry generated names after synthesis, but nets keep their
        # RTL hierarchy: the routed points of a block's named nets show where
        # that block's wiring actually lies
        nets = text[text.find('\nNETS'):text.find('\nEND NETS')]
        pt = re.compile(r'\(\s*(-?\d+)\s+(-?\d+)')
        for entry in nets.split(';'):
            e = entry.strip()
            if not e.startswith('- '):
                continue
            name = e[2:].split(None, 1)[0].replace('\\', '')
            for k, (_, pat) in groups.items():
                if re.match(pat, name):
                    r = e.find('ROUTED')
                    if r >= 0:
                        for x, y in pt.findall(e[r:])[::3]:
                            pts[k].append((int(x) / unit, int(y) / unit))
                    break
        blocks = []
        colors = {'prism_shards': (183, 255, 53), 'prism_sram': (255, 196, 61), 'tinyqv': (49, 92, 255),
                  'cfgmem_if': (40, 181, 232), 'uart': (255, 110, 199), 'dma': (157, 123, 255)}
        bin_um = 10.0
        nx, ny = int(np.ceil(die.width() / bin_um)), int(np.ceil(die.height() / bin_um))
        for k, (label, _) in groups.items():
            p = np.array(pts[k])
            if len(p) < 50:
                continue
            hist, _, _ = np.histogram2d(p[:, 1], p[:, 0], bins=[ny, nx], range=[[0, die.height()], [0, die.width()]])
            s = hist.copy()
            for _ in range(4):                     # box blur: a smooth density, not a scatter
                q = np.pad(s, 1, mode='edge')
                s = sum(q[1 + dy:1 + dy + ny, 1 + dx:1 + dx + nx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)) / 9
            d = s / s.max()
            alpha = np.where(d > 0.12, np.clip(d, 0, 1) ** 0.6 * 230, 0).astype(np.uint8)
            rgba = np.zeros((ny, nx, 4), np.uint8); rgba[..., :3] = colors[k]; rgba[..., 3] = alpha
            Image.fromarray(rgba[::-1]).save(os.path.join(OUT, f'block-{k}.png'), optimize=True)
            py, px = np.unravel_index(np.argmax(s), s.shape)
            # the area holding the densest half of the block's wiring
            core = d > 0.35
            ys, xs = np.where(core)
            blocks.append({'id': k, 'label': label, 'samples': int(len(p)), 'color': '#%02X%02X%02X' % colors[k],
                           'heat': f'assets/block-{k}.png', 'peak_um': [round((px + .5) * bin_um, 1), round((py + .5) * bin_um, 1)],
                           'core_um': [round(xs.min() * bin_um, 1), round(ys.min() * bin_um, 1), round((xs.max() + 1) * bin_um, 1), round((ys.max() + 1) * bin_um, 1)]})
        print('blocks', [(b['id'], b['samples'], b['peak_um'], b['core_um']) for b in blocks])

    # ---- evidence from the hardened run
    m = json.load(open(os.path.join(ROOT, 'local_build', 'metrics.json')))
    g = lambda k: m.get(k)
    lef = open(os.path.join(ROOT, manifest['lef'])).read()
    size = re.search(r'SIZE\s+([\d.]+)\s+BY\s+([\d.]+)', lef)
    info = {
        'design': manifest['name'], 'top_module': top, 'pdk': 'IHP SG13CMOS5L (130 nm CMOS, 5-layer stack: Metal1-Metal4 used by the tile)',
        'tile': manifest['tile'], 'die_um': [float(size.group(1)), float(size.group(2))],
        'gds_db_unit_um': round(dbu, 6), 'gds_cells': ly.cells(), 'gds_bytes': os.path.getsize(gds),
        'top_cell_children': tc.child_instances(),
        'metal_area_pct': usage,
        'evidence': {
            'instances_total': g('design__instance__count'), 'stdcells': g('design__instance__count__stdcell'),
            'macros': g('design__instance__count__macros'), 'sequential_cells': g('design__instance__count__class:sequential_cell'),
            'utilization_pct': round(100 * g('design__instance__utilization'), 1), 'stdcell_utilization_pct': round(100 * g('design__instance__utilization__stdcell'), 1),
            'route_drc_errors': g('route__drc_errors'), 'klayout_drc_errors': g('klayout__drc_error__count'),
            'lvs_errors': g('design__lvs_error__count'), 'antenna_violating_nets': g('antenna__violating__nets'),
            'wirelength_um': g('route__wirelength'), 'setup_ws_typ_ns': round(g('timing__setup__ws__corner:nom_typ_1p20V_25C'), 3),
            'setup_ws_slow_ns': round(g('timing__setup__ws__corner:nom_slow_1p08V_125C'), 3), 'setup_ws_fast_ns': round(g('timing__setup__ws__corner:nom_fast_1p32V_m40C'), 3),
            'hold_ws_ns': round(g('timing__hold__ws'), 3), 'max_slew_violations': g('design__max_slew_violation__count'),
            'max_cap_violations': g('design__max_cap_violation__count'), 'max_fanout_violations': g('design__max_fanout_violation__count'),
            'ir_drop_worst_mv': round(1000 * g('ir__drop__worst'), 3), 'power_total_mw': round(1000 * g('power__total'), 2),
            'magic_illegal_overlap': g('magic__illegal_overlap__count'),
        },
        'chip_art': {'image': 'Calvin.png (SENO pose)', 'box_um': art['box'], 'size_um': [round(x1 - x0, 1), round(y1 - y0, 1)],
                     'metal_area_um2': art['metal_area_um2'], 'rectangles': art['rectangles'], 'layer': 'Metal4 50/0 on bare oxide (rows cut, all-layer nofill)'},
        'macros': macros, 'blocks': blocks, 'layers': layers_out,
        'images': {'overview': 'assets/overview.webp', 'overview_small': 'assets/overview-1600.webp', 'overview_jpg': 'assets/overview-1600.jpg',
                   'chip_art': 'assets/chip-art.webp', 'chip_art_box_um': [abox.left, abox.bottom, abox.right, abox.top], 'size_px': [W, H]},
    }
    json.dump(info, open(pj, 'w'), indent=1)
    print('wrote', pj)


if __name__ == '__main__':
    main()
