"""Check that Netgen identifier repair retains reports and LVS failures."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.netgen_json import normalize_sram_power_pins, repair_identifier_escapes, repair_report


class NetgenJSONTests(unittest.TestCase):
    def test_power_adapter_preserves_connections_and_other_cells(self):
        text = r'''other_cell outside (.\VDD! (OTHER_SUPPLY));
RM_IHPSG13_1P_256x16_c2_bm_bist \program_store.i_sram  (
 .\VSS! (VGND), .\VDD! (VPWR), .\VDDARRAY! (ARRAY_SUPPLY),
 .A_CLK(clk), .A_DIN({data_hi, data_lo}));'''
        adapted = normalize_sram_power_pins(text)
        self.assertIn(r'other_cell outside (.\VDD! (OTHER_SUPPLY));', adapted)
        self.assertIn('.VSS!(VGND)', adapted)
        self.assertIn('.VDD!(VPWR)', adapted)
        self.assertIn('.VDDARRAY!(ARRAY_SUPPLY)', adapted)
        self.assertIn('.A_DIN({data_hi, data_lo})', adapted)
        self.assertEqual(normalize_sram_power_pins(adapted), adapted)

    def test_missing_supply_connection_rejected(self):
        text = r'RM_IHPSG13_1P_256x16_c2_bm_bist \program_store.i_sram (.\VDD! (VPWR));'
        with self.assertRaises(ValueError):
            normalize_sram_power_pins(text)

    def test_duplicate_sram_instance_rejected(self):
        text = r'RM_IHPSG13_1P_256x16_c2_bm_bist \program_store.i_sram (.\VDD! (VPWR));'
        with self.assertRaises(ValueError):
            normalize_sram_power_pins(text + '\n' + text)

    def test_valid_escapes_and_unicode_unchanged(self):
        text = r'{"name":"a\\b\n\t\"c\/\u0041"}'
        repaired, count = repair_identifier_escapes(text)
        self.assertEqual(repaired, text)
        self.assertEqual(count, 0)
        json.loads(repaired)

    def test_literal_hdl_identifier_escapes(self):
        text = r'{"badnets":["\program_store.i_sram/\A_DOUT[0]"]}'
        repaired, count = repair_identifier_escapes(text)
        self.assertEqual(count, 2)
        self.assertEqual(json.loads(repaired)['badnets'],
                         [r'\program_store.i_sram/\A_DOUT[0]'])

    def test_invalid_unicode_identifier_escape(self):
        repaired, count = repair_identifier_escapes(r'{"pin":"\uio_out[0]"}')
        self.assertEqual(count, 1)
        self.assertEqual(json.loads(repaired)['pin'], r'\uio_out[0]')

    def test_report_retains_original_and_mismatch_data(self):
        text = r'[{"nets":[5259,5272],"badnets":["\program_store.i_sram"],"pins":[["VPWR"],["VGND"]]}]'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'lvs.netgen.json'
            path.write_text(text)
            self.assertEqual(repair_report(path), 1)
            self.assertEqual(path.with_suffix('.json.original').read_text(), text)
            report = json.loads(path.read_text())[0]
            self.assertEqual(report['nets'], [5259, 5272])
            self.assertEqual(report['pins'], [['VPWR'], ['VGND']])
            self.assertEqual(report['badnets'], [r'\program_store.i_sram'])
            self.assertEqual(repair_report(path), 0)

    def test_structurally_invalid_report_still_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'lvs.netgen.json'
            for text in (r'{"pin":"\broken",}', '{"nets": [1,2]'):
                path.write_text(text)
                with self.assertRaises(json.JSONDecodeError):
                    repair_report(path)
                self.assertEqual(path.read_text(), text)
