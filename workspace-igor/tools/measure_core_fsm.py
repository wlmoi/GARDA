"""Measure an explicit FSM model against the existing Icarus VCD.

This is observed functional state/arc coverage, not native simulator FSM
extraction, exhaustive transition proof, or a substitute for branch coverage.
"""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'fpga/evidence/parallel8_wave_proof'
VCD=BASE/'core/core.vcd'
RTL=ROOT/'fpga/experiments/parallel8/igor_src_policy_core.v'
OUT=ROOT/'fpga/evidence/rtl_coverage'
receipt=json.loads((BASE/'simulation_receipt.json').read_text())
expected=receipt['accepted_inputs_sha256']['experiments/parallel8/igor_src_policy_core.v']
assert hashlib.sha256(RTL.read_bytes()).hexdigest()==expected, 'Waveform RTL binding differs'
names={0:'IDLE',1:'BIAS_ADDRESS',2:'BIAS_WAIT',3:'BIAS_TAKE',4:'WEIGHT_ADDRESS',5:'WEIGHT_WAIT',6:'MAC',7:'ACTIVATE'}
normal={(0,1),(1,2),(2,3),(3,4),(4,5),(5,6),(6,4),(6,7),(7,1),(7,0)}
states=set(); arcs=set(); previous=None; scope=[]; symbol=None; header=True
with VCD.open() as stream:
    for raw in stream:
        parts=raw.split()
        if not parts: continue
        if header:
            if parts[0]=='$scope': scope.append(parts[2])
            elif parts[0]=='$upscope': scope.pop()
            elif parts[0]=='$var' and '.'.join(scope)=='tb_src_policy_core.dut' and parts[4]=='state': symbol=parts[3]
            elif parts[0]=='$enddefinitions': header=False;assert symbol,'FSM state missing'
            continue
        if parts[0].startswith('b') and len(parts)==2 and parts[1]==symbol:
            bits=parts[0][1:]
            if any(c in bits.lower() for c in 'xz'):
                previous=None;continue
            current=int(bits,2)
            states.add(current)
            if previous is not None and current!=previous: arcs.add((previous,current))
            previous=current
result={'scope':'Functional FSM observation from bound existing Icarus waveform; sampled transitions, no self-loop or reset-arc denominator',
        'source_sha256':expected,'waveform_sha256':hashlib.sha256(VCD.read_bytes()).hexdigest(),
        'waveform':VCD.relative_to(ROOT).as_posix(),
        'state_coverage':{'hit':len(states & names.keys()),'total':8,'percent':100*len(states & names.keys())/8},
        'normal_arc_coverage':{'hit':len(arcs & normal),'total':len(normal),'percent':100*len(arcs & normal)/len(normal)},
        'normal_arc_bins':[{'from':names[a],'to':names[b],'hit':(a,b) in arcs} for a,b in sorted(normal)],
        'observed_other_changes':[list(x) for x in sorted(arcs-normal)],
        'limitations':['Waveform intentionally omits vectors 2..235; only observed segments counted.',
                      'Other observed changes may be reset/abort/fault; they are not classified as normal arcs.',
                      'Illegal-state recovery is verified separately by the instrumented supplemental test.',
                      'Not MC/DC, native FSM extraction, or 100% of all temporal interleavings.']}
(OUT/'fsm_observation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['state_coverage','normal_arc_coverage']},indent=2))
