"""Reject the old gate, hard SRAM, missing metrics, and electrical failures."""
from pathlib import Path
import json,tempfile,unittest
from check_neural_logic_layout import db,TOP,REQUIRED,inspect_layout,validate_metrics

class LogicLayoutTests(unittest.TestCase):
    def layout(self,path,name=TOP,sram=False):
        layout=db.Layout();top=layout.create_cell(name)
        cell=layout.create_cell('RM_IHPSG13_test' if sram else 'sg13cmos5l_buf_1')
        cell.shapes(layout.layer(1,0)).insert(db.Box(0,0,100,100))
        top.insert(db.CellInstArray(cell.cell_index(),db.Trans()));layout.write(str(path))

    def test_only_full_inference_without_hard_sram_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'layout.gds';self.layout(path)
            self.assertEqual(inspect_layout(path)['physical_sram_banks'],0)
            self.layout(path,sram=True)
            with self.assertRaises(ValueError):inspect_layout(path)
            self.layout(path,name='tt_um_wlmoi_igor_gate')
            with self.assertRaises(ValueError):inspect_layout(path)

    def test_each_required_signoff_metric_is_enforced(self):
        clean=dict.fromkeys(REQUIRED,0);validate_metrics(clean)
        for name in REQUIRED:
            with self.assertRaises(ValueError):validate_metrics({**clean,name:1})
            missing=clean.copy();del missing[name]
            with self.assertRaises(ValueError):validate_metrics(missing)

    def test_active_sources_and_native_pin_template_flow(self):
        root=Path(__file__).resolve().parents[1]
        info=(root/'info.yaml').read_text();self.assertIn('top_module: '+TOP,info)
        config=json.loads((root/'src/config.json').read_text())
        self.assertEqual(config['CLOCK_PERIOD'],20)
        self.assertNotIn('MACROS',config);self.assertNotIn('PDN_CFG',config)
        self.assertNotIn('meta',config)  # ApplyDEFTemplate stays after PDN.
        self.assertFalse(config['GRT_ALLOW_CONGESTION'])
        # Both horizontal routing layers are available to signals. Clocks stay
        # on Metal2 and above. Never "repair" the run by accepting congestion.
        self.assertEqual(config['RT_MIN_LAYER'],'Metal1')
        self.assertEqual(config['RT_CLOCK_MIN_LAYER'],'Metal2')
        self.assertEqual(config['GRT_ADJUSTMENT'],0.1)
        self.assertTrue(config['ERROR_ON_TR_DRC'])
        self.assertTrue(config['ERROR_ON_KLAYOUT_DRC'])
        self.assertTrue(config['ERROR_ON_LVS_ERROR']);self.assertTrue(config['ERROR_ON_ILLEGAL_OVERLAPS'])

if __name__=='__main__':unittest.main()
