"""Compare exact MAC input activity against a committed RTL baseline.

The counters use the complete pin-wrapper regression and independent oracle.
They measure registered MAC input Hamming transitions, not power in watts.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['garda_neural_logic_top.v', 'garda_parameter_logic.v',
           'garda_neural_datapath_logic.v', 'garda_activation_logic.v']
MONITOR = r'''`timescale 1ns/1ps
module neural_activity;
parameter ASSERT_ISOLATION=0;
reg [31:0] previous_weights=0,previous_operands=0;
reg [31:0] current_weights,current_operands;
integer weight_transitions=0,operand_transitions=0,zero_lanes=0,mac_lanes=0;
function integer popcount(input [31:0] value);
integer i;begin popcount=0;for(i=0;i<32;i=i+1)popcount=popcount+value[i];end
endfunction
always @(posedge tb.clk) begin
 #2;
 current_weights={{(16-$bits(tb.dut.neural.weight1_q)){tb.dut.neural.weight1_q[$bits(tb.dut.neural.weight1_q)-1]}},tb.dut.neural.weight1_q,
                  {(16-$bits(tb.dut.neural.weight0_q)){tb.dut.neural.weight0_q[$bits(tb.dut.neural.weight0_q)-1]}},tb.dut.neural.weight0_q};
 current_operands={tb.dut.neural.operand1_q,tb.dut.neural.operand0_q};
 if(tb.rst_n && tb.dut.busy)begin
  if(ASSERT_ISOLATION && ((tb.dut.neural.operand0_q==0)!=(tb.dut.neural.weight0_q==0) ||
                         (tb.dut.neural.operand1_q==0)!=(tb.dut.neural.weight1_q==0)))
   $fatal(1,"zero MAC factor failed to isolate the other input");
  weight_transitions=weight_transitions+popcount(current_weights^previous_weights);
  operand_transitions=operand_transitions+popcount(current_operands^previous_operands);
  if(tb.dut.neural.state==4) begin
   mac_lanes=mac_lanes+2;
   if(tb.dut.neural.operand0_q==0)zero_lanes=zero_lanes+1;
   if(tb.dut.neural.operand1_q==0)zero_lanes=zero_lanes+1;
  end
 end
 previous_weights=current_weights;previous_operands=current_operands;
end
final $display("ACTIVITY weight_bit_transitions=%0d activation_bit_transitions=%0d zero_lanes=%0d sampled_lanes=%0d",weight_transitions,operand_transitions,zero_lanes,mac_lanes);
endmodule
'''


def run(command):
    return subprocess.run(command, cwd=ROOT, check=True, text=True,
                          capture_output=True, timeout=600).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-ref', required=True,
                        help='Committed pre-optimization source revision')
    parser.add_argument('--report', default='evidence/neural_logic_activity.json')
    args = parser.parse_args()
    commit = run(['git', 'rev-parse', args.baseline_ref + '^{commit}']).strip()
    build = ROOT / 'verification/build/neural_logic_activity'
    build.mkdir(parents=True, exist_ok=True)
    monitor = build / 'activity_monitor.v'
    monitor.write_text(MONITOR)
    sys.path.insert(0, str(ROOT / 'reference_model'))
    from neural_reference import infer, read_mem
    inputs = read_mem('test_inputs.mem')
    expected = []
    for index in range(100):
        values, fault = infer(inputs[index * 24:index * 24 + 24])
        assert not fault
        expected.extend(values)
    oracle = build / 'independent_expected.hex'
    oracle.write_text(''.join(f'{value & 65535:04x}\n' for value in expected))
    testbench = build / 'tb_neural_logic.v'
    original = (ROOT / 'asic/neural_logic/tb_neural_logic.v').read_text()
    testbench.write_text(original.replace(
        'verification/build/neural_logic/independent_expected.hex',
        oracle.relative_to(ROOT).as_posix()))
    assert len(expected) == 400
    metrics = {}
    source_hashes = {}
    for name in ['baseline', 'current']:
        directory = build / name
        directory.mkdir(exist_ok=True)
        for filename in SOURCES:
            source = run(['git', 'show', commit + ':src/' + filename]) if name == 'baseline' else (ROOT / 'src' / filename).read_text()
            (directory / filename).write_text(source)
        source_hashes[name] = hashlib.sha256(b''.join(
            (directory / filename).read_bytes() for filename in SOURCES)).hexdigest()
        executable = directory / 'simulation.out'
        run([shutil.which('iverilog') or 'C:/iverilog/bin/iverilog.exe',
             '-g2012', '-s', 'tb', '-s', 'neural_activity',
             '-Pneural_activity.ASSERT_ISOLATION=' + ('1' if name == 'current' else '0'),
             '-o', str(executable)]
            + [str(directory / filename) for filename in SOURCES]
            + [str(testbench), str(monitor)])
        log = run([shutil.which('vvp') or 'C:/iverilog/bin/vvp.exe', str(executable)])
        (directory / 'simulation.log').write_text(log)
        assert 'PASS full neural logic:' in log, log
        assert '100 vectors/400 outputs, 3080 cycles' in log, log
        match = re.search(r'ACTIVITY weight_bit_transitions=(\d+) activation_bit_transitions=(\d+) zero_lanes=(\d+) sampled_lanes=(\d+)', log)
        assert match, log
        metrics[name] = dict(zip(['weight_bit_transitions', 'activation_bit_transitions',
                                 'zero_lanes', 'sampled_lanes'], map(int, match.groups())))
        print(name + ': ' + match.group(0), flush=True)
    before = sum(metrics['baseline'][key] for key in ['weight_bit_transitions', 'activation_bit_transitions'])
    after = sum(metrics['current'][key] for key in ['weight_bit_transitions', 'activation_bit_transitions'])
    assert after < before, (before, after)
    report = {
        'status': 'PASS', 'baseline_commit': commit, 'source_sha256': source_hashes,
        'vectors_per_revision': 100, 'outputs_checked_per_revision': 400,
        'model_words': 6020, 'latency_cycles_before': 3080, 'latency_cycles_after': 3080,
        'reference_clock_hz': 50000000, 'reference_inference_us': 61.6,
        'coefficient_range': [-1205, 640], 'coefficient_bits_before': 16,
        'coefficient_bits_after': 12, 'activation_bits': 16, 'accumulator_bits': 40,
        'metrics': metrics, 'combined_bit_transitions_before': before,
        'combined_bit_transitions_after': after,
        'combined_bit_transition_reduction_percent': round((before - after) * 100 / before, 4),
        'qualification': 'RTL MAC input switching proxy normalized to sign-extended 16-bit signals on supplied vectors, not power in watts, timing signoff or a global minimum; includes directed overflow and guard traffic',
        'physical_power_measured': False,
    }
    target = ROOT / args.report
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: same 400 oracle outputs per revision; active MAC input transitions decreased ' +
          str(report['combined_bit_transition_reduction_percent']) + '%')


if __name__ == '__main__':
    main()
