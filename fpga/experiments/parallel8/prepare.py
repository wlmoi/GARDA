"""Generate an isolated eight-neuron parallel candidate from the accepted baseline."""
from pathlib import Path
import hashlib
import json
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RTL = ROOT / 'rtl/igor_src_policy'
(HERE/'artifacts').mkdir(exist_ok=True)
words = (RTL/'policy_weights.mem').read_text().split()
for lane in range(8):
    bank = []
    for rows, cols, wbase, bbase in [(128,74,0,9472),(64,128,9600,17792),(3,64,17856,18048)]:
        groups = (rows+7)//8
        for group in range(groups):
            neuron = group*8+lane
            bank.extend(words[wbase+neuron*cols:wbase+(neuron+1)*cols] if neuron<rows else ['0000']*cols)
        bank.extend(words[bbase+group*8+lane] if group*8+lane<rows else '0000' for group in range(groups))
    assert len(bank)==2297
    (HERE/f'bank{lane}.mem').write_text('\n'.join(bank+['0000']*(4096-len(bank)))+'\n')
text = (RTL/'igor_src_policy_core.v').read_text()
text = text.replace('reg signed [39:0] accumulator;', 'reg signed [39:0] accumulator [0:7];\n    integer lane;')
begin = text.index('    reg [14:0] address, weight_address;')
end = text.index('    assign output_value', begin)
text = text[:begin]+'''    reg [11:0] address, weight_address;
    wire [7:0] input_count = layer==0 ? 8'd74 : (layer==1 ? 8'd128 : 8'd64);
    // neuron is the base index of an eight-neuron group.
    wire [7:0] output_count = layer==0 ? 8'd128 : (layer==1 ? 8'd64 : 8'd3);
    wire [11:0] bias_base = layer==0 ? 12'd1184 : (layer==1 ? 12'd2224 : 12'd2296);
    wire signed [15:0] weight [0:7];
    wire signed [31:0] product [0:7];
    wire signed [39:0] mac_sum [0:7];
    wire signed [15:0] activated [0:7];
    wire [7:0] activation_saturated;
    genvar g;
    generate for(g=0;g<8;g=g+1) begin: lanes
        localparam BANK_FILE = g==0 ? "bank0.mem" : g==1 ? "bank1.mem" :
          g==2 ? "bank2.mem" : g==3 ? "bank3.mem" : g==4 ? "bank4.mem" :
          g==5 ? "bank5.mem" : g==6 ? "bank6.mem" : "bank7.mem";
        (* ramstyle = "M10K" *) reg [15:0] memory [0:4095];
        reg signed [15:0] data;
        initial $readmemh(BANK_FILE,memory);
        always @(posedge clk) data <= memory[address];
        assign weight[g] = data;
        assign product[g] = operand * weight[g];
        assign mac_sum[g] = accumulator[g] + {{8{product[g][31]}},product[g]};
        igor_src_policy_activation activation(accumulator[g],layer==2,
                                               activated[g],activation_saturated[g]);
    end endgenerate
''' + text[end:]
text = text.replace('accumulator<=0;', 'for(lane=0;lane<8;lane=lane+1) accumulator[lane]<=0;')
text = text.replace('address<=bias_base+neuron;', 'address<=bias_base+(neuron>>3);')
text = text.replace('accumulator<={{16{weight[15]}},weight,8\'d0};', "for(lane=0;lane<8;lane=lane+1)\n                        accumulator[lane]<={{16{weight[lane][15]}},weight[lane],8'd0};")
text = text.replace('accumulator<=mac_sum;', 'for(lane=0;lane<8;lane=lane+1) accumulator[lane]<=mac_sum[lane];')
text = text.replace('if (activation_saturated) saturated<=1;', 'if (|activation_saturated) saturated<=1;')
text = text.replace('if (layer==0) hidden1[neuron]<=activated;\n                    else if (layer==1) hidden2[neuron]<=activated;\n                    else actions[neuron]<=activated;', '''for(lane=0;lane<8;lane=lane+1) begin
                        if (layer==0) hidden1[neuron+lane]<=activated[lane];
                        else if (layer==1) hidden2[neuron+lane]<=activated[lane];
                        else if(lane<3) actions[lane]<=activated[lane];
                    end''')
text = text.replace("neuron==output_count-1'b1", "neuron+8>=output_count")
text = text.replace("15'd9600 : 15'd17856", "12'd1200 : 12'd2232")
text = text.replace("neuron<=neuron+1'b1", "neuron<=neuron+8")
# Bank hidden storage physically too: eight writes into one inferred array
# make elaboration unnecessarily expensive. Each lane has one write port.
text=text.replace('reg signed [15:0] hidden1 [0:127];','wire signed [15:0] hidden1 [0:127];')
text=text.replace('reg signed [15:0] hidden2 [0:63];','wire signed [15:0] hidden2 [0:63];')
text=text.replace('        reg signed [15:0] data;', '''        reg signed [15:0] data;
        reg signed [15:0] h1 [0:15];
        reg signed [15:0] h2 [0:7];
        genvar n;
        for(n=0;n<16;n=n+1) begin: h1_view
            assign hidden1[n*8+g]=h1[n];
        end
        for(n=0;n<8;n=n+1) begin: h2_view
            assign hidden2[n*8+g]=h2[n];
        end
        always @(posedge clk) begin
            if(rst_n && !abort && !fault && !load_input && !start && state==ACTIVATE) begin
                if(layer==0) h1[neuron[6:3]]<=activated[g];
                if(layer==1) h2[neuron[5:3]]<=activated[g];
            end
        end''')
text=text.replace('if (layer==0) hidden1[neuron+lane]<=activated[lane];\n                        else if (layer==1) hidden2[neuron+lane]<=activated[lane];\n                        else if(lane<3) actions[lane]<=activated[lane];',
                  'if(layer==2 && lane<3) actions[lane]<=activated[lane];')
text=text.replace('reg signed [39:0] accumulator [0:7];\n    integer lane;', 'wire signed [39:0] accumulator [0:7];')
text=text.replace('        reg signed [15:0] data;', '''        reg signed [15:0] data;
        reg signed [39:0] acc;
        assign accumulator[g]=acc;
        always @(posedge clk or negedge rst_n) begin
            if(!rst_n) acc<=0;
            else if(!abort && !fault && !load_input && !start) begin
                if(state==BIAS_TAKE) acc<={{16{weight[g][15]}},weight[g],8'd0};
                else if(state==MAC) acc<=mac_sum[g];
            end
        end''')
text=text.replace('for(lane=0;lane<8;lane=lane+1) accumulator[lane]<=0;', '')
text=text.replace("for(lane=0;lane<8;lane=lane+1)\n                        accumulator[lane]<={{16{weight[lane][15]}},weight[lane],8'd0};", '')
text=text.replace('for(lane=0;lane<8;lane=lane+1) accumulator[lane]<=mac_sum[lane];', '')
text=text.replace('for(lane=0;lane<8;lane=lane+1) begin\n                        if(layer==2 && lane<3) actions[lane]<=activated[lane];\n                    end',
'''if(layer==2) begin
                        actions[0]<=activated[0];
                        actions[1]<=activated[1];
                        actions[2]<=activated[2];
                    end''')
# Emit literal lane scopes instead of nested genvar loops. This is a static
# source expansion, not extra pipeline stages or a changed numerical schedule.
import re
begin=text.index('    genvar g;')
end=text.index('    end endgenerate',begin)+len('    end endgenerate')
body=text[text.index('begin: lanes',begin)+len('begin: lanes'):text.index('    end endgenerate',begin)]
body=body.replace('        genvar n;\n','')
body=re.sub(r'        for\(n=0;n<16;n=n\+1\) begin: h1_view\n.*?        end',
            '\n'.join(f'        assign hidden1[{n}*8+g]=h1[{n}];' for n in range(16)),body,flags=re.S)
body=re.sub(r'        for\(n=0;n<8;n=n\+1\) begin: h2_view\n.*?        end',
            '\n'.join(f'        assign hidden2[{n}*8+g]=h2[{n}];' for n in range(8)),body,flags=re.S)
expanded='    generate\n'+''.join('    begin: lane'+str(i)+re.sub(r'\bg\b',str(i),body)+'    end\n' for i in range(8))+'    endgenerate'
text=text[:begin]+expanded+text[end:]
(HERE/'igor_src_policy_core.v').write_text(text)
# Same numerical and fault assertions, with only the declared scheduling contract changed.
for suite in ['core','uart']:
    tb = (ROOT/f'verification/src_policy/tb_src_policy_{suite}.sv').read_text().replace('54348','6916')
    tb = tb.replace('verification/src_policy/artifacts/', '')
    # Read independent golden inputs through explicit paths; write candidate evidence locally.
    import re
    tb = re.sub(r'\$readmemh\("([^"/]+)"', r'$readmemh("../../verification/src_policy/artifacts/\1"',tb)
    (HERE/f'tb_src_policy_{suite}.sv').write_text(tb)
tb=(ROOT/'verification/tb_board_wrapper.sv').read_text().replace('54348','6916')
tb=tb.replace('../../evidence/current_board_wrapper/','artifacts/')
(HERE/'tb_board_wrapper.sv').write_text(tb)
board = ROOT/'fpga_de10_nano/src_policy'
for name in ['igor_src_policy.qpf','igor_src_policy.sdc','pin_assignment.tcl','igor_src_policy_de10_nano.v']:
    (HERE/name).write_bytes((board/name).read_bytes())
qsf = (board/'igor_src_policy.qsf').read_text()
qsf = qsf.replace('../../rtl/igor_src_policy/igor_src_policy_core.v','igor_src_policy_core.v')
(HERE/'igor_src_policy.qsf').write_text(qsf)
manifest = {'expected_cycles':6916,'latency_ms_at_50mhz':0.13832,
            'scope':'Isolated candidate; not substituted for baseline',
            'baseline_sha256':hashlib.sha256((RTL/'igor_src_policy_core.v').read_bytes()).hexdigest()}
(HERE/'candidate.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Prepared candidate: 8 MAC lanes, 6916 cycles, 138.32 us at 50 MHz')
