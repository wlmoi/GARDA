"""Exercise the foundry macro's masks, clocked reads and enable semantics."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SRAMTests(unittest.TestCase):
    def simulate(self, body, instance, extra_sources=()):
        self.assertTrue(shutil.which("iverilog") and shutil.which("vvp"))
        with tempfile.TemporaryDirectory(prefix="protocol-sram-") as directory:
            p = Path(directory)
            (p / "tb.v").write_text("`timescale 1ns/1ps\nmodule tb;\n" + instance +
                                    "\ninitial begin\n" + body +
                                    '\n$display("PASS"); $finish; end\nendmodule\n')
            sources = [ROOT / "test/ihp_sram/RM_IHPSG13_1P_core_behavioral_bm_bist.v",
                       ROOT / "test/ihp_sram/RM_IHPSG13_1P_256x16_c2_bm_bist.v", *extra_sources]
            compiled = subprocess.run(["iverilog", "-g2012", "-DSIM", "-DFUNCTIONAL",
                                       f"-I{ROOT / 'src'}", "-s", "tb", "-o", str(p / "sim"),
                                       str(p / "tb.v"), *map(str, sources)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run(["vvp", str(p / "sim")], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS", result.stdout)

    def test_macro_partial_mask_enable_and_output_hold(self):
        self.simulate('''
            #1; tick();
            wen=0; ren=1; tick(); if(q!==16'hA55A) $fatal(1,"full word");
            wen=1; ren=0; bm=16'h00F0; d=16'h0030; tick();
            if(q!==16'hA55A) $fatal(1,"write-only must hold output");
            wen=0; ren=1; tick(); if(q!==16'hA53A) $fatal(1,"bit mask");
            men=0; wen=1; d=0; bm=16'hFFFF; tick();
            if(q!==16'hA53A) $fatal(1,"disabled output");
            men=1; wen=0; tick(); if(q!==16'hA53A) $fatal(1,"disabled write");
            addr=0; ren=0; tick(); if(q!==16'hA53A) $fatal(1,"read disabled");
        ''', '''
            reg clk=0, men=1, wen=1, ren=0;
            reg [7:0] addr=255;
            reg [15:0] d=16'hA55A, bm=16'hFFFF;
            wire [15:0] q;
            RM_IHPSG13_1P_256x16_c2_bm_bist memory(
              .A_CLK(clk), .A_MEN(men), .A_WEN(wen), .A_REN(ren),
              .A_ADDR(addr), .A_DIN(d), .A_BM(bm), .A_DLY(1'b1), .A_DOUT(q),
              .A_BIST_CLK(1'b0), .A_BIST_EN(1'b0), .A_BIST_MEN(1'b0),
              .A_BIST_WEN(1'b0), .A_BIST_REN(1'b0), .A_BIST_ADDR(8'd0),
              .A_BIST_DIN(16'd0), .A_BIST_BM(16'd0));
            task tick; begin #5; clk=1; #5; clk=0; end endtask
        ''')

    def test_wrapper_byte_preservation_read_edge_and_reset_retention(self):
        self.simulate('''
            #1; tick(); high=1; d=8'hA5; tick();
            we=0; tick(); if(q!==16'hA55A) $fatal(1,"byte ordering");
            we=1; high=0; d=8'h3C; tick(); we=0; tick();
            if(q!==16'hA53C) $fatal(1,"opposite byte preserved");
            addr=0; if(q!==16'hA53C) $fatal(1,"read must await falling edge");
            addr=255; rst_n=0; tick(); if(q!==16'hA53C) $fatal(1,"disabled memory");
            rst_n=1; tick(); if(q!==16'hA53C) $fatal(1,"reset retains program");
        ''', '''
            reg clk=1, rst_n=1, we=1, high=0;
            reg [7:0] addr=255, d=8'h5A;
            wire [15:0] q;
            program_memory memory(.clk(clk), .rst_n(rst_n), .address(addr),
              .write_enable(we), .high_byte(high), .write_data(d), .read_data(q));
            task tick; begin #5; clk=0; #5; clk=1; end endtask
        ''', [ROOT / "src/program_memory.v"])
