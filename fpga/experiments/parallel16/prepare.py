"""Generate an isolated sixteen-lane GARDA policy core and banked model."""
from pathlib import Path
import hashlib
import json

here = Path(__file__).resolve().parent
root = here.parents[2]
baseline = root / 'fpga/experiments/parallel8/garda_src_policy_core.v'
model = root / 'fpga/rtl/garda_src_policy/policy_weights.mem'
if not model.is_file():
    model = root / 'rtl/garda_src_policy/policy_weights.mem'
words = model.read_text().split()
if len(words) != 32768:
    raise ValueError('Expected the complete 32768-word policy memory image')
for lane in range(16):
    bank = []
    for rows, cols, wbase, bbase in [(128,74,0,9472), (64,128,9600,17792), (3,64,17856,18048)]:
        groups = (rows + 15)//16
        for group in range(groups):
            neuron = group*16 + lane
            bank.extend(words[wbase+neuron*cols:wbase+(neuron+1)*cols] if neuron < rows else ['0000']*cols)
        bank.extend(words[bbase+group*16+lane] if group*16+lane < rows else '0000' for group in range(groups))
    assert len(bank) == 1181
    (here/f'bank{lane}.mem').write_text('\n'.join(bank+['0000']*(2048-len(bank)))+'\n', newline='\n')
source = baseline.read_text()
start = source.index('    generate\n')
end = source.index('    endgenerate', start)+len('    endgenerate')
prefix, suffix = source[:start], source[end:]
changes = [
    ('accumulator [0:7]', 'accumulator [0:15]'),
    ('reg [11:0] address, weight_address;', 'reg [10:0] address, weight_address;'),
    ('eight-neuron group', 'sixteen-neuron group'),
    ("wire [11:0] bias_base = layer==0 ? 12'd1184 : (layer==1 ? 12'd2224 : 12'd2296);", "wire [10:0] bias_base = layer==0 ? 11'd592 : (layer==1 ? 11'd1112 : 11'd1180);"),
    ('weight [0:7]', 'weight [0:15]'), ('product [0:7]', 'product [0:15]'),
    ('mac_sum [0:7]', 'mac_sum [0:15]'), ('activated [0:7]', 'activated [0:15]'),
    ('wire [7:0] activation_saturated;', 'wire [15:0] activation_saturated;'),
]
for old, new in changes:
    if old not in prefix: raise ValueError(f'Parallel8 prefix changed: {old}')
    prefix = prefix.replace(old,new)
for old,new in [('neuron>>3','neuron>>4'), ('neuron+8>=output_count','neuron+16>=output_count'),
                ("12'd1200 : 12'd2232", "11'd600 : 11'd1116"), ('neuron<=neuron+8','neuron<=neuron+16')]:
    if old not in suffix: raise ValueError(f'Parallel8 schedule changed: {old}')
    suffix=suffix.replace(old,new)
lanes = ['    generate\n']
for i in range(16):
    h1 = ''.join(f'        assign hidden1[{n}*16+{i}]=h1[{n}];\n' for n in range(8))
    h2 = ''.join(f'        assign hidden2[{n}*16+{i}]=h2[{n}];\n' for n in range(4))
    lanes.append(f"""    begin: lane{i}
        (* ramstyle = "M10K" *) reg [15:0] memory [0:2047];
        reg signed [15:0] data;
        reg signed [39:0] acc;
        reg signed [15:0] h1 [0:7];
        reg signed [15:0] h2 [0:3];
        wire active = layer != 2 || {i} < 3;
        assign accumulator[{i}] = acc;
{h1}{h2}        initial $readmemh("bank{i}.mem",memory);
        always @(posedge clk) begin
            if(active) data <= memory[address];
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:4]] <= activated[{i}];
                if(layer==1) h2[neuron[5:4]] <= activated[{i}];
            end
        end
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(active && !abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{{{16{{weight[{i}][15]}}}},weight[{i}],8'd0}};
                else if(state==MAC) acc<=mac_sum[{i}];
            end
        end
        assign weight[{i}] = data;
        assign product[{i}] = active ? operand * weight[{i}] : 32'sd0;
        assign mac_sum[{i}] = accumulator[{i}] + {{{{8{{product[{i}][31]}}}},product[{i}]}};
        garda_src_policy_activation activation(accumulator[{i}],layer==2,
                                               activated[{i}],activation_saturated[{i}]);
    end
""")
lanes.append('    endgenerate')
(here/'garda_src_policy_core.v').write_text(prefix+''.join(lanes)+suffix, newline='\n')
(here/'candidate.json').write_text(json.dumps({'lane_count':16,'model_words':18051,
    'bank_count':16,'bank_depth':2048,'bank_used_words':1181,'expected_cycles':3556,
    'scope':'isolated candidate; not a routed or physical hardware result',
    'hash_format':'SHA-256 of text with CRLF normalized to LF',
    'model_sha256':hashlib.sha256(model.read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
    'baseline_core_sha256':hashlib.sha256(baseline.read_bytes().replace(b'\r\n', b'\n')).hexdigest()},indent=2)+'\n', newline='\n')
print('Generated Parallel16 core with 16 banks and 3556-cycle schedule')
