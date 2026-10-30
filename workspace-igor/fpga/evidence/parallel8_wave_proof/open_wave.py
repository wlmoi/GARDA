"""Open an evidence view interactively with its original zoom and markers."""
from pathlib import Path
import argparse, json, shutil, subprocess, sys
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='replace')
here=Path(__file__).resolve().parent
views=json.loads((here/'screenshots.json').read_text())
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('view',nargs='?',default='08_eight_lanes')
p.add_argument('--list',action='store_true')
p.add_argument('--gtkwave',default=shutil.which('gtkwave') or 'C:/iverilog/gtkwave/bin/gtkwave.exe')
args=p.parse_args()
if args.list:
    for v in views:print(v['name'],v['title'])
    raise SystemExit(0)
v=next((v for v in views if v['name']==args.view),None)
if v is None:p.error('Unknown view; use --list')
script=here/'interactive.tcl'
cmds=[f'gtkwave::setZoomRangeTimes {v["start"]} {v["end"]}',f'gtkwave::setMarker {v["marker"]}']
for letter,(t,label) in zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ',v['markers']):
    cmds.append(f'gtkwave::setNamedMarker {letter} {t} "{label}"')
script.write_text('\n'.join(cmds)+'\n')
subprocess.Popen([args.gtkwave,'-r',str(here/'proof.gtkwaverc'),'-S',str(script),str(here/v['waveform']),str(here/'images'/f'{v["name"]}.gtkw')],cwd=here)
