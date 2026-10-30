"""Reject a submission/viewer layout that omits the active neural SRAM banks."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.runtime/layout-python'))
import klayout.db as db

TOP = 'tt_um_wlmoi_igor_neural_sram'
sys.path.insert(0,str(ROOT))
from asic.neural_sram.contracts import EXPECTED_COUNTS


def inspect_layout(path):
    layout = db.Layout()
    layout.read(str(path))
    top = layout.cell(TOP)
    if top is None:
        raise ValueError(f'Active neural top {TOP} missing from {path}')
    counts={master:0 for master in EXPECTED_COUNTS}
    def count(cell,multiplicity=1):
        for instance in cell.each_inst():
            copies=multiplicity*(instance.na*instance.nb if instance.is_regular_array() else 1)
            child=instance.cell
            if child.name in counts:counts[child.name]+=copies
            elif child.name.startswith('RM_IHPSG13_'):
                raise ValueError(f'Unexpected reachable SRAM master: {child.name}')
            else:count(child,copies)
    count(top)
    if counts != EXPECTED_COUNTS:
        raise ValueError(f'Expected one parameter and two activation SRAMs; found {counts}')
    banks=sum(counts.values())
    box = top.bbox()
    return {'top': top.name, 'macro_counts':counts, 'physical_banks': banks,
            'layout': str(path), 'bounds_um': [v * layout.dbu for v in
                                             [box.left, box.bottom, box.right, box.top]]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('layout', type=Path)
    parser.add_argument('--metrics', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = inspect_layout(args.layout)
    if args.metrics:
        metrics = json.loads(args.metrics.read_text())
        required = ['design__lvs_error__count', 'klayout__drc_error__count',
                    'design__power_grid_violation__count',
                    'project__unqualified_overlap__count']
        for key in required:
            if metrics.get(key) != 0:
                raise ValueError(f'Physical acceptance failed: {key}={metrics.get(key)}')
        report['physical_metrics'] = {key: metrics[key] for key in required}
        report['timing_metrics'] = {key: value for key, value in metrics.items()
                                    if key.startswith('timing__')}
        # Setup/hold and electrical limits qualify the intended operating clock.
        for key in ['timing__setup_vio__count', 'timing__hold_vio__count',
                    'design__max_slew_violation__count',
                    'design__max_cap_violation__count']:
            if metrics.get(key) != 0:
                raise ValueError(f'50 MHz timing acceptance failed: {key}={metrics.get(key)}')
    report['status'] = 'PASS'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
