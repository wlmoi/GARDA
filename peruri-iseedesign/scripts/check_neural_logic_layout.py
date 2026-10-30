"""Require the complete inference target, no hard SRAM, and strict signoff."""
from pathlib import Path
import argparse,json,sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.runtime/layout-python'))
import klayout.db as db

TOP='tt_um_wlmoi_igor_neural_logic'
REQUIRED=['design__lvs_error__count','klayout__drc_error__count','route__drc_errors',
          'design__power_grid_violation__count','magic__illegal_overlap__count',
          'timing__setup_vio__count','timing__hold_vio__count',
          'design__max_slew_violation__count','design__max_cap_violation__count']


def inspect_layout(path):
    layout=db.Layout();layout.read(str(path));top=layout.cell(TOP)
    if top is None:raise ValueError(f'Full inference target {TOP} missing')
    visited=set()
    def visit(cell):
        if cell.cell_index() in visited:return
        visited.add(cell.cell_index())
        if cell.name.startswith('RM_IHPSG13_'):raise ValueError(f'Unexpected SRAM: {cell.name}')
        for instance in cell.each_inst():visit(instance.cell)
    visit(top)
    box=top.bbox()
    if box.empty():raise ValueError('Empty inference layout')
    return {'top':TOP,'physical_sram_banks':0,'reachable_cell_types':len(visited),
            'layout':str(path),'bounds_um':[v*layout.dbu for v in [box.left,box.bottom,box.right,box.top]]}


def validate_metrics(metrics):
    for name in REQUIRED:
        if metrics.get(name)!=0:raise ValueError(f'Physical acceptance failed: {name}={metrics.get(name)}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('layout',type=Path);parser.add_argument('--metrics',type=Path)
    parser.add_argument('--report',type=Path);args=parser.parse_args()
    report=inspect_layout(args.layout)
    if args.metrics:
        metrics=json.loads(args.metrics.read_text());validate_metrics(metrics)
        report['physical_metrics']={name:metrics[name] for name in REQUIRED}
        report['timing_metrics']={key:value for key,value in metrics.items() if key.startswith('timing__')}
    report['status']='PASS'
    if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
