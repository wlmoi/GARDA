"""Generate a simple editable draw.io chip diagram and matching SVG/PNG preview."""
from pathlib import Path
import html
import hashlib
import json
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/assets'
OUT.mkdir(parents=True, exist_ok=True)
mxfile = ET.Element('mxfile', host='app.diagrams.net', type='device')
diagram = ET.SubElement(mxfile, 'diagram', id='igor-core', name='IGOR Core')
model = ET.SubElement(diagram, 'mxGraphModel', dx='2400', dy='1450', grid='1',
                      gridSize='10', guides='1', tooltips='1', connect='1',
                      arrows='1', fold='1', page='1', pageScale='1',
                      pageWidth='2400', pageHeight='1450', math='0', shadow='0')
root = ET.SubElement(model, 'root')
ET.SubElement(root, 'mxCell', id='0')
ET.SubElement(root, 'mxCell', id='1', parent='0')
svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="2400" height="1450" viewBox="0 0 2400 1450">',
       '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L10,5 L0,10 Z" fill="#334155"/></marker></defs>',
       '<rect width="2400" height="1450" fill="white"/>']
boxes = {}
edge_records = []


def text_svg(x, y, label, size, color='#0f172a', bold=False):
    lines = label.split('\n')
    start = y - (len(lines)-1)*size*.66
    for i, line in enumerate(lines):
        svg.append(f'<text x="{x}" y="{start+i*size*1.32}" text-anchor="middle" dominant-baseline="middle" font-family="Arial, sans-serif" font-size="{size}" fill="{color}" font-weight="{700 if bold else 400}">{html.escape(line)}</text>')


def box(key, x, y, w, h, label='', fill='#ffffff', stroke='#334155', size=18,
        bold=False, text='#0f172a', radius=16, width=2):
    boxes[key] = (x,y,w,h)
    style = (f'rounded={int(radius>0)};whiteSpace=wrap;html=0;arcSize=12;'
             f'fillColor={fill};strokeColor={stroke};strokeWidth={width};'
             f'fontFamily=Arial;fontSize={size};fontColor={text};fontStyle={int(bold)};'
             'align=center;verticalAlign=middle;spacing=8;')
    cell = ET.SubElement(root, 'mxCell', id=key, value=label, style=style, vertex='1', parent='1')
    ET.SubElement(cell, 'mxGeometry', x=str(x), y=str(y), width=str(w), height=str(h), **{'as':'geometry'})
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')
    if label:
        text_svg(x+w/2,y+h/2,label,size,text,bold)


def label(key,x,y,w,h,value,size=18,color='#475569',bold=False):
    cell=ET.SubElement(root,'mxCell',id=key,value=value,vertex='1',parent='1',
        style=f'text;html=0;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;fontFamily=Arial;fontSize={size};fontColor={color};fontStyle={int(bold)};whiteSpace=wrap;')
    ET.SubElement(cell,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),**{'as':'geometry'})
    text_svg(x+w/2,y+h/2,value,size,color,bold)


def edge(key,source,target,points,exit_xy,entry_xy,caption,label_center,dashed=False,size=16):
    style = (f'edgeStyle=orthogonalEdgeStyle;rounded=0;html=0;endArrow=block;endFill=1;strokeColor=#334155;strokeWidth=2.5;'
             f'exitX={exit_xy[0]};exitY={exit_xy[1]};exitDx=0;exitDy=0;'
             f'entryX={entry_xy[0]};entryY={entry_xy[1]};entryDx=0;entryDy=0;'
             f'dashed={int(dashed)};fontFamily=Arial;fontSize={size};fontColor=#334155;labelBackgroundColor=#ffffff;')
    cell=ET.SubElement(root,'mxCell',id=key,value=caption,edge='1',parent='1',source=source,target=target,style=style)
    geom=ET.SubElement(cell,'mxGeometry',x='0',y='0',relative='1',**{'as':'geometry'})
    lengths=[abs(b[0]-a[0])+abs(b[1]-a[1]) for a,b in zip(points,points[1:])]
    remaining=sum(lengths)/2
    middle=points[0]
    for a,b,length in zip(points,points[1:],lengths):
        if remaining<=length:
            t=remaining/length if length else 0
            middle=(a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1]))
            break
        remaining-=length
    ET.SubElement(geom,'mxPoint',x=str(label_center[0]-middle[0]),y=str(label_center[1]-middle[1]),**{'as':'offset'})
    if len(points)>2:
        arr=ET.SubElement(geom,'Array',**{'as':'points'})
        for x,y in points[1:-1]:
            ET.SubElement(arr,'mxPoint',x=str(x),y=str(y))
    path='M'+' L'.join(f'{x},{y}' for x,y in points)
    dash=' stroke-dasharray="7 5"' if dashed else ''
    svg.append(f'<path d="{path}" fill="none" stroke="#334155" stroke-width="2.5" marker-end="url(#arrow)"{dash}/>')
    lines=caption.split('\n')
    w=max(map(len,lines))*size*.56+20
    h=len(lines)*size*1.32+12
    svg.append(f'<rect x="{label_center[0]-w/2}" y="{label_center[1]-h/2}" width="{w}" height="{h}" rx="5" fill="white"/>')
    text_svg(*label_center,caption,size)
    edge_records.append({'id':key,'source':source,'target':target,'label':caption})


label('title',400,25,1600,65,'IGOR CORE — BIT FLOW',36,'#0f172a',True)
label('subtitle',300,92,1800,35,'74 → 128 → 64 → 3  ·  nama_sinyal[MSB:LSB]  ·  lane = 0..7  ·  Sinyal skalar: 1-bit',20)

# Decorative package pins, explicitly separate from functional ports.
for side,x in [('left',290),('right',2080)]:
    for i,y in enumerate(range(285,1266,40)):
        box(f'pin-{side}-{i}',x,y,20,12,fill='#94a3b8',stroke='#64748b',radius=2,width=1)
box('chip',310,150,1770,1140,fill='#f8fafc',stroke='#0f172a',radius=28,width=4)
box('chip-header',345,175,1700,75,'IGOR  |  FPGA NEURAL CORE  |  WIDTHS FROM RTL',fill='#0f172a',stroke='#0f172a',size=28,bold=True,text='#ffffff')
box('memory',780,300,710,150,'MEMORY: weights + bias\n8 bank × 4.096 × 16-bit ROM\nM10K · 64 KiB · address[11:0] bersama',fill='#ede9fe',stroke='#7c3aed',size=23,bold=True)
box('input',20,590,220,150,'INPUT\n74 nilai berurutan\ninput_value[15:0]\nskala 1/256',fill='#eff6ff',stroke='#2563eb',size=19,bold=True)
box('storage',390,590,210,150,'DATA STORAGE\n74 × s16 input\n128 × s16 hidden1\n64 × s16 hidden2',fill='#e0f2fe',stroke='#0284c7',size=20,bold=True)
box('multiply',790,590,230,150,'8× MULTIPLIER\ns16 input × s16 weights\n= s32 product',fill='#dbeafe',stroke='#2563eb',size=19,bold=True)
box('accumulator',1240,590,250,150,'8× ACCUMULATOR\ns40 + sign-extended product\n= s40 mac_sum\nRegister s40 / lane',fill='#cffafe',stroke='#0891b2',size=18,bold=True)
box('activation',1700,590,300,150,'8× ACTIVATION\ns40 → s32: [39:8]\n= floor(accumulator / 256)\nReLU / clamp: s32 → s16',fill='#dcfce7',stroke='#16a34a',size=18,bold=True)
box('actions',1700,890,300,130,'ACTIONS + OUTPUT MUX\n3 × s16 actions[0:2]\nPilih index 0, 1, atau 2\nOutput invalid → 16\'sd0',fill='#dcfce7',stroke='#16a34a',size=19,bold=True)
box('output',2180,895,200,120,'OUTPUT\noutput_value[15:0]\n1 nilai / pembacaan\nskala 1/256',fill='#f0fdf4',stroke='#16a34a',size=17,bold=True)
box('select',2180,790,200,65,'SELECT\noutput_index[1:0]',fill='#f8fafc',stroke='#94a3b8',size=17)
box('control',800,1110,690,105,'CONTROL / FSM\nUrutan baca memory, MAC, activation, dan validasi state',fill='#e2e8f0',stroke='#64748b',size=21,bold=True)
box('control-input',20,1100,220,120,'CONTROL INPUT\nclk · rst_n\nstart · abort',fill='#f8fafc',stroke='#94a3b8',size=19)
box('status',2180,1105,200,115,'STATUS\nbusy · done · fault\nsaturated\nerror_code · latency',fill='#f8fafc',stroke='#94a3b8',size=17)

edge('input-data','input','storage',[(240,665),(390,665)],(1,.5),(0,.5),'input_value[15:0]\ninput_index[6:0]\nload_input (1-bit)',(315,620),size=12)
edge('operand','storage','multiply',[(600,665),(790,665)],(1,.5),(0,.5),'operand[15:0]\nbroadcast ×8',(695,625))
edge('weights','memory','multiply',[(905,450),(905,590)],(125/710,1),(.5,0),'weight[lane][15:0]\nlane = 0..7',(1035,520))
edge('bias','memory','accumulator',[(1365,450),(1365,590)],(585/710,1),(.5,0),'weight[lane][15:0] (bias)\n→ acc[39:0], << 8\nlane = 0..7',(1550,520),size=14)
edge('products','multiply','accumulator',[(1020,665),(1240,665)],(1,.5),(0,.5),'product[lane][31:0]\n+ 8 sign bits → 40-bit',(1130,625),size=14)
edge('sum','accumulator','activation',[(1490,665),(1700,665)],(1,.5),(0,.5),'accumulator[lane][39:0]\nlane = 0..7',(1595,625),size=14)
edge('acc-feedback','accumulator','accumulator',[(1365,740),(1365,790),(1190,790),(1190,710),(1240,710)],(.5,1),(0,.8),'acc[39:0]\nper lane',(1280,790),size=15)
edge('final-actions','activation','actions',[(1850,740),(1850,890)],(.5,1),(.5,0),'activated[lane][15:0]\n→ actions[lane][15:0]\nlane = 0..2',(1940,810),size=15)
edge('result','actions','output',[(2000,955),(2180,955)],(1,.5),(0,.5),'output_value[15:0]\nindex = 0, 1, 2',(2090,915),size=14)
edge('hidden-feedback','activation','storage',[(1790,740),(1790,830),(495,830),(495,740)],(.3,1),(.5,1),'activated[lane][15:0] → hidden1 / hidden2\nhidden1[k][15:0] / hidden2[k][15:0] → operand[15:0]',(1070,875))
edge('select-index','select','actions',[(2180,822.5),(2120,822.5),(2120,860),(1940,860),(1940,890)],(0,.5),(.8,0),'output_index[1:0]',(2110,870),True,size=13)
edge('control-in','control-input','control',[(240,1160),(800,1160)],(1,.5),(0,50/105),'clk, rst_n, start, abort\n(1-bit tiap sinyal)',(520,1110),True)
edge('control-out','control','status',[(1490,1162.5),(2180,1162.5)],(1,.5),(0,.5),'busy, done, fault, saturated (1-bit)\nerror_code[3:0]; latency_cycles[31:0]',(1835,1110),True,size=15)
edge('output-valid','control','actions',[(1420,1110),(1420,1055),(1660,1055),(1660,980),(1700,980)],(620/690,0),(0,90/130),'done, fault, abort\n(1-bit tiap sinyal)',(1515,1050),True,size=15)
label('scales',350,945,1050,55,'Input, weights, bias: kode / 256  →  product, accumulator: kode / 65.536\nActivation: floor(accumulator / 256), lalu clamp sebelum hasil s16',18)
label('timing',400,1310,1600,45,'6.916 siklus  ·  50 MHz  ·  138,32 µs  (<160 µs)',25,'#0f172a',True)
label('scope',300,1370,1800,36,'Lebar aktual RTL 16/32/40-bit · Bundel kontrol = sinyal terpisah · Pins ilustratif · UART berada di wrapper',17)

ET.indent(mxfile,space='  ')
(OUT/'igor_core_simple.drawio').write_bytes(ET.tostring(mxfile,encoding='utf-8',xml_declaration=True))
svg.append('</svg>')
(OUT/'igor_core_simple.svg').write_text('\n'.join(svg),encoding='utf-8')
sys.path.insert(0,str(ROOT/'.runtime/diagram_renderer'))
import resvg_py
(OUT/'igor_core_simple.png').write_bytes(resvg_py.svg_to_bytes(svg_string='\n'.join(svg)))
names=['docs/assets/igor_core_simple.drawio','docs/assets/igor_core_simple.svg','docs/assets/igor_core_simple.png',
       'scripts/render_igor_core_drawio.py','experiments/parallel8/igor_src_policy_core.v','experiments/parallel8/artifacts/acceptance.json']
record={'kind':'editable RTL bit-flow diagram; no RTL or hardware change',
        'edges':edge_records,'files':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}}
(OUT/'igor_core_simple.provenance.json').write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('Generated editable draw.io + SVG + PNG:',OUT/'igor_core_simple.drawio')
