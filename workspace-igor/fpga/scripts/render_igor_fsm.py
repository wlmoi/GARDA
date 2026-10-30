"""Build native multi-page draw.io FSMs with Graphviz layout and SVG/PNG previews.

Requirements: Graphviz dot on PATH; resvg-py in fpga/.runtime/diagram_renderer.
This script documents RTL; it neither synthesizes nor changes RTL.
"""
from pathlib import Path
import base64
import hashlib
import html
import json
import math
import re
import shutil
import subprocess
import sys
import textwrap
import xml.etree.ElementTree as ET
from igor_fsm_data import PAGES

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/assets/igor_fsm'
OUT.mkdir(parents=True,exist_ok=True)
DOT=shutil.which('dot')
if not DOT:
    raise SystemExit('Graphviz dot is required on PATH')
sys.path.insert(0,str(ROOT/'.runtime/diagram_renderer'))
import resvg_py

book=ET.Element('mxfile',host='app.diagrams.net',type='device')
sources=set()
catalog=[]


def quoted(value):
    return json.dumps(value,ensure_ascii=False)


def wrap(value,limit=38):
    return '\n'.join(piece for line in value.split('\n')
                     for piece in (textwrap.wrap(line,limit,break_long_words=False,break_on_hyphens=False) or ['']))


def add_text(svg,x,y,value,size=18,bold=False,color='#172033',anchor='middle'):
    lines=value.split('\n')
    for i,line in enumerate(lines):
        yy=y+(i-(len(lines)-1)/2)*size*1.35
        svg.append(f'<text x="{x:.2f}" y="{yy:.2f}" text-anchor="{anchor}" dominant-baseline="middle" font-family="Arial, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{color}">{html.escape(line)}</text>')


def vertex(root,key,label,x,y,w,h,style):
    c=ET.SubElement(root,'mxCell',id=key,value=label,vertex='1',parent='1',style=style)
    ET.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),**{'as':'geometry'})
    return c


def core_layout(spec,labels):
    """Keep the main eight-state loop clockwise, with separate return channels."""
    w,h=2400,1100
    centres={'IDLE':(300,180),'BIAS_ADDRESS':(900,180),'BIAS_WAIT':(1500,180),
             'BIAS_TAKE':(2100,180),'WEIGHT_ADDRESS':(2100,700),
             'WEIGHT_WAIT':(1500,700),'MAC':(900,700),'ACTIVATE':(300,700),
             '__reset':(300,20)}
    if spec['key']=='10_legacy_neural':
        aliases=dict(zip(['IDLE','BIAS_ADDRESS','BIAS_WAIT','BIAS_TAKE','WEIGHT_ADDRESS','WEIGHT_WAIT','MAC','ACTIVATE'],
                         [s['id'] for s in spec['states']]))
        centres={aliases.get(key,key):value for key,value in centres.items()}
    objects=[]; indices={}
    for key,(x,y) in centres.items():
        indices[key]=len(objects)
        objects.append({'_gvid':len(objects),'name':key,'pos':f'{x},{h-y}',
                        'width':430/72 if key!='__reset' else .16,
                        'height':180/72 if key!='__reset' else .16,
                        'fillcolor':'#DDEAF7' if key==spec['states'][0]['id'] else '#E6F3CF'})
    routes=[
      ([(85,180),(30,180),(30,315),(150,315),(150,245)],(140,365)),
      ([(515,180),(685,180)],(600,180)),
      ([(1115,180),(1285,180)],(1200,180)),
      ([(1715,180),(1885,180)],(1800,180)),
      ([(2100,270),(2100,610)],(2250,440)),
      ([(1885,700),(1715,700)],(1800,700)),
      ([(1285,700),(1115,700)],(1200,700)),
      ([(900,790),(900,1000),(2100,1000),(2100,790)],(1500,1000)),
      ([(685,700),(515,700)],(600,700)),
      ([(400,620),(400,515),(830,515),(830,265)],(650,515)),
      ([(350,612),(350,410),(970,410),(970,265)],(680,410)),
      ([(300,610),(300,270)],(175,465))]
    edges=[]
    def put(source,target,caption,pts,lp):
        pos=' '.join(f'{x},{h-y}' for x,y in pts)
        edges.append({'tail':indices[source],'head':indices[target],
                      'label':caption,'lp':f'{lp[0]},{h-lp[1]}','pos':pos,'polyline':True})
    put('__reset',spec['states'][0]['id'],'!rst_n / reset',[(300,26),(300,90)],(435,50))
    for edge,(pts,lp) in zip(spec['transitions'],routes):
        limit=22 if len(pts)==2 else 43
        put(edge['source'],edge['target'],wrap(edge['label'],limit),pts,lp)
    return {'bb':f'0,0,{w},{h}','objects':objects,'edges':edges}


def mode_layout(spec):
    """Ten-state clockwise controller; hold loops sit outside the main ring."""
    w,h=3000,1100
    centres={'RX':(300,220),'LOAD':(900,220),'START':(1500,220),'RUN':(2100,220),'CAP0':(2700,220),
             'CAP1':(2700,700),'CAP2':(2100,700),'TX':(1500,700),
             'TX_START_LAST':(900,700),'TX_END_LAST':(300,700),'__reset':(20,220)}
    objects=[]; indices={}
    for key,(x,y) in centres.items():
        indices[key]=len(objects)
        objects.append({'_gvid':len(objects),'name':key,'pos':f'{x},{h-y}',
                        'width':430/72 if key!='__reset' else .16,
                        'height':180/72 if key!='__reset' else .16,
                        'fillcolor':'#DDEAF7' if key=='RX' else '#E6F3CF'})
    routes={
      ('RX','LOAD'):([(515,220),(685,220)],(600,220)),
      ('LOAD','START'):([(1115,220),(1285,220)],(1200,220)),
      ('START','RUN'):([(1715,220),(1885,220)],(1800,220)),
      ('RUN','CAP0'):([(2315,220),(2485,220)],(2400,220)),
      ('CAP0','CAP1'):([(2700,310),(2700,610)],(2850,460)),
      ('CAP1','CAP2'):([(2485,700),(2315,700)],(2400,700)),
      ('CAP2','TX'):([(1885,700),(1715,700)],(1800,700)),
      ('TX','TX_START_LAST'):([(1285,700),(1115,700)],(1200,700)),
      ('TX_START_LAST','TX_END_LAST'):([(685,700),(515,700)],(600,700)),
      ('TX_END_LAST','RX'):([(300,610),(300,310)],(450,460))}
    edges=[]
    def put(source,target,caption,pts,lp):
        edges.append({'tail':indices[source],'head':indices[target],'label':caption,
                      'lp':f'{lp[0]},{h-lp[1]}','pos':' '.join(f'{x},{h-y}' for x,y in pts),'polyline':True})
    put('__reset','RX','!rst_n / reset',[(26,220),(85,220)],(53,155))
    for edge in spec['transitions']:
        source,target=edge['source'],edge['target']
        if source==target:
            x,y=centres[source]
            if y==220:
                pts=[(x+150,y-65),(x+150,70),(x-150,70),(x-150,y-65)]; lp=(x,50)
            else:
                pts=[(x+150,y+65),(x+150,950),(x-150,950),(x-150,y+65)]; lp=(x,950)
            limit=42
        else:
            pts,lp=routes[(source,target)]; limit=22 if len(pts)==2 and pts[0][1]==pts[1][1] else 35
        put(source,target,wrap(edge['label'],limit),pts,lp)
    return {'bb':f'0,0,{w},{h}','objects':objects,'edges':edges}


for spec in sorted(PAGES,key=lambda p:p['key']):
    structural=spec['kind'].startswith(('OVERVIEW','STRUCTURE'))
    ids={s['id'] for s in spec['states']}
    assert len(ids)==len(spec['states'])
    for edge in spec['transitions']:
        assert edge['source'] in ids and edge['target'] in ids and edge['label']
    sources.add(spec['source'])
    labels={s['id']:s['label']+'\n'+wrap(s['action'],32) for s in spec['states']}
    lines=['digraph FSM {',
           'graph [rankdir=TB, nodesep=0.95, ranksep=1.0, splines=spline, bgcolor="transparent", pad=0.15, outputorder=edgesfirst];',
           'node [shape=ellipse, style=filled, fillcolor="#E6F3CF", color="#6E8950", penwidth=2, fontname="Arial", fontsize=18, margin="0.25,0.18"];',
           'edge [fontname="Arial", fontsize=14, color="#374151", arrowsize=0.9, penwidth=1.7];']
    for state in spec['states']:
        fill='#FDE8E8' if 'FAULT' in state['id'] or state['id']=='D7' else '#E6F3CF'
        if state['id']==spec['states'][0]['id']:
            fill='#DDEAF7'
        shape='box' if structural else 'ellipse'
        lines.append(f'{quoted(state["id"])} [label={quoted(labels[state["id"]])}, fillcolor="{fill}", shape={shape}];')
    if spec['reset']:
        lines += ['"__reset" [shape=point, width=0.16, color="#506A89", fillcolor="#506A89", label=""];',
                  f'"__reset" -> {quoted(spec["states"][0]["id"])} [label="!rst_n / reset", color="#506A89"];']
    for i,edge in enumerate(spec['transitions']):
        ports=', tailport=nw, headport=ne' if edge['source']==edge['target'] else ''
        lines.append(f'{quoted(edge["source"])} -> {quoted(edge["target"])} [label={quoted(wrap(edge["label"],34))}, id="edge{i}"{ports}];')
    for rank in spec['ranks']:
        lines.append('{ rank=same; '+'; '.join(quoted(x) for x in rank)+'; }')
    lines.append('}')
    dot='\n'.join(lines)
    layout=json.loads(subprocess.run([DOT,'-Tjson'],input=dot,text=True,encoding='utf-8',capture_output=True,check=True,timeout=30).stdout)
    if spec['key'] in {'01_core_parallel8','09_baseline_serial','10_legacy_neural'}:
        layout=core_layout(spec,labels)
    if spec['key']=='02_policy_mode':
        layout=mode_layout(spec)
    _,_,gw,gh=map(float,layout['bb'].split(','))
    width=max(1700,math.ceil(gw+140))
    xoff=(width-gw)/2
    yoff=250
    def xy(x,y):
        return float(x)+xoff, gh-float(y)+yoff
    note_lines=[]
    note_lines.append('SOURCE: '+spec['source'])
    note_lines.append('RESET: '+(spec['reset'] or 'Lihat halaman FSM; halaman ini adalah struktur/overview.'))
    for n,note in enumerate(spec['notes'],1):
        note_lines += textwrap.wrap(f'{n}. {note}',max(90,int((width-180)/9.0)),break_long_words=False)
    note_height=len(note_lines)*26+44
    note_y=gh+yoff+65
    height=math.ceil(note_y+note_height+60)
    diagram=ET.SubElement(book,'diagram',id=spec['key'],name=spec['key'][:3]+' '+spec['title'])
    model=ET.SubElement(diagram,'mxGraphModel',dx=str(width),dy=str(height),grid='1',gridSize='10',
                        page='1',pageScale='1',pageWidth=str(width),pageHeight=str(height),math='0',shadow='0')
    root=ET.SubElement(model,'root')
    ET.SubElement(root,'mxCell',id='0'); ET.SubElement(root,'mxCell',id='1',parent='0')
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
         '<defs><marker id="arr" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L10,5 L0,10 Z" fill="#374151"/></marker></defs>',
         f'<rect width="{width}" height="{height}" fill="white"/>',
         f'<rect x="25" y="25" width="{width-50}" height="{height-50}" rx="45" fill="#F8FAFC" stroke="#20233F" stroke-width="3"/>',
         f'<rect x="60" y="55" width="{width-120}" height="75" rx="10" fill="#78638C"/>']
    vertex(root,'frame','',25,25,width-50,height-50,'rounded=1;arcSize=5;fillColor=#F8FAFC;strokeColor=#20233F;strokeWidth=3;')
    vertex(root,'header',spec['title'],60,55,width-120,75,'rounded=1;fillColor=#78638C;strokeColor=#78638C;fontColor=#FFFFFF;fontFamily=Arial;fontStyle=1;fontSize=25;align=center;')
    add_text(svg,width/2,92,spec['title'],25,True,'white')
    sub=spec['register']+'  |  '+spec['kind']
    vertex(root,'subtitle',sub,65,145,width-130,60,'text;html=0;strokeColor=none;fillColor=none;fontFamily=Arial;fontSize=18;align=center;whiteSpace=wrap;')
    add_text(svg,width/2,175,wrap(sub,110),18)
    objects={o['_gvid']:o for o in layout.get('objects',[]) if 'pos' in o}
    state_positions={}
    for o in objects.values():
        cx,cy=xy(*o['pos'].split(',')); w=float(o['width'])*72; h=float(o['height'])*72
        state_positions[o['name']]=(cx,cy,w,h)
        if o['name']=='__reset':
            vertex(root,'__reset','',cx-w/2,cy-h/2,w,h,'ellipse;fillColor=#506A89;strokeColor=#506A89;')
            svg.append(f'<circle cx="{cx}" cy="{cy}" r="{w/2}" fill="#506A89"/>')
        else:
            shape='rounded=1;' if structural else 'ellipse;'
            vertex(root,o['name'],labels[o['name']],cx-w/2,cy-h/2,w,h,
                    shape+f'whiteSpace=wrap;html=0;fillColor={o["fillcolor"]};strokeColor=#6E8950;strokeWidth=2;fontFamily=Arial;fontSize=18;align=center;spacing=10;')
            if structural:
                svg.append(f'<rect x="{cx-w/2}" y="{cy-h/2}" width="{w}" height="{h}" rx="15" fill="{o["fillcolor"]}" stroke="#6E8950" stroke-width="2"/>')
            else:
                svg.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{w/2}" ry="{h/2}" fill="{o["fillcolor"]}" stroke="#6E8950" stroke-width="2"/>')
            add_text(svg,cx,cy,labels[o['name']],18)
    for i,e in enumerate(layout.get('edges',[])):
        source=objects[e['tail']]['name']; target=objects[e['head']]['name']
        points=[]; endpoint=None
        for part in e['pos'].split():
            parts=part.split(',')
            if parts[0]=='e': endpoint=xy(parts[1],parts[2])
            elif len(parts)==2: points.append(xy(*parts))
        if not points: continue
        lx,ly=xy(*e['lp'].split(','))
        caption=e.get('label','').replace('\\n','\n')
        sx,sy,sw,sh=state_positions[source]
        tx,ty,tw,th=state_positions[target]
        end=endpoint or points[-1]
        anchors=f'exitX={(points[0][0]-sx+sw/2)/sw};exitY={(points[0][1]-sy+sh/2)/sh};entryX={(end[0]-tx+tw/2)/tw};entryY={(end[1]-ty+th/2)/th};exitPerimeter=0;entryPerimeter=0;'
        curved=0 if e.get('polyline') else 1
        c=ET.SubElement(root,'mxCell',id=f'edge-{i}',value=caption,edge='1',parent='1',source=source,target=target,
            style=f'edgeStyle=none;curved={curved};rounded=0;html=0;endArrow=block;endFill=1;strokeColor=#374151;strokeWidth=1.7;fontFamily=Arial;fontSize=14;labelBackgroundColor=#FFFFFF;'+anchors)
        geom=ET.SubElement(c,'mxGeometry',x='0',y='0',relative='1',**{'as':'geometry'})
        lengths=[math.dist(a,b) for a,b in zip(points,points[1:])]
        distance=sum(lengths)/2; mid=points[0]
        for a,b,length in zip(points,points[1:],lengths):
            if distance<=length:
                t=distance/length if length else 0
                mid=(a[0]+t*(b[0]-a[0]),a[1]+t*(b[1]-a[1])); break
            distance-=length
        ET.SubElement(geom,'mxPoint',x=str(lx-mid[0]),y=str(ly-mid[1]),**{'as':'offset'})
        arr=ET.SubElement(geom,'Array',**{'as':'points'})
        for x,y in points[1:-1]: ET.SubElement(arr,'mxPoint',x=str(x),y=str(y))
        path=f'M {points[0][0]},{points[0][1]}'
        if not e.get('polyline') and (len(points)-1)%3==0:
            for p in range(1,len(points),3): path+=' C '+' '.join(f'{x},{y}' for x,y in points[p:p+3])
        else:
            path+=' L '+' L '.join(f'{x},{y}' for x,y in points[1:])
        if endpoint: path+=f' L {endpoint[0]},{endpoint[1]}'
        svg.append(f'<path d="{path}" fill="none" stroke="#374151" stroke-width="1.7" marker-end="url(#arr)"/>')
        ls=caption.split('\n'); lw=max(map(len,ls))*7.5+12; lh=len(ls)*18.9+10
        svg.append(f'<rect x="{lx-lw/2}" y="{ly-lh/2}" width="{lw}" height="{lh}" rx="3" fill="white"/>')
        add_text(svg,lx,ly,caption,14)
    note_text='\n'.join(note_lines)
    vertex(root,'notes',note_text,70,note_y,width-140,note_height,
            'rounded=1;whiteSpace=wrap;html=0;fillColor=#F2EDF7;strokeColor=#C2B1D3;fontFamily=Arial;fontSize=17;align=left;verticalAlign=top;spacing=20;')
    svg.append(f'<rect x="70" y="{note_y}" width="{width-140}" height="{note_height}" rx="14" fill="#F2EDF7" stroke="#C2B1D3"/>')
    for i,line in enumerate(note_lines): add_text(svg,90,note_y+30+i*26,line,17,anchor='start')
    svg.append('</svg>')
    svg_text='\n'.join(svg)
    (OUT/(spec['key']+'.svg')).write_text(svg_text,encoding='utf-8')
    (OUT/(spec['key']+'.png')).write_bytes(resvg_py.svg_to_bytes(svg_string=svg_text))
    catalog.append(dict(spec,width=width,height=height))

ET.indent(book,space='  ')
book_path=ROOT/'docs/assets/igor_fsm_all.drawio'
book_path.write_bytes(ET.tostring(book,encoding='utf-8',xml_declaration=True))
source_files=sorted(set(sources)|{p.relative_to(ROOT).as_posix() for p in (ROOT/'rtl').rglob('*.v')}|
                    {'experiments/parallel8/igor_src_policy_de10_nano.v','scripts/igor_fsm_data.py','scripts/render_igor_fsm.py'})
receipt={'kind':'documentation of current RTL; no refactor, synthesis, or new hardware acceptance',
         'pages':catalog,'source_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in source_files},
         'drawio_sha256':hashlib.sha256(book_path.read_bytes()).hexdigest()}
(OUT/'fsm_sources.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
# Contact sheet for reviewing every page, independent of the editable XML.
cols=3; tw=640; th=440; rows=math.ceil(len(catalog)/cols)
sheet=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{cols*tw}" height="{rows*th}" viewBox="0 0 {cols*tw} {rows*th}">',
       '<rect width="100%" height="100%" fill="#E2E8F0"/>']
for i,p in enumerate(catalog):
    x=(i%cols)*tw; y=(i//cols)*th
    data=base64.b64encode((OUT/(p['key']+'.png')).read_bytes()).decode()
    sheet.append(f'<image x="{x+8}" y="{y+8}" width="{tw-16}" height="{th-38}" preserveAspectRatio="xMidYMid meet" href="data:image/png;base64,{data}"/>')
    add_text(sheet,x+tw/2,y+th-16,p['key'],15,True)
sheet.append('</svg>')
(OUT/'contact_sheet.png').write_bytes(resvg_py.svg_to_bytes(svg_string='\n'.join(sheet)))
receipt['artifact_sha256']={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted(OUT.iterdir()) if p.suffix in {'.svg','.png'}}
(OUT/'fsm_sources.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(f'Generated {len(catalog)} native draw.io pages, PNG/SVG previews, source hashes: {book_path}')
