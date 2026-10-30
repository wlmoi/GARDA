"""Layout must contain both live parameter and activation macro hierarchies."""
from pathlib import Path
import tempfile,unittest
from check_sram_layout import db,TOP,inspect_layout,EXPECTED_COUNTS
from asic.neural_sram.contracts import PARAM_MACRO,ACT_MACRO
class LayoutTests(unittest.TestCase):
    def make_layout(self,path,parameters,activations,top_name=TOP,orphan_activations=0):
        layout=db.Layout();top=layout.create_cell(top_name)
        for master,number in [(PARAM_MACRO,parameters),(ACT_MACRO,activations)]:
            macro=layout.create_cell(master)
            macro.shapes(layout.layer(1,0)).insert(db.Box(0,0,100,100))
            for i in range(number):top.insert(db.CellInstArray(macro.cell_index(),db.Trans(i*200,0)))
            if master==ACT_MACRO and orphan_activations:
                orphan=layout.create_cell('unreachable')
                for i in range(orphan_activations):
                    orphan.insert(db.CellInstArray(macro.cell_index(),db.Trans(i*200,0)))
        layout.write(str(path))
    def test_accepts_parameter_and_activation_hierarchy(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'valid.gds';self.make_layout(path,1,2)
            self.assertEqual(inspect_layout(path)['macro_counts'],EXPECTED_COUNTS)
    def test_rejects_missing_extra_wrong_and_unreachable_banks(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'invalid.gds'
            for parameters,activations,orphan in [(0,0,4),(1,0,2),(1,1,1),(0,3,0),(2,2,0),(1,3,0)]:
                self.make_layout(path,parameters,activations,orphan_activations=orphan)
                with self.assertRaises(ValueError):inspect_layout(path)
    def test_rejects_previous_safety_gate_target(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'gate.gds';self.make_layout(path,1,2,top_name='tt_um_wlmoi_igor_gate')
            with self.assertRaises(ValueError):inspect_layout(path)
if __name__=='__main__':unittest.main()
