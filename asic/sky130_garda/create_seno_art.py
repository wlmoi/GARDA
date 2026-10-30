"""Generate an unplaced SKY130 met4 artwork study; not a signoff layout."""
from pathlib import Path
import argparse
from PIL import Image, ImageDraw, ImageFont, ImageOps
import klayout.db as db

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--image', type=Path, default=Path(__file__).with_name('seno.png'))
p.add_argument('--out', type=Path, default=Path(__file__).parent / 'artwork')
p.add_argument('--width-pixels', type=int, default=300)
p.add_argument('--height-pixels', type=int, default=540)
p.add_argument('--pixel-um', type=float, default=1.0)
a = p.parse_args()
if a.width_pixels < 100 or a.height_pixels < 150 or a.pixel_um <= 0:
    p.error('Use positive dimensions and at least 100 x 150 pixels')
im = Image.open(a.image).convert('RGBA')
bbox = im.getchannel('A').getbbox()
if bbox is None: p.error('Image is fully transparent')
im = im.crop(bbox)
im.thumbnail((a.width_pixels - 12, a.height_pixels - 64), Image.Resampling.LANCZOS)
canvas = Image.new('RGB', (a.width_pixels, a.height_pixels), 'black')
canvas.paste(im, ((a.width_pixels - im.width)//2, 6), im)
draw = ImageDraw.Draw(canvas)
try:
    font = ImageFont.truetype('arialbd.ttf', max(15, a.width_pixels//7))
except OSError:
    font = ImageFont.load_default(size=max(15, a.width_pixels//7))
draw.text((a.width_pixels//2, a.height_pixels-28), 'GARDA', font=font, fill='white', anchor='mm')
mono = ImageOps.grayscale(canvas).convert('1', dither=Image.Dither.FLOYDSTEINBERG)
a.out.mkdir(parents=True, exist_ok=True)
mono.resize((a.width_pixels*3,a.height_pixels*3),Image.Resampling.NEAREST).save(a.out/'preview.png')
ly=db.Layout(); ly.dbu=0.001; cell=ly.create_cell('GARDA_SENO_ART'); layer=ly.layer(71,20)
step=round(a.pixel_um/ly.dbu)
if step <= 0: p.error('Pixel smaller than GDS grid')
pix=mono.load()
for y in range(a.height_pixels):
    x=0
    while x<a.width_pixels:
        if not pix[x,y]: x+=1; continue
        start=x
        while x<a.width_pixels and pix[x,y]: x+=1
        cell.shapes(layer).insert(db.Box(start*step,(a.height_pixels-1-y)*step,x*step,(a.height_pixels-y)*step))
ly.write(str(a.out/'garda_seno_study.gds'))
print(f'Unplaced study: {a.width_pixels*step*ly.dbu:g} x {a.height_pixels*step*ly.dbu:g} um, SKY130 met4 drawing 71/20. No DRC, LVS, power or placement validation.')
