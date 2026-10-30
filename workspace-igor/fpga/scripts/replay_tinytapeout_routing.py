"""Replay a placed TinyTapeout design with strict, inspectable routing evidence.

Run under Linux or WSL with OpenROAD in PATH. This is a routing diagnostic,
not a replacement for the complete TinyTapeout DRC/LVS/STA/precheck flow.
The input DEF must be a placed/CTS artifact from the same submitted RTL.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def tcl_path(path):
    value = str(Path(path).resolve())
    if any(char in value for char in '{}\n\r'):
        raise ValueError('Unsupported Tcl filename characters')
    return '{' + value + '}'


def global_overflows(log):
    rows = re.findall(
        r'^\s*(Metal\d+)\s+\d+\s+\d+\s+[\d.]+%\s+(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*$',
        log, re.MULTILINE)
    return {layer: {'horizontal': int(h), 'vertical': int(v), 'total': int(total)}
            for layer, h, v, total in rows}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--def', dest='placed_def', type=Path, required=True)
    parser.add_argument('--tech-lef', type=Path, required=True)
    parser.add_argument('--cell-lef', type=Path, required=True)
    parser.add_argument('--liberty', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'evidence/tinytapeout/current/routing')
    parser.add_argument('--signal-min', choices=['Metal1', 'Metal2'])
    parser.add_argument('--global-only', action='store_true')
    parser.add_argument('--threads', type=int, default=2)
    args = parser.parse_args()
    executable = shutil.which('openroad')
    if not executable:
        parser.error('OpenROAD is required. On Windows, run this script inside WSL.')
    config = json.loads((ROOT / 'src/config.json').read_text())
    signal_min = args.signal_min or config['RT_MIN_LAYER']
    clock_min = config['RT_CLOCK_MIN_LAYER']
    for name in ['placed_def', 'tech_lef', 'cell_lef', 'liberty']:
        if not getattr(args, name).is_file():
            parser.error(f'Input does not exist: {getattr(args, name)}')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Keep output filenames relative to the working directory. OpenROAD's
    # guide writer cannot reliably handle a filename containing spaces.
    lines = [
        f'read_lef {tcl_path(args.tech_lef)}',
        f'read_lef {tcl_path(args.cell_lef)}',
        f'read_liberty {tcl_path(args.liberty)}',
        f'read_def {tcl_path(args.placed_def)}',
        f'create_clock -name clk -period {config["CLOCK_PERIOD"]} [get_ports clk]',
        f'set_routing_layers -signal {signal_min}-Metal4 -clock {clock_min}-Metal4',
        f'set_global_routing_layer_adjustment * {config["GRT_ADJUSTMENT"]}',
        'set_macro_extension 0',
        'global_route -verbose -congestion_iterations 50 -congestion_report_file global_congestion.rpt',
        'write_db global.odb',
        'write_guides global.guide',
    ]
    if not args.global_only:
        lines.extend([
            f'detailed_route -bottom_routing_layer {signal_min} -top_routing_layer Metal4 '
            '-output_drc detailed_drc.rpt -drc_report_iter_step 5 -droute_end_iter 30',
            'write_db routed.odb',
            'write_def routed.def',
        ])
    lines.append('exit')
    script = output / 'replay.tcl'
    script.write_text('\n'.join(lines) + '\n')
    command = [executable, '-exit', '-threads', str(args.threads),
               '-metrics', 'openroad_metrics.json', 'replay.tcl']
    with (output / 'openroad.log').open('w') as stream:
        completed = subprocess.run(command, cwd=output, stdout=stream, stderr=subprocess.STDOUT)
    log = (output / 'openroad.log').read_text()
    metrics_path = output / 'openroad_metrics.json'
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    overflows = global_overflows(log)
    global_pass = (len(overflows) == 4 and all(row['total'] == 0 for row in overflows.values())
                   and '[ERROR GRT-' not in log)
    # OpenROAD may exit zero with detailed-routing violations. Zero process
    # status alone is never accepted as a clean physical design.
    detailed_pass = (not args.global_only and completed.returncode == 0
                     and metrics.get('route__drc_errors') == 0
                     and (output / 'routed.def').exists())
    report = {
        'qualification': 'Placed-netlist routing replay only. Not full GDS DRC/LVS/STA acceptance.',
        'signal_layers': signal_min + '-Metal4',
        'clock_layers': clock_min + '-Metal4',
        'track_reserve': config['GRT_ADJUSTMENT'],
        'returncode': completed.returncode,
        'global_routing': {'status': 'PASS' if global_pass else 'FAIL', 'overflows': overflows},
        'detailed_routing': {'status': 'NOT_RUN' if args.global_only else ('PASS' if detailed_pass else 'FAIL'),
                             'drc_errors': metrics.get('route__drc_errors')},
        'physical_signoff': {'status': 'NOT_RUN'},
        'inputs': {name: {'path': str(getattr(args, name).resolve()), 'sha256': sha256(getattr(args, name))}
                   for name in ['placed_def', 'tech_lef', 'cell_lef', 'liberty']},
    }
    (output / 'routing_report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if not global_pass or (not args.global_only and not detailed_pass):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
