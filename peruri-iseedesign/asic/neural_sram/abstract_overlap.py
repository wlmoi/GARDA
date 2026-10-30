"""Qualify only LEF obstruction overlaps on the checked SRAM power columns."""
from collections import Counter
from decimal import Decimal
import hashlib
import re

from .contracts import EXPECTED_INSTANCES


def qualify_overlaps(feedback, scale, macros, expected_count):
    """Fail closed on unknown types, locations, missing entries or macro views.

    Magic extracts LEF abstractions; their Metal4 obstructions cover the real
    SRAM supply columns. KLayout checks the assembled GDS separately. Preserve
    Magic's raw count and require every reported rectangle to be inside one
    intended SRAM footprint and its exact 2.1-um extended supply stripe.
    """
    from pathlib import Path
    scale=Decimal(str(scale))
    if scale<=0:raise ValueError('Invalid Magic feedback scale')
    footprints=[];actual={}
    for master,macro in macros.items():
        if len(macro['lef'])!=1:raise ValueError('Expected one official LEF per SRAM')
        lef=Path(macro['lef'][0]).read_text()
        size=re.search(r'\bSIZE\s+([\d.]+)\s+BY\s+([\d.]+)',lef)
        if size is None:raise ValueError('SRAM dimensions missing')
        width,height=map(Decimal,size.groups())
        centers=set()
        for pin in ['VDD!','VDDARRAY!','VSS!']:
            body=re.search(r'\bPIN\s+'+re.escape(pin)+r'\s+(.*?)\n\s*END\s+'+re.escape(pin)+r'\s',lef,re.S)
            if body is None:raise ValueError('Missing SRAM supply pin')
            if set(re.findall(r'\bLAYER\s+(\S+)',body[1]))!={'Metal4'}:
                raise ValueError('Unexpected SRAM supply layer')
            rectangles=re.findall(r'\bRECT\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)',body[1])
            if not rectangles:raise ValueError('Missing supply geometry')
            for left,bottom,right,top in rectangles:
                centers.add((Decimal(left)+Decimal(right))/2)
        for name,instance in macro['instances'].items():
            actual[name]=master
            if instance['orientation']!='N':raise ValueError('Expected N orientation')
            x,y=map(lambda value:Decimal(str(value)),instance['location'])
            footprints.append((name,x,y,x+width,y+height,[x+v for v in centers]))
    if actual!=EXPECTED_INSTANCES:raise ValueError('Unexpected SRAM identities')
    lines=[line.strip() for line in feedback.splitlines() if line.strip()]
    if len(lines)!=2*expected_count:raise ValueError('Magic feedback count differs from metric')
    counts=Counter();tolerance=scale+Decimal('0.001')
    for offset in range(0,len(lines),2):
        box=re.fullmatch(r'box (-?\d+) (-?\d+) (-?\d+) (-?\d+)',lines[offset])
        if box is None:raise ValueError('Unrecognized overlap rectangle')
        if lines[offset+1]!='feedback add "Illegal overlap between obsm4 and metal4 (types do not connect)" medium':
            raise ValueError('Unqualified Magic overlap type')
        a,b,c,d=[Decimal(v)*scale for v in box.groups()]
        if a>=c or b>=d:raise ValueError('Invalid overlap rectangle')
        matches=[]
        for name,x0,y0,x1,y1,centers in footprints:
            if a<x0-tolerance or b<y0-tolerance or c>x1+tolerance or d>y1+tolerance:continue
            if any(a>=center-Decimal('1.05')-tolerance and c<=center+Decimal('1.05')+tolerance for center in centers):
                matches.append(name)
        if len(matches)!=1:raise ValueError(f'Overlap outside a unique SRAM supply column: {a},{b},{c},{d}')
        counts[matches[0]]+=1
    return {'status':'PASS','raw_magic_overlap_count':expected_count,
            'qualified_sram_abstraction_count':sum(counts.values()),'unqualified_count':0,
            'instances':dict(counts),'feedback_sha256':hashlib.sha256(feedback.encode()).hexdigest(),
            'qualification':'Only obsm4/metal4 rectangles within SRAM supply stripes; actual GDS DRC and LVS must pass separately'}
