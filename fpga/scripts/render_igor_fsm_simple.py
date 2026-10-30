"""Three black-and-white circular FSMs, split into state and clocked action."""
from pathlib import Path
import copy
import hashlib
import html
import json
import math
import sys
import xml.etree.ElementTree as ET
from igor_fsm_data import PAGES

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/assets/igor_fsm_simple'
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'.runtime/diagram_renderer'))
import resvg_py

BOOK=ET.Element('mxfile',host='app.diagrams.net',type='device')
R=110
RECORDS=[]


def ring(keys,cx,cy,radius,start):
    return {key:(cx+radius*math.cos(math.radians(start+i*360/len(keys))),
                 cy+radius*math.sin(math.radians(start+i*360/len(keys)))) for i,key in enumerate(keys)}


def node(root,key,cx,cy,name,action,svg):
    group=ET.SubElement(root,'mxCell',id=key,vertex='1',parent='1',style='group;')
    ET.SubElement(group,'mxGeometry',x=str(cx-R),y=str(cy-R),width=str(2*R),height=str(2*R),**{'as':'geometry'})
    def child(suffix,value,x,y,w,h,style):
        c=ET.SubElement(root,'mxCell',id=key+suffix,value=value,vertex='1',parent=key,style=style)
        ET.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),**{'as':'geometry'})
    child('-circle','',0,0,2*R,2*R,'ellipse;html=0;fillColor=#FFFFFF;strokeColor=#000000;strokeWidth=2;')
    child('-name',name,10,22,2*R-20,72,'text;html=0;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;fontFamily=Arial;fontSize=18;whiteSpace=wrap;')
    child('-divider','',14,R,2*R-28,1,'line;strokeColor=#000000;strokeWidth=1.5;')
    child('-action',action,15,R+8,2*R-30,R-24,'text;html=0;strokeColor=none;fillColor=none;align=center;verticalAlign=middle;fontFamily=Arial;fontSize=16;whiteSpace=wrap;')
    svg.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="white" stroke="black" stroke-width="2"/>')
    svg.append(f'<path d="M{cx-R+14},{cy} L{cx+R-14},{cy}" stroke="black" stroke-width="1.5"/>')
    text(svg,cx,cy-52,name,18)
    text(svg,cx,cy+47,action,16)


def text(svg,x,y,value,size=19,bold=False):
    lines=value.split('\n')
    for i,line in enumerate(lines):
        yy=y+(i-(len(lines)-1)/2)*size*1.3
        svg.append(f'<text x="{x}" y="{yy}" text-anchor="middle" dominant-baseline="middle" font-family="Arial, sans-serif" font-size="{size}" font-weight="{700 if bold else 400}">{html.escape(line)}</text>')


def norm(v):
    length=math.hypot(*v)
    return v[0]/length,v[1]/length


def path_points(positions,source,target,controls=None):
    a=positions[source]; b=positions[target]
    if controls:
        u=norm((controls[0][0]-a[0],controls[0][1]-a[1]))
        v=norm((controls[1][0]-b[0],controls[1][1]-b[1]))
        return [(a[0]+R*u[0],a[1]+R*u[1]),*controls,(b[0]+R*v[0],b[1]+R*v[1])]
    u=norm((b[0]-a[0],b[1]-a[1]))
    return [(a[0]+R*u[0],a[1]+R*u[1]),(b[0]-R*u[0],b[1]-R*u[1])]


def loop_points(c,angle):
    spread=.5
    return [(c[0]+radius*math.cos(angle+a),c[1]+radius*math.sin(angle+a))
            for radius,a in [(R,-spread),(R+155,-spread),(R+155,spread),(R,spread)]]


def edge(root,key,source,target,points,caption,label,positions,svg):
    source_id=source+'-circle' if source else None
    target_id=target+'-circle'
    a=positions.get(source,(0,0)); b=positions[target]
    end=points[-1]; start=points[0]
    anchors=f'entryX={(end[0]-b[0]+R)/(2*R)};entryY={(end[1]-b[1]+R)/(2*R)};entryPerimeter=0;'
    if source:
        anchors+=f'exitX={(start[0]-a[0]+R)/(2*R)};exitY={(start[1]-a[1]+R)/(2*R)};exitPerimeter=0;'
    attrs=dict(id=key,value=caption,edge='1',parent='1',target=target_id,
               style=f'edgeStyle=none;curved={int(len(points)==4)};rounded=0;endArrow=block;endFill=1;strokeColor=#000000;strokeWidth=2;html=0;fontFamily=Arial;fontSize=20;labelBackgroundColor=#FFFFFF;'+anchors)
    if source_id: attrs['source']=source_id
    c=ET.SubElement(root,'mxCell',**attrs)
    g=ET.SubElement(c,'mxGeometry',x='0',y='0',relative='1',**{'as':'geometry'})
    if not source:
        ET.SubElement(g,'mxPoint',x=str(start[0]),y=str(start[1]),**{'as':'sourcePoint'})
    if len(points)==4:
        m=tuple((points[0][i]+3*points[1][i]+3*points[2][i]+points[3][i])/8 for i in (0,1))
        p=f'M{start[0]},{start[1]} C'+' '.join(f'{x},{y}' for x,y in points[1:])
        arr=ET.SubElement(g,'Array',**{'as':'points'})
        for x,y in points[1:-1]: ET.SubElement(arr,'mxPoint',x=str(x),y=str(y))
    else:
        m=((start[0]+end[0])/2,(start[1]+end[1])/2)
        p=f'M{start[0]},{start[1]} L{end[0]},{end[1]}'
    ET.SubElement(g,'mxPoint',x=str(label[0]-m[0]),y=str(label[1]-m[1]),**{'as':'offset'})
    svg.append(f'<path d="{p}" fill="none" stroke="black" stroke-width="2" marker-end="url(#arrow)"/>')
    lines=caption.split('\n'); w=max(map(len,lines))*11+14; h=len(lines)*26+6
    svg.append(f'<rect x="{label[0]-w/2}" y="{label[1]-h/2}" width="{w}" height="{h}" fill="white"/>')
    text(svg,*label,caption,20)


def make(spec_key,key,title,width,height,positions,actions,captions,legends,curves=None,loop_directions=None,custom_labels=None,reset_point=None):
    spec=next(p for p in PAGES if p['key']==spec_key)
    assert len(captions)==len(spec['transitions'])
    curves=curves or {}; loop_directions=loop_directions or {}; custom_labels=custom_labels or {}
    diagram=ET.SubElement(BOOK,'diagram',id=key,name=title)
    model=ET.SubElement(diagram,'mxGraphModel',grid='1',gridSize='10',page='1',pageScale='1',pageWidth=str(width),pageHeight=str(height),dx=str(width),dy=str(height))
    root=ET.SubElement(model,'root'); ET.SubElement(root,'mxCell',id='0'); ET.SubElement(root,'mxCell',id='1',parent='0')
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
         '<defs><marker id="arrow" markerWidth="12" markerHeight="12" refX="11" refY="6" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L12,6 L0,12 Z" fill="black"/></marker></defs>',
         f'<rect width="{width}" height="{height}" fill="white"/>']
    def annotation(name,value,x,y,w,h,size=20):
        c=ET.SubElement(root,'mxCell',id=name,value=value,vertex='1',parent='1',
                        style=f'text;html=0;strokeColor=none;fillColor=none;fontFamily=Arial;fontSize={size};align=center;whiteSpace=wrap;')
        ET.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),**{'as':'geometry'})
        text(svg,x+w/2,y+h/2,value,size,name=='title')
    annotation('title',title,50,25,width-100,55,30)
    annotation('subtitle','Atas: state  |  Bawah: aksi register  |  Panah: kondisi transisi',50,85,width-100,35,19)
    for state in spec['states']:
        name=state['id']
        if key=='03_uart_rx': name={'S0':'IDLE (0)','S1':'START CHECK (1)','S2':'DATA (2)','S3':'STOP (3)'}[name]
        node(root,state['id'],*positions[state['id']],name,actions[state['id']],svg)
    initial=spec['states'][0]['id']; c=positions[initial]
    reset_point=reset_point or (c[0],c[1]-R-100)
    direction=norm((reset_point[0]-c[0],reset_point[1]-c[1]))
    end=(c[0]+R*direction[0],c[1]+R*direction[1])
    midpoint=((reset_point[0]+end[0])/2+70,(reset_point[1]+end[1])/2)
    edge(root,'reset',None,initial,[reset_point,end],'rst_n=0',midpoint,positions,svg)
    for i,(transition,caption) in enumerate(zip(spec['transitions'],captions)):
        source=transition['source']; target=transition['target']
        if source==target:
            angle=loop_directions.get(source,0)
            points=loop_points(positions[source],angle)
            label=(positions[source][0]+(R+90)*math.cos(angle),positions[source][1]+(R+90)*math.sin(angle))
        else:
            points=path_points(positions,source,target,curves.get(i))
            if len(points)==4:
                label=tuple((points[0][j]+3*points[1][j]+3*points[2][j]+points[3][j])/8 for j in (0,1))
            else: label=((points[0][0]+points[-1][0])/2,(points[0][1]+points[-1][1])/2)
        label=custom_labels.get(i,label)
        edge(root,f'transition-{i}',source,target,points,caption,label,positions,svg)
    legend_text='\n'.join(legends)
    annotation('legend',legend_text,60,height-300,width-120,240,18)
    svg.append('</svg>'); svg_text='\n'.join(svg)
    (OUT/(key+'.svg')).write_text(svg_text,encoding='utf-8')
    (OUT/(key+'.png')).write_bytes(resvg_py.svg_to_bytes(svg_string=svg_text))
    single=ET.Element('mxfile',host='app.diagrams.net',type='device'); single.append(copy.deepcopy(diagram)); ET.indent(single,space='  ')
    (OUT/(key+'.drawio')).write_bytes(ET.tostring(single,encoding='utf-8',xml_declaration=True))
    RECORDS.append(dict(key=key,source=spec['source'],states=[s['id'] for s in spec['states']],
                        transitions=[dict(t,diagram_label=c) for t,c in zip(spec['transitions'],captions)]))


core_keys=['IDLE','BIAS_ADDRESS','BIAS_WAIT','BIAS_TAKE','WEIGHT_ADDRESS','WEIGHT_WAIT','MAC','ACTIVATE']
core_pos=ring(core_keys,800,750,510,-135)
make('01_core_parallel8','01_core','1. FSM CORE PARALLEL8',1600,1800,core_pos,
     dict(zip(core_keys,['Tunggu start','address\n← alamat bias','Tunggu ROM','acc[39:0]\n← bias << 8',
                        'address, operand\n← data berikut','Tunggu ROM','acc[39:0]\n← mac_sum[39:0]','hidden / actions\n← activated'])),
     ['S=0','S=1','1','1','1','1','1','N=0','N=1','G=0','G=1, L=0','G=1, L=1'],
     ['S=start; N=(k==input_count-1); G=(neuron+8>=output_count); L=(layer==2).',
      'MAC, N=0: k++. ACTIVATE, G=0: neuron+=8; G=1,L=0: layer++, neuron=0.',
      'ACTIVATE, G=1,L=1: busy=0, done=1. Bias/product memakai sign-extension ke 40-bit.',
      'Global: reset dari semua state; abort/fault/protokol salah → IDLE. Fault sticky sampai reset.',
      'Default state ilegal → IDLE, fault=1, error_code=6. Transisi normal hanya setelah prioritas global lolos.',
      '1 = satu clock tanpa syarat. Source: experiments/parallel8/igor_src_policy_core.v'],
     curves={7:[(680,930),(920,930)],9:[(550,490),(720,470)],10:[(730,780),(950,550)]},
     loop_directions={'IDLE':math.pi},custom_labels={7:(800,960),9:(620,490),10:(850,620)},
     reset_point=(core_pos['IDLE'][0],150))

mode_keys=['RX','LOAD','START','RUN','CAP0','CAP1','CAP2','TX','TX_START_LAST','TX_END_LAST']
mode_pos=ring(mode_keys,1050,850,600,-126)
make('02_policy_mode','02_policy','2. FSM CONTROLLER TRANSAKSI',2100,2100,mode_pos,
     dict(zip(mode_keys,['Tunggu frame sah','core_load=1\ninput ← buffer','core_start=1','Tunggu core_done',
                        'sample0 ← output','sample1 ← output','sample2 ← output\nresult_valid=1\nresponse_valid=1',
                        'R: tx_send=1\nKirim byte berikut','Tunggu tx_busy=1','Tunggu tx_busy=0'])),
     ['A=0','A=1','I=0','I=1','1','D=0','D=1','1','1','1','R=0 atau F=0','R=1, F=1','B=0','B=1','B=1','B=0'],
     ['A=CRC+domain frame sah; I=(load_index==73); D=core_done; B=tx_busy.',
      'R=(!tx_busy && !tx_send); F=(tx_index==10). Saat R=1,F=0: tx_index++.',
      'CAP0/1 memilih output_index berikut; CAP2 menyiapkan CRC dan tx_index=0.',
      'Global E-stop/reject → RX, core_abort=1, tx_cancel=1, result_valid=0; lihat prioritas RTL.',
      'Default mode ilegal: reject(10). 1 = satu clock. Pulse register default 0 pada clock berikutnya.',
      'Source: rtl/igor_src_policy/igor_src_policy_uart.v'],
     loop_directions={key:math.atan2(850-y,1050-x) for key,(x,y) in mode_pos.items()},
     reset_point=(mode_pos['RX'][0]-240,mode_pos['RX'][1]-110))

rx_pos={'S0':(400,350),'S1':(1000,350),'S2':(1000,900),'S3':(400,900)}
make('04_uart_rx','03_uart_rx','3. FSM UART RX',1400,1450,rx_pos,
     {'S0':'Tunggu start bit','S1':'Periksa start bit','S2':'C=1: shift[bit_index]\n← sync',
      'S3':'C=1: valid / error\ndata[7:0] ← shift\njika stop sah'},
     ['sync=1','sync=0','C=0','C=1, sync=0','C=1, sync=1','C=0 atau K=0','C=1, K=1','C=0','C=1, sync=1','C=1, sync=0'],
     ['C=(count==0); K=(bit_index==7); sync adalah RX setelah synchronizer dua flop.',
      'Saat count!=0: count--. Start sah: index=0. DATA C=1,K=0: sample, index++, reload count.',
      'STOP C=1,sync=1: valid=1,data=shift; STOP C=1,sync=0: error=1. Pulse default 0 tiap clock.',
      'Reset/default case → state0. IDLE/START CHECK/DATA/STOP adalah alias kode RTL 0/1/2/3.',
      'Semua panah normal pada posedge clk. Source: rtl/igor_uart_rx.v'],
     curves={1:[(610,220),(790,220)],4:[(790,500),(610,500)],
             9:[(550,1000),(610,530)]},
     loop_directions={'S0':math.pi,'S1':0,'S2':0,'S3':math.pi},
     custom_labels={1:(700,245),4:(700,470),9:(595,770)},reset_point=(400,150))

ET.indent(BOOK,space='  ')
combined=ROOT/'docs/assets/igor_fsm_3_simple.drawio'
combined.write_bytes(ET.tostring(BOOK,encoding='utf-8',xml_declaration=True))
sources={'scripts/render_igor_fsm_simple.py','scripts/igor_fsm_data.py'}|{r['source'] for r in RECORDS}
record={'kind':'three simplified presentation diagrams; state names/topology follow existing RTL; no RTL change',
        'pages':RECORDS,'source_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sorted(sources)},
        'artifacts':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.suffix in {'.drawio','.svg','.png'}},
        'combined_sha256':hashlib.sha256(combined.read_bytes()).hexdigest()}
(OUT/'sources.json').write_text(json.dumps(record,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print('Generated exactly three circular FSMs:',combined)
