"""Connect the program SRAM to the CMOS5L tile's Metal4 power pins."""
from pathlib import Path

from librelane.steps import Step
from librelane.steps.openroad import OpenROADStep
from librelane.steps.netgen import LVS
from librelane.config import Variable
from librelane.common import Path as ConfigPath
from tools.netgen_json import normalize_sram_power_pins, repair_report
from librelane.state import State, DesignFormat


@Step.factory.register()
class PowerProgramSRAM(OpenROADStep):
    id = "Project.PowerProgramSRAM"
    name = "Connect Program SRAM Supply Columns"
    config_vars = OpenROADStep.config_vars + [
        Variable("PROGRAM_SRAM_GEOMETRY", ConfigPath,
                 "SRAM power-column geometry helper",
                 default=ConfigPath(str(Path(__file__).resolve().parent / "src" / "sram_geometry.tcl")))
    ]

    def get_script_path(self):
        return str(Path(__file__).resolve().parent / "src" / "power_sram.tcl")


@Step.factory.register()
class ProgramSRAMLVS(LVS):
    id = "Project.ProgramSRAMLVS"
    name = "Netgen LVS with SRAM report compatibility"

    def run(self, state_in, **kwargs):
        original = Path(state_in[DesignFormat.POWERED_NETLIST])
        adapted = Path(self.step_dir) / "netgen_powered_netlist.v"
        adapted.write_text(normalize_sram_power_pins(original.read_text()))
        # This copy is local to LVS. The original flow state and all other
        # consumers retain the OpenROAD powered netlist.
        lvs_state = State(state_in, overrides={
            DesignFormat.POWERED_NETLIST: ConfigPath(str(adapted))
        })
        return super().run(lvs_state, **kwargs)

    def run_subprocess(self, *args, **kwargs):
        result = super().run_subprocess(*args, **kwargs)
        report = Path(self.step_dir) / "reports" / "lvs.netgen.json"
        if report.is_file():
            count = repair_report(report)
            if count:
                self.warn(f"Preserved {count} literal identifier escapes in Netgen JSON. "
                          "Original report retained as lvs.netgen.json.original.")
        return result
