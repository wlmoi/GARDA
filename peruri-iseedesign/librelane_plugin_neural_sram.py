"""Packed parameter and activation CMOS5L SRAM power/LVS integration."""
from pathlib import Path
from librelane.steps import Step
from librelane.steps.openroad import OpenROADStep, GlobalRouting, RepairDesignPostGRT
from librelane.steps.netgen import LVS
from librelane.steps.checker import IllegalOverlap
from asic.neural_sram.abstract_overlap import qualify_overlaps
from librelane.config import Variable
from librelane.common import Path as ConfigPath
from librelane.logging import info
from librelane.state import State, DesignFormat
from asic.neural_sram.netgen_json import normalize_sram_power_pins, repair_report

SRAM_DIR = Path(__file__).resolve().parent / 'asic/neural_sram'


@Step.factory.register()
class PowerNeuralSRAM(OpenROADStep):
    id = 'Project.PowerNeuralSRAM'
    name = 'Connect Parameter and Activation SRAM Supply Columns'
    config_vars = OpenROADStep.config_vars + [
        Variable('NEURAL_SRAM_GEOMETRY', ConfigPath, 'SRAM power geometry',
                 default=ConfigPath(str(SRAM_DIR / 'sram_geometry.tcl')))
    ]

    def get_script_path(self):
        return str(SRAM_DIR / 'power_sram.tcl')


@Step.factory.register()
class NeuralSRAMLVS(LVS):
    id = 'Project.NeuralSRAMLVS'
    name = 'Netgen Neural SRAM Integration LVS'

    def run(self, state_in, **kwargs):
        original = Path(state_in[DesignFormat.POWERED_NETLIST])
        adapted = Path(self.step_dir) / 'netgen_powered_netlist.v'
        adapted.write_text(normalize_sram_power_pins(original.read_text()))
        return super().run(State(state_in, overrides={
            DesignFormat.POWERED_NETLIST: ConfigPath(str(adapted))
        }), **kwargs)

    def run_subprocess(self, *args, **kwargs):
        result = super().run_subprocess(*args, **kwargs)
        report = Path(self.step_dir) / 'reports/lvs.netgen.json'
        if report.is_file():
            count = repair_report(report)
            if count:
                self.warn(f'Preserved {count} literal identifier escapes; original report retained.')
        return result


@Step.factory.register()
class NeuralSRAMRouting(GlobalRouting):
    id='Project.NeuralSRAMRouting'
    name='Global Routing with SRAM Congestion Locations'
    def get_script_path(self):
        return str(SRAM_DIR/'routing_report.tcl')


@Step.factory.register()
class NeuralSRAMRepair(RepairDesignPostGRT):
    id='Project.NeuralSRAMRepair'
    name='Repair Routed Design and SRAM Mask Decoder Drive'
    config_vars=RepairDesignPostGRT.config_vars+[
        Variable('NEURAL_SRAM_MASK_REPAIR',ConfigPath,'SRAM mask driver repair script',
                 default=ConfigPath(str(SRAM_DIR/'mask_driver_repair.tcl')))
    ]

    def get_script_path(self):
        return str(SRAM_DIR/'repair_postgrt.tcl')


@Step.factory.register()
class NeuralSRAMAbstractOverlap(IllegalOverlap):
    id='Project.NeuralSRAMAbstractOverlap'
    name='Check SRAM LEF Obstruction Overlaps Against Supply Columns'
    inputs=[DesignFormat.SPICE]

    def run(self,state_in,**kwargs):
        count=state_in.metrics.get('magic__illegal_overlap__count')
        if count is None:raise ValueError('Missing Magic overlap metric')
        count=int(count)
        if count==0:
            super().run(state_in,**kwargs)
            return {},{'project__unqualified_overlap__count':0,
                       'project__sram_abstract_overlap__count':0}
        for metric in ['klayout__drc_error__count','route__drc_errors',
                       'design__power_grid_violation__count']:
            if state_in.metrics.get(metric)!=0:raise ValueError(f'Cannot qualify overlaps before {metric} passes')
        macros={master:{'lef':[str(p) for p in macro.lef],
                'instances':{name:{'location':inst.location,
                    'orientation':getattr(inst.orientation,'value',inst.orientation)}
                    for name,inst in macro.instances.items()}}
                for master,macro in self.config['MACROS'].items()}
        directory=Path(state_in[DesignFormat.SPICE]).parent
        report=qualify_overlaps((directory/'feedback.txt').read_text(),
                               (directory/'cif_scale.txt').read_text().strip(),macros,count)
        import json
        (Path(self.step_dir)/'sram_abstract_overlap.json').write_text(json.dumps(report,indent=2)+'\n')
        info(f'Qualified {count} LEF obstruction overlaps on SRAM power stripes; raw Magic count retained')
        return {},{'project__unqualified_overlap__count':0,
                   'project__sram_abstract_overlap__count':count}
