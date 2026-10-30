"""Map the actual eight-lane DE10-Nano design to Cyclone V FPGA primitives."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'experiments/parallel8'
OUT = ROOT / 'verification/build/de10_parallel8'
TOP = 'garda_src_policy_de10_nano'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = PROJECT / 'garda_src_policy.qsf'
    sources = [(PROJECT / name).resolve() for name in
               re.findall(r'^set_global_assignment -name VERILOG_FILE (.+)$', manifest.read_text(), re.M)]
    if not sources or any(not path.is_file() for path in sources):
        raise ValueError('The active Quartus source manifest is incomplete')
    # Reconstruct every bank from the source-current, independently checked ROM.
    words = (ROOT / 'rtl/garda_src_policy/policy_weights.mem').read_text().split()
    for lane in range(8):
        bank = []
        for rows, columns, weight_base, bias_base in ((128,74,0,9472),(64,128,9600,17792),(3,64,17856,18048)):
            groups = (rows + 7) // 8
            for group in range(groups):
                neuron = group * 8 + lane
                bank += words[weight_base + neuron*columns:weight_base + (neuron+1)*columns] if neuron < rows else ['0000'] * columns
            bank += [words[bias_base + group*8 + lane] if group*8 + lane < rows else '0000' for group in range(groups)]
        bank += ['0000'] * (4096 - len(bank))
        if [int(word,16) for word in (PROJECT / f'bank{lane}.mem').read_text().split()] != [int(word,16) for word in bank]:
            raise ValueError(f'bank{lane}.mem differs from the source model')
    def quote(path):
        return '"' + path.as_posix() + '"'
    # Defer unused serial-ROM elaboration from the shared Quartus manifest;
    # the active Parallel8 core initializes its eight banks in this project.
    command = 'read_verilog -defer ' + ' '.join(quote(path) for path in sources)
    command += f'; synth_intel_alm -family cyclonev -top {TOP}; check -assert; stat; '
    command += f'write_json {quote(OUT / "netlist.json")}'
    subprocess.run([shutil.which('yosys') or 'yosys','-l',str(OUT / 'synthesis.log'),'-p',command],cwd=PROJECT,check=True)
    netlist = json.loads((OUT / 'netlist.json').read_text())
    cells = netlist['modules'][TOP]['cells']
    counts = Counter(cell['type'] for cell in cells.values())
    if not counts.get('MISTRAL_M10K') or not any(name.startswith('MISTRAL_MUL') for name in counts):
        raise ValueError('Expected model block RAM and DSP multipliers in the mapped design')
    if any(name.startswith('$') for name in counts):
        raise ValueError('Unmapped generic cells remain')
    report = {'status':'PASS','target':'Cyclone V 5CSEBA6U23I7','top':TOP,
              'scope':'Source-current technology-mapped synthesis; Quartus fit, timing and bitstream are separate',
              'clock_hz':50000000,'parallel_mac_lanes':8,'cells':dict(sorted(counts.items())),
              'source_sha256':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in [manifest,*sources,*[PROJECT / f'bank{lane}.mem' for lane in range(8)]]}}
    (OUT / 'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
