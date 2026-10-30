"""Reproduce Parallel8 simulations and export unmodified native GTKWave images.

Only copied testbenches are instrumented. Accepted RTL and ROMs are read-only.
"""
from pathlib import Path
import bisect, csv, hashlib, html, importlib.util, json, re, shutil, struct, subprocess, zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
FPGA = ROOT / 'fpga'
SRC = FPGA / 'experiments/parallel8'
OUT = FPGA / 'evidence/parallel8_wave_proof'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def run_simulations(suites=('board','core','uart')):
    OUT.mkdir(parents=True, exist_ok=True)
    acceptance = json.loads((SRC/'artifacts/acceptance.json').read_text())
    hashes = acceptance['sha256']
    # Bind the production sources, benches, banks and independent golden files.
    bound = [p for p in hashes if p.endswith(('.v','.sv','.mem','.hex','.qsf','.sdc','.tcl'))]
    for p in bound:
        assert sha(FPGA/p) == hashes[p], f'Accepted input drift: {p}'
    prior=OUT/'simulation_receipt.json'
    results = json.loads(prior.read_text())['suites'] if prior.exists() else {}
    for suite in suites:
        dest = OUT/suite
        dest.mkdir(exist_ok=True)
        (dest/'artifacts').mkdir(exist_ok=True)
        for bank in SRC.glob('bank*.mem'): shutil.copy2(bank,dest/bank.name)
        top = 'tb_board_wrapper' if suite=='board' else f'tb_src_policy_{suite}'
        original = SRC/f'{top}.sv'
        tb = original.read_text()
        tb = tb.replace('../../verification/src_policy/artifacts/', (FPGA/'verification/src_policy/artifacts').as_posix()+'/')
        if suite=='board':
            tb=tb.replace('integer received=0,', 'reg [7:0] decoded_byte=0;\n integer received=0,')
            tb=tb.replace('response[received]=monitored_byte;', 'response[received]=monitored_byte;decoded_byte=monitored_byte;')
            # Scalar scope dumps exclude the large ROM and observation arrays.
            tb = tb.replace('$dumpvars(1,dut.policy);', '$dumpvars(1,dut.policy);\n'
                '$dumpvars(1,dut.policy.receiver);$dumpvars(1,dut.policy.transmitter);\n'
                '$dumpvars(1,dut.policy.core);\n' + '\n'.join(
                f'$dumpvars(1,dut.policy.core.lane{i});$dumpvars(1,dut.policy.core.lane{i}.activation);' for i in range(8)))
        (dest/f'{top}.sv').write_text(tb)
        sources = [SRC/'igor_src_policy_core.v']
        if suite!='core': sources += [FPGA/'rtl/igor_src_policy/igor_src_policy_uart.v', FPGA/'rtl/igor_uart_rx.v', FPGA/'rtl/igor_uart_tx.v']
        if suite=='board': sources += [SRC/'igor_src_policy_de10_nano.v']
        sources += [dest/f'{top}.sv']
        commands = [
            ['C:/iverilog/bin/iverilog.exe','-g2012','-s',top,'-DVECTOR_COUNT=236','-DACTIVATION_COUNT=8364','-o',str(dest/'simulation.vvp'),*map(str,sources)],
            ['C:/iverilog/bin/vvp.exe',str(dest/'simulation.vvp')]]
        for label,cmd in zip(['compile','simulation'],commands):
            r=subprocess.run(cmd,cwd=dest,capture_output=True,text=True,timeout=600)
            (dest/f'{label}.log').write_text(r.stdout+r.stderr)
            assert r.returncode==0, (suite,label,r.stdout,r.stderr)
        assert f'PASS {suite}' in r.stdout
        results[suite]={'commands':commands,'testbench_original_sha256':sha(original),
                        'instrumented_testbench_sha256':sha(dest/f'{top}.sv'),'result':r.stdout.strip()}
        print(r.stdout.strip(),flush=True)
    sof=FPGA/'bitstreams/igor_src_policy_parallel8.sof'
    assert sha(sof)=='cb2e0de357a3865b4058f89d34b54f59ab8604db0865a7ceefff436bd6230b49'
    for p in bound: assert sha(FPGA/p)==hashes[p]
    receipt={'scope':'RTL simulation, not oscilloscope/SignalTap hardware measurement',
             'sof_sha256':sha(sof),'accepted_inputs_sha256':{p:hashes[p] for p in bound},'suites':results}
    (OUT/'simulation_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')

class Wave:
    def __init__(self,path):
        self.path=path; self.names={}; self.events={}; stack=[]; t=0
        with path.open() as f:
            for line in f:
                p=line.split()
                if p[:1]==['$scope']: stack.append(p[2])
                elif p[:1]==['$upscope']: stack.pop()
                elif p[:1]==['$var']: self.names['.'.join(stack+[p[4]])]=(p[3],int(p[2]),p[5] if p[1]!='integer' and p[5].startswith('[') else '')
                elif p[:1]==['$enddefinitions']: break
            codes={v[0] for v in self.names.values()}
            for line in f:
                if line.startswith('#'): t=int(line[1:])
                elif line[:1] in '01xXzZ' and line.strip():
                    code=line[1:].strip(); bits=line[0]
                    if code in codes:self.events.setdefault(code,[]).append((t,bits))
                elif line.startswith(('b','B')):
                    p=line.split()
                    if len(p)==2:self.events.setdefault(p[1],[]).append((t,p[0][1:]))
    def series(self,name): return self.events[self.names[name][0]]
    def value(self,name,t,signed=False):
        values=self.series(name); i=bisect.bisect_right(values,(t,'~'))-1
        bits=values[i][1]
        if any(x in bits.lower() for x in 'xz'):return None
        v=int(bits,2); w=self.names[name][1]
        return v-(1<<w) if signed and v&(1<<(w-1)) else v
    def transitions(self,name,value=None):
        return [t for t,b in self.series(name) if not any(x in b.lower() for x in 'xz') and (value is None or int(b,2)==value)]

def capture_views(only=None):
    images=OUT/'images'; images.mkdir(exist_ok=True)
    rc=OUT/'proof.gtkwaverc'
    rc.write_text('hide_sst yes\nhier_max_level 0\nfontname_signals Monospace 11\nfontname_waves Monospace 11\n')
    b=Wave(OUT/'board/artifacts/board.vcd')
    c=Wave(OUT/'core/core.vcd'); u=Wave(OUT/'uart/uart.vcd')
    B='tb_board_wrapper.'; P=B+'dut.policy.'; C=P+'core.'; U='tb_src_policy_uart.'
    views=[]
    def add(name,w,start,end,marker,signals,title,explanation,rtl,markers=()):
        assert start<=marker<=end
        for s in signals: assert s in w.names,s
        views.append(dict(name=name,wave=w,start=int(start),end=int(end),marker=int(marker),signals=signals,
                          title=title,explanation=explanation,rtl=rtl,markers=markers))
    def sig(prefix,names): return [prefix+s for s in names.split()]
    # Derive every important time from the VCD, rather than assume screenshots show it.
    start=b.transitions(C+'busy',1)[0]; done=b.transitions(C+'done',1)[0]
    assert done-start==6916*20000
    accept=b.transitions(P+'accepted_frames',1)[0]
    tx=b.transitions(P+'tx_send',1)[:11]
    assert len(tx)==11
    wire_bytes=[]
    for t in tx:
        wire_start=t+20000
        assert b.value(B+'tx',wire_start+540000)==0
        value=sum(b.value(B+'tx',wire_start+1620000+i*1080000)<<i for i in range(8))
        assert b.value(B+'tx',wire_start+10260000)==1
        assert value==b.value(P+'tx_data',t)
        wire_bytes.append(value)
    assert wire_bytes[:4]==[0x5a,0xa5,2,6]
    crc=0
    for byte in wire_bytes[2:10]:
        crc^=byte
        for _ in range(8):crc=(crc>>1)^0x8c if crc&1 else crc>>1
    assert crc==wire_bytes[-1]
    outputs=[int.from_bytes(bytes(wire_bytes[i:i+2]),'little',signed=True) for i in (4,6,8)]
    golden=[int(x,16) for x in (FPGA/'verification/src_policy/artifacts/expected.hex').read_text().split()[3:6]]
    assert outputs==[v-65536 if v&32768 else v for v in golden]==[-57,76,42]
    # Independent arithmetic checks at the first MAC edge for all eight lanes.
    mac=b.transitions(C+'state',6)[0]; arithmetic=[]
    for lane in range(8):
        pre=b.value(C+f'lane{lane}.acc',mac+1,True)
        weight=b.value(C+f'lane{lane}.data',mac+1,True)
        operand=b.value(C+'operand',mac+1,True)
        post=b.value(C+f'lane{lane}.acc',mac+20001,True)
        assert post==pre+weight*operand
        arithmetic.append(dict(lane=lane,before=pre,weight=weight,operand=operand,after=post))
    loaded=b.value(C+'loaded',start-1)
    assert loaded==(1<<74)-1
    mac_times=[t for t in b.transitions(C+'state',6) if start<t<done]
    activation_times=[t for t in b.transitions(C+'state',7) if start<t<done]
    assert len(mac_times)==16*74+8*128+64==2272
    assert len(activation_times)==16+8+1==25
    banks=[[int(x,16) for x in (SRC/f'bank{i}.mem').read_text().split()] for i in range(8)]
    for t in mac_times:
        operand=b.value(C+'operand',t+1,True); address=b.value(C+'address',t+1)
        for lane in range(8):
            weight=b.value(C+f'lane{lane}.data',t+1,True)
            word=banks[lane][address]; expected_weight=word-65536 if word&32768 else word
            assert weight==expected_weight
            pre=b.value(C+f'lane{lane}.acc',t+1,True)
            post=b.value(C+f'lane{lane}.acc',t+20001,True)
            assert post==pre+operand*weight
    add('01_reset',b,0,350000,151000,sig(B,'clk key')+sig(B+'dut.','reset_sync rst_n stop_active stop_latched permit error_code')+sig(B,'tx led'),
        'Reset: asynchronous assertion, release after two clocks',
        'KEY=2 means KEY0 is held low while KEY1 is released. KEY becomes 3 at 120 ns; reset_sync progresses 0 → 1 → 3 at 130/150 ns. rst_n releases at 150 ns, after two rising edges. TX is idle high; permit and error_code remain zero. This prevents a false E-stop at a clean boot.',
        ['experiments/parallel8/igor_src_policy_de10_nano.v:11','rtl/igor_src_policy/igor_src_policy_uart.v:137'],[(120000,'KEY0'),(150000,'RST_N')])
    rx_start=b.transitions(B+'rx',0)[0]
    assert [b.value(B+'rx',rx_start+1620000+i*1080000) for i in range(8)]==[0,1,0,1,1,0,1,0]
    bitmarks=[(rx_start+540000,'START=0')]+[(rx_start+1620000+i*1080000,f'D{i}={v}') for i,v in enumerate([0,1,0,1,1,0,1,0])]+[(rx_start+10260000,'STOP=1')]
    add('02_rx_exact_bits',b,rx_start-100000,rx_start+11000000,rx_start+10260000,
        sig(B,'rx')+sig(P+'receiver.','meta sync state bit_index count shift data valid error'),
        'RX: exact 0x5A, LSB first, 8N1',
        'Read the named sample markers left to right: start 0; data D0..D7 = 0,1,0,1,1,0,1,0; stop 1. That is 0x5A. Each bit lasts 54 × 20 ns = 1080 ns. The receiver validates the start at half a bit, samples data once per bit, and pulses valid only after a high stop bit. data becomes 5A; error stays 0.',
        ['rtl/igor_uart_rx.v:8'],bitmarks)
    add('03_rx_synchronizer',b,rx_start-40000,rx_start+180000,rx_start+70000,
        sig(B,'clk rx')+sig(P+'receiver.','meta sync state count'),
        'RX clock crossing: two sampled registers',
        'The falling RX edge is followed by meta and then sync on successive 50 MHz rising edges. The state machine reads sync, not the asynchronous pin. This is the intended synchronizer structure; a digital RTL simulation does not model analog metastability or prove its MTBF.',
        ['rtl/igor_uart_rx.v:7'])
    add('04_crc_acceptance',b,accept-13000000,accept+1800000,accept+1,
        sig(P,'uart_rx rx_valid rx_data position crc invalid_observation accepted_frames mode core_load core_start core_busy'),
        'Only the final correct CRC accepts the 153-byte request',
        'Before the CRC, position is 152 (0x98): 4 header bytes + 148 payload bytes have arrived. accepted_frames and core_busy are still zero. When rx_valid carries the matching CRC, accepted_frames rises once and mode changes RX(0) → LOAD(1). The board bench also explicitly asserts that a partial header and a complete payload without CRC cannot start inference.',
        ['rtl/igor_src_policy/igor_src_policy_uart.v:170','experiments/parallel8/tb_board_wrapper.sv:78'],[(accept,'ACCEPT_CRC')])
    add('05_load_then_start',b,start-280000,start+180000,start-1,
        sig(B,'clk')+sig(P,'mode core_load core_input_index core_input_value core_start core_busy')+sig(C,'loaded state'),
        'All 74 inputs are loaded before start',
        'At the marker, loaded is 74 ones. core_input_index reaches 73 (0x49) with core_load asserted. The controller then drops core_load and pulses core_start; busy rises on the following sampling edge. The core rejects incomplete loads or simultaneous start/load, so no neuron runs on a partial observation.',
        ['rtl/igor_src_policy/igor_src_policy_uart.v:193','experiments/parallel8/igor_src_policy_core.v:577'],[(start-20000,'START'),(start,'BUSY')])
    add('06_latency_layers',b,start-5000000,done+8000000,done+1,
        sig(P,'core_start core_busy core_done core_fault core_latency')+sig(C,'layer neuron k state')+sig(P,'response_valid'),
        'Parallel8 inference: 6916 cycles = 138.32 µs',
        'BUSY and DONE markers are exactly 138,320 ns apart: 6916 clocks at 50 MHz. layer advances 0 → 1 → 2. neuron advances by eight for 16 groups in layer 0 and 8 groups in layer 1; only the first three lanes are committed in layer 2. fault remains zero. done is a level held until a new load/reset/abort, not a one-cycle pulse.',
        ['experiments/parallel8/igor_src_policy_core.v:593'],[(start,'BUSY'),(done,'DONE_6916')])
    add('07_rom_bias_mac',b,start-40000,start+400000,mac+20001,
        sig(B,'clk')+sig(C,'state address weight_address operand k')+sig(C+'lane0.','data acc')+sig(C+'lane1.','data acc'),
        'Synchronous ROM and bias alignment before MAC',
        'Core states 1/2/3 are BIAS_ADDRESS/WAIT/TAKE; 4/5/6 are WEIGHT_ADDRESS/WAIT/MAC. ROM data updates on a rising edge after address is registered. WAIT prevents use of the previous ROM word. BIAS_TAKE initializes each 40-bit accumulator to signed_bias << 8; each MAC then adds signed_operand × signed_weight. Eight independent bank*.mem files provide eight weights at the same address.',
        ['experiments/parallel8/igor_src_policy_core.v:74','experiments/parallel8/igor_src_policy_core.v:602'],[(mac,'MAC'),(mac+20000,'ACC')])
    add('08_eight_lanes',b,mac-80000,mac+200000,mac+20001,
        sig(B,'clk')+sig(C,'state k operand')+[C+f'lane{i}.acc' for i in range(8)],
        'Eight accumulators update on the same edge',
        'At ACC_UPDATE all eight lane accumulators commit in parallel. The accompanying arithmetic table independently checks each after = before + operand × weight from the VCD. MAC repeats every three clocks because WEIGHT_ADDRESS and WEIGHT_WAIT precede each MAC. Parallel8 means eight neurons share one input operand and use different weights; it does not mean eight input samples per clock.',
        ['experiments/parallel8/igor_src_policy_core.v:62'],[(mac+20000,'ALL_8_UPDATE')])
    act=b.transitions(C+'state',7)[0]
    add('09_relu_group',b,act-100000,act+140000,act+20001,
        sig(B,'clk')+sig(C,'state layer neuron k')+[C+f'lane{i}.activation.value' for i in range(8)],
        'Hidden layer: activate and store eight neurons per group',
        'After k=73 has been accumulated, state ACTIVATE(7) commits one Q8.8 activation per lane, then neuron changes 0 → 8 and the next group begins. Activation uses arithmetic floor(acc/256), ReLU to zero for negatives, and saturation at 32767 for hidden outputs. The full core regression compares every one of 128 + 64 hidden values against an independent integer model, not just the three final outputs.',
        ['experiments/parallel8/igor_src_policy_core.v:6','experiments/parallel8/igor_src_policy_core.v:84','experiments/parallel8/tb_src_policy_core.sv:112'],[(act+20000,'STORE_8')])
    for layer,oldk,oldneuron in [(1,73,120),(2,127,56)]:
        t=b.transitions(C+'layer',layer)[0]
        add(f'10_layer{layer}_transition',b,t-150000,t+230000,t+1,
            sig(B,'clk')+sig(C,'state layer neuron k input_count output_count bias_base address weight_address operand'),
            f'Layer {layer-1} → {layer}: correct dimensions and bank offsets',
            f'Before the transition, k={oldk} and the final group starts at neuron={oldneuron}. ACTIVATE advances layer and resets neuron. Layer 1 consumes 128 hidden1 values for 64 neurons, with weight_address starting at 1200; layer 2 consumes 64 hidden2 values for 3 outputs, starting at 2232. Bias bases are 1184, 2224, 2296. These addresses refer to each lane bank, not the original unbanked ROM.',
            ['experiments/parallel8/igor_src_policy_core.v:55','experiments/parallel8/igor_src_policy_core.v:626'],[(t,f'LAYER_{layer}')])
    add('11_capture_q88',b,done-100000,done+180000,done+80001,
        sig(B,'clk')+sig(P,'core_done mode core_output_index core_output_value sample0 sample1 sample2 response_crc result_valid response_valid safety_permit'),
        'Capture three ordered Q8.8 values before constructing CRC',
        'CAP0/CAP1/CAP2 read outputs 0/1/2 on successive clocks, giving raw signed [-57, 76, 42] = [-0.22265625, 0.296875, 0.1640625]. All three match golden vector 1. Only after sample2 is captured does result_valid rise and response_valid pulse. response_crc is 0F. safety_permit here means a valid policy residual; this design has no motor-driver enable output.',
        ['rtl/igor_src_policy/igor_src_policy_uart.v:200'],[(done,'CORE_DONE'),(done+80000,'RESULT_VALID')])
    add('12_tx_full_packet',b,tx[0]-7000000,tx[-1]+11500000,tx[-1]+10820000,
        sig(P,'uart_tx tx_send tx_busy tx_data tx_index mode response_valid safety_permit')+sig(B,'decoded_byte received'),
        'TX: exactly 11 bytes with independent wire decoding',
        'The response on the wire is 5A A5 02 06 C7 FF 4C 00 2A 00 0F. C7 FF = -57, 4C 00 = 76, 2A 00 = 42, in little-endian signed Q8.8. Eleven tx_send pulses produce eleven complete 8N1 bytes; received reaches 11. The monitor decodes the pin without reusing the DUT receiver, and independently checks header, numerical results and CRC.',
        ['rtl/igor_src_policy/igor_src_policy_uart.v:212','experiments/parallel8/tb_board_wrapper.sv:12'],[(tx[0]+20000,'BYTE_0_5A'),(tx[-1]+20000,'BYTE_10_CRC')])
    ts=tx[0]+20000
    add('13_tx_exact_bits',b,ts-80000,ts+11000000,ts+10260000,
        sig(P+'transmitter.','send data busy bit_index count shift tx'),
        'TX zoom: start, all eight bits and full stop bit',
        'The 10-bit shift register is {stop=1, data=0x5A, start=0}; shift[0] drives TX. Named markers show the same 0x5A LSB-first sequence as RX. Each bit is exactly 1080 ns. At 50 MHz, the rounded divider 54 produces 925925.93 baud, +0.4694% relative to nominal 921600. The separately recorded nominal-baud audit passes as well; this screenshot uses an exact-divider host.',
        ['rtl/igor_uart_tx.v:9'],[(ts+540000,'START=0')]+[(ts+1620000+i*1080000,f'D{i}={v}') for i,v in enumerate([0,1,0,1,1,0,1,0])]+[(ts+10260000,'STOP=1')])
    add('14_tx_final_stop',b,tx[-1]+9000000,tx[-1]+11300000,tx[-1]+10840001,
        sig(B,'clk tx received')+sig(P,'mode tx_send tx_busy tx_index')+sig(P+'transmitter.','bit_index count'),
        'Do not return to RX until the CRC stop bit finishes',
        'After the last send the mode progresses TX_START_LAST(8) → TX_END_LAST(9), waits for tx_busy to fall after ten full bits, and only then returns to RX(0). tx_send is one clock wide and TX requires both !tx_busy and !tx_send; this avoids duplicate bytes caused by the registered busy handshake. The stop bit remains high for its complete 54 clocks.',
        ['rtl/igor_src_policy/igor_src_policy_uart.v:212','rtl/igor_src_policy/igor_src_policy_uart.v:232'])
    stop=1949003000
    assert b.value(B+'dut.stop_active',stop)==1 and b.value(B+'dut.permit',stop)==0
    add('15_estop_immediate',b,stop-100000,stop+220000,stop+1,
        sig(B,'clk key')+sig(B+'dut.','stop_active stop_sync stop_latched permit a0 a1 a2 error_code rejected')+sig(B,'tx led'),
        'KEY1: immediate gating between clocks, then logged once',
        'KEY1 falls at 1,949,003 ns, between rising clock edges. stop_active immediately rises and all three gated residuals plus permit become zero in the same simulation timestamp; TX returns to idle high. On the following rising edge stop_latched sets; error_code becomes 1, error_flags bit 1 is recorded, and rejected increments once. This is an asynchronous inhibition path followed by synchronous bookkeeping.',
        ['experiments/parallel8/igor_src_policy_de10_nano.v:24','rtl/igor_src_policy/igor_src_policy_uart.v:155'],[(stop,'KEY1_STOP')])
    add('16_estop_latched',b,1948900000,1950500000,1950351000,
        sig(B,'key')+sig(B+'dut.','stop_active stop_latched permit error_code error_flags accepted rejected a0 a1 a2'),
        'Releasing KEY1 does not restart the design',
        'Even when KEY returns to 3, stop_latched and stop_active remain high, all residual outputs remain zero, and rejected stays at 1 rather than incrementing each held clock. A new valid packet while latched is not accepted (separate checkpoint at 3,606,192 ns). KEY0 reset is required to clear the latch and fault history.',
        ['experiments/parallel8/igor_src_policy_de10_nano.v:24','experiments/parallel8/tb_board_wrapper.sv:89'])
    add('17_key0_clears',b,5522380000,5522520000,5522461000,
        sig(B,'clk key')+sig(B+'dut.','rst_n reset_sync stop_latched permit error_code error_flags accepted rejected a0 a1 a2')+sig(B,'tx'),
        'KEY0 clears result, counters and history asynchronously',
        'Before KEY0 assertion the post-reset transaction has again returned the correct result. At 5,522,460 ns KEY0 falls; reset_sync and rst_n immediately clear, permit and all outputs become zero, and accepted/error history clear. A separate held-KEY1 boot case is recorded as a real stop exactly once, rather than mistaken for a clean boot.',
        ['experiments/parallel8/igor_src_policy_de10_nano.v:11','experiments/parallel8/tb_board_wrapper.sv:98'])
    # Independent activation unit cases: pick a compact group around the zero boundary.
    ac='tb_src_policy_core.'
    add('18_activation_edges',c,0,4000,2500,
        sig(ac,'activation_accumulator activation_output activation_value activation_saturated'),
        'Activation arithmetic: floor, ReLU and output clipping',
        'Each 1 ns step is an independent combinational activation test, not an inference clock. At the signed 40-bit minimum (-549755813888), hidden output is zero and output-layer value clips to -256. At the maximum (+549755813887), hidden value saturates to 32767 with saturated=1, while the output layer clips to +256. The regression exercises 8364 activation cases before network inference begins.',
        ['experiments/parallel8/igor_src_policy_core.v:6','experiments/parallel8/tb_src_policy_core.sv:98'])
    add('18b_floor_relu',c,64000,82000,75500,
        sig(ac,'activation_accumulator activation_output activation_value activation_saturated'),
        'Negative fractions floor before hidden ReLU',
        'At accumulator=-257 the output-layer result is -2, because arithmetic floor(-257/256)=-2. At -1 the output-layer result is -1, while the hidden-layer result is 0 after ReLU. At accumulator=0 or 1 the scaled value is zero. This proves signed arithmetic floor rather than truncation toward zero. Each test step is 1 ns; it is combinational stimulus.',
        ['experiments/parallel8/igor_src_policy_core.v:13'],[(65500,'FLOOR_MINUS_2'),(75500,'FLOOR_MINUS_1')])
    add('18c_hidden_saturation',c,158000,164000,162500,
        sig(ac,'activation_accumulator activation_output activation_value activation_saturated'),
        'Hidden saturation threshold is exact',
        'With output_layer=0, accumulator=8388607 scales to 32767 without saturation; 8388608 scales to 32768 and is clamped to 32767 with saturated=1. Switching output_layer=1 gives +256 and clears this hidden-saturation flag. Output clipping and hidden saturation are deliberately different operations.',
        ['experiments/parallel8/igor_src_policy_core.v:13'],[(162500,'HIDDEN_SATURATES')])
    rows=list(csv.DictReader((OUT/'uart/uart_checkpoints.csv').open()))
    common=sig(U,'test_id uart_rx uart_tx error_code error_flags safety_permit action0 action1 action2 accepted_frames rejected_frames')+sig(U+'dut.','core_abort mode')
    for name,test,code,title,text_ in [
        ('19_bad_crc',2,6,'CRC mismatch rejects without a success reply','The complete payload has a deliberately corrupted CRC. error_code becomes 6, error_flags gains bit 6, rejected rises once, accepted stays zero, core_abort asserts and all residuals remain zero. No success response is transmitted.'),
        ('20_framing',7,2,'A low stop bit is a framing error','The test drives a low stop bit. rx_error causes error 2 and rejection; it cannot be interpreted as a valid data byte or a successful policy response.'),
        ('21_interbyte_timeout',6,7,'A stalled partial frame is discarded','A header plus one payload byte is followed by a stall. At the test threshold of 256 clocks (5.12 µs), the parser rejects with error 7, resets position and aborts the transaction. Production uses 1,000,000 clocks = 20 ms.'),
        ('22_busy_reject',13,9,'Bytes during inference cannot corrupt the active calculation','A new byte is deliberately received during RUN. Error 9 aborts the in-flight calculation and cancels transmission; no valid residual escapes. This interface requires one complete request/response at a time.'),
        ('23_result_lease',15,11,'A result expires and the residual gate returns to zero','The good result is valid first. At the test lease of 100,000 clocks (2 ms), error 11 invalidates the old residual and all three outputs become zero without emitting a fresh successful packet. Production RESULT_TIMEOUT_CYCLES is 1,000,000 clocks (20 ms).'),
        ('24_inference_watchdog',20,12,'A missing done signal cannot leave RUN stuck forever','The testbench deliberately forces core_done=0. At the test watchdog of 60,000 clocks (1.2 ms), error 12 aborts RUN and leaves the residual gate zero. This is fault injection, not a naturally observed core failure; production timeout is 100,000 clocks (2 ms).'),
        ('25_internal_fault',21,10,'An internal core fault also closes the gate','The bench forces core_fault=1 while RUN is active. Error 10 rejects the transaction and cancels its response. This view is a deliberate fault-injection test of the wrapper.'),
    ]:
        row=next(r for r in rows if int(r['test_id'])==test and r['event']=='rejected_zero_guard')
        t=int(row['time_ps'])-1
        error_times=[x for x in u.transitions(U+'error_code',code) if x<=t]
        edge=error_times[-1]
        radius=160000 if code not in (7,11,12) else 400000
        extra={6:'rx_valid rx_data crc position',2:'rx_error rx_valid',7:'rx_timer position',9:'core_busy rx_valid',11:'result_timer result_valid',12:'infer_timer core_done',10:'core_fault'}[code]
        add(name,u,edge-radius,edge+radius,edge+1,common+sig(U+'dut.',extra),title,
            text_+' This UART protocol bench uses 8 clocks per serial bit (160 ns in simulation); it proves logic/fault behavior, not production 921600-baud timing.',
            ['rtl/igor_src_policy/igor_src_policy_uart.v:121','rtl/igor_src_policy/igor_src_policy_uart.v:164'],[(edge,f'ERROR_{code}')])
    row=next(r for r in rows if r['event']=='accepted_counter_saturates')
    t=int(row['time_ps'])-1
    add('26_counter_saturation',u,t-25000000,t,t-1,
        sig(U,'test_id accepted_frames rejected_frames error_flags response_valid safety_permit action0 action1 action2'),
        'Counters saturate rather than wrap through zero',
        'The testbench seeds accepted_frames near 0xFFFFFFFF, then completes valid transactions. The counter reaches its maximum and remains there on the next accepted request; outputs still update correctly. Rejected-counter CRC/E-stop saturation and reset recovery are also asserted in the CSV/log. The seeded value is fault-injection acceleration, not billions of transactions run in real time.',
        ['rtl/igor_src_policy/igor_src_policy_uart.v:175','experiments/parallel8/tb_src_policy_uart.sv:224'])
    # Save facts before rendering, allowing the explanations to be audited separately.
    facts={'busy_start_ps':start,'done_ps':done,'latency_cycles':6916,'tx_bytes_hex':' '.join(f'{x:02X}' for x in wire_bytes),
           'outputs_raw_q8_8':outputs,'first_mac_arithmetic':arithmetic,
           'loaded_mask_before_start_hex':hex(loaded),'checked_rx_byte':0x5a,'checked_tx_bytes':11,
           'checked_mac_updates_all_lanes':len(mac_times)*8,'checked_banked_rom_weights':len(mac_times)*8,'checked_activation_groups':len(activation_times)}
    (OUT/'checked_wave_facts.json').write_text(json.dumps(facts,indent=2)+'\n')
    manifests=[]
    for v in views:
        if only and v['name']!=only:continue
        stem=images/v['name']; wave=v['wave']; names=[]; formats=[]
        for s in v['signals']:
            # Explicit aliases keep the eight lane identities visible at any width.
            label=s.split('dut.policy.')[-1] if 'dut.policy.' in s else s.split('tb_src_policy_uart.')[-1].split('tb_src_policy_core.')[-1]
            if label.startswith('tb_board_wrapper.'):label=label[len('tb_board_wrapper.'):]
            label=label.replace('core.lane','L').replace('core.','core_').replace('.','_')
            if label.startswith('activation_'): label=label.replace('activation_','act_')
            if label=='act_output':label='act_output_layer'
            leaf=s.rsplit('.',1)[-1]
            signed=leaf in ['acc','accumulator','scaled','operand','input_value','core_input_value','core_output_value','output_value','value','activation_accumulator','activation_value','action0','action1','action2','a0','a1','a2','sample0','sample1','sample2']
            if '.lane' in s and leaf=='data': signed=True
            byte=leaf in ['rx_data','tx_data','data','shift','crc','response_crc','monitored_byte','decoded_byte','error_flags','loaded'] and not signed
            radix='@22' if byte else ('@420' if signed else '@24')
            formats.append((16 if byte else 10,signed))
            # GTKWave 3.3.100 uses the legacy +alias syntax (no braces).
            names += [radix, '+'+label+' '+s+wave.names[s][2]]
        save=stem.with_suffix('.gtkw')
        save.write_text('[size] 1480 720\n[pos] 0 0\n[sst_width] 160\n[signals_width] 370\n[timestart] 0\n'+'\n'.join(names)+'\n')
        png=stem.with_suffix('.png'); tcl=stem.with_suffix('.tcl')
        cmds=[f'gtkwave::setZoomRangeTimes {v["start"]} {v["end"]}',f'gtkwave::setMarker {v["marker"]}']
        for letter,(t,label) in zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ',v['markers']):
            cmds.append(f'gtkwave::setNamedMarker {letter} {int(t)} "{label}"')
        cmds += ['gtkwave::nop', 'gtkwave::nop',f'puts "DISPLAYED [gtkwave::getDisplayedSignals]"']
        for i in range(len(v['signals'])):cmds.append(f'puts "VALUE {i} [gtkwave::getTraceValueAtMarkerFromIndex {i}]"')
        cmds += ['gtkwave::nop',f'gtkwave::/File/Grab_To_File {{{png.as_posix()}}}','gtkwave::/File/Quit']
        tcl.write_text('if {[catch {\n'+'\n'.join(cmds)+'\n} err]} {puts stderr $err; exit 1}\n')
        cmds.insert(0,f'if {{[llength [gtkwave::getDisplayedSignals]] != {len(v["signals"])}}} {{error "Missing displayed trace"}}')
        tcl.write_text('if {[catch {\n'+'\n'.join(cmds)+'\n} err]} {puts stderr $err; exit 1}\n')
        cmd=['C:/iverilog/gtkwave/bin/gtkwave.exe','-r',str(rc),'-S',str(tcl),str(wave.path),str(save)]
        r=subprocess.run(cmd,cwd=OUT,capture_output=True,text=True,timeout=60)
        stem.with_suffix('.log').write_text(r.stdout+r.stderr)
        assert r.returncode==0 and png.read_bytes().startswith(b'\x89PNG'),(v['name'],r.stderr)
        shown={int(i):value.strip() for i,value in re.findall(r'^VALUE (\d+) (.*)$',r.stdout,re.M)}
        assert len(shown)==len(v['signals'])
        marker_values={}
        for i,s in enumerate(v['signals']):
            base,signed=formats[i]
            expected=wave.value(s,v['marker'],signed)
            assert expected is not None, (v['name'],s,'unknown marker value')
            assert int(shown[i],base)==expected,(v['name'],s,shown[i],expected)
            marker_values[s]=expected
        item={k:val for k,val in v.items() if k!='wave'}
        item.update(waveform=str(wave.path.relative_to(OUT)),waveform_sha256=sha(wave.path),image=f'images/{png.name}',image_sha256=sha(png),command=cmd,gtkwave_marker_values_match_vcd=True,checked_marker_values=marker_values)
        manifests.append(item)
        print('CAPTURED',v['name'],flush=True)
    if not only:
        (OUT/'screenshots.json').write_text(json.dumps(manifests,indent=2)+'\n')
        write_report(manifests,facts)
        verify_and_package()

def verify_and_package():
    receipt=json.loads((OUT/'simulation_receipt.json').read_text())
    for path,digest in receipt['accepted_inputs_sha256'].items():assert sha(FPGA/path)==digest,path
    assert sha(FPGA/'bitstreams/igor_src_policy_parallel8.sof')==receipt['sof_sha256']
    views=json.loads((OUT/'screenshots.json').read_text())
    assert len(views)==29
    for v in views:
        assert v['gtkwave_marker_values_match_vcd']
        assert sha(OUT/v['image'])==v['image_sha256']
        assert sha(OUT/v['waveform'])==v['waveform_sha256']
        width,height=struct.unpack('>II',(OUT/v['image']).read_bytes()[16:24])
        assert width>=1400 and height>=700,(v['name'],width,height)
    index=(OUT/'index.html').read_text(encoding='utf-8')
    for target in re.findall(r'(?:src|href)="([^"]+)"',index):
        if not target.startswith(('#','http')):assert (OUT/target).is_file(),target
    subprocess.run(['python',str(OUT/'open_wave.py'),'--list'],capture_output=True,check=True)
    validation={'verified_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS','screenshots':len(views),
                'all_png_and_vcd_hashes_match':True,'all_gtkwave_marker_values_match_vcd':True,
                'accepted_inputs_and_sof_unchanged':True,'gallery_local_links_exist':True,
                'interactive_viewer_list_command_passes':True,'renderer':'GTKWave 3.3.100 native Grab_To_File, unmodified',
                'reproduction_script_sha256':sha(Path(__file__))}
    (OUT/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    archive=OUT.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(OUT.rglob('*')):
            if path.is_file() and path.name not in ['review.tcl','interactive.tcl']:
                z.write(path,Path(OUT.name)/path.relative_to(OUT))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print(f'PASS: {len(views)} verified screenshots; archive {archive.stat().st_size:,} bytes',flush=True)

def write_report(views,facts):
    intro='''# Parallel8: RTL explained with native GTKWave evidence

These are unmodified GTKWave exports of fresh Icarus RTL simulations using the accepted Parallel8 sources and eight weight banks. They are not oscilloscope or SignalTap measurements of the board. The user reports that Parallel8 works on hardware; this package independently explains and checks its digital behavior.

The active design is **50 MHz, nominal UART 921600 baud, 8N1, signed Q8.8**. It is the original Parallel8 image, not the 9600-baud variant. SOF SHA256: `cb2e0de357a3865b4058f89d34b54f59ab8604db0865a7ceefff436bd6230b49`.

## Why the design fulfills its purpose

A complete, CRC-correct 74-element observation is accepted once; all 74 words load before inference starts. Eight banked ROM/MAC lanes compute the 74→128→64→3 integer network, completing in **6916 clocks / 138.32 µs**. Three independently verified Q8.8 residuals are captured in order, CRC-protected, and sent as **exactly 11 serial bytes**. Faults cancel the transaction and gate the residuals to zero. `safety_permit` is residual validity, not a motor-enable signal.

The request layout is `5A A5 01 94` + 148 payload bytes + one CRC byte: **153 bytes** total. Every observation is signed int16 little-endian; raw/256 gives its Q8.8 value. LiDAR fields 0–63 must be raw 0…256; fields 64–73 must be -256…256. CRC-8/MAXIM uses reflected polynomial 0x8C, starts at zero and covers opcode, length and payload (not the two synchronization bytes).

For each neuron, `acc = (signed_bias << 8) + Σ(signed_input × signed_weight)`, with a signed 40-bit accumulator and 16 fractional bits. Activation floors `acc/256` back to Q8.8. Each group takes 3 bias cycles + 3 cycles per input + 1 activation cycle. Therefore **16×(3+74×3+1) + 8×(3+128×3+1) + (3+64×3+1) = 6916 clocks**. This explains both the observed latency and why eight neurons finish together.

The independent monitor's `decoded_byte` changes only when a high stop bit commits a byte, and `received` increments with that commit. Its internal shift-assembly values are not shown as completed packets. On a real Jetson, UART reads can return different chunk sizes because the serial interface is a byte stream; software must assemble the 11-byte reply and check its header/CRC.

For the board test's **golden vector 1**, raw outputs are **[-57, 76, 42]**, and the response is **5A A5 02 06 C7 FF 4C 00 2A 00 0F**. This is a different input from the earlier synthetic 0.8 example, whose [-46,60,34] result must not be substituted here.

## Which RTL is actually exercised

| Active module | Purpose | Wave views |
|---|---|---|
| `igor_src_policy_de10_nano` | Clock/reset release, latched KEY1 E-stop, LED status and UART policy instance | 01, 15–17 |
| `igor_uart_rx` | Synchronize RX, validate start/stop and reconstruct LSB-first byte | 02–03, 20 |
| `igor_src_policy_uart` | Header/domain/CRC validation, load/start, result capture, TX handshake, validity/timeout/fault bookkeeping | 04–05, 11–17, 19–26 |
| `igor_src_policy_core` | Eight banked synchronous ROMs, eight signed MACs, layer scheduling and output masking | 05–10 |
| `igor_src_policy_activation` | Arithmetic scaling, hidden ReLU/saturation and output clipping | 09, 18 |

The QSF also lists `rtl/igor_src_policy/igor_src_policy_rom.v`, but **the Parallel8 core does not instantiate that module**. Its synchronous ROM behavior is implemented inside lane0…lane7. It would be incorrect to claim a waveform proves execution of the unused unbanked ROM module. Other FPGA experiments/planners in the repository are not part of this configured image.

## Fresh regression results and evidence limits

* Core: **236 network vectors, 8364 activation cases, 54399 assertions**. All 192 hidden activations and all three outputs are checked for every network vector.
* UART: **184 directed transactions, 268 assertions**, including all 74 observation-field domain boundaries, CRC/framing, busy rejection, E-stop, timeouts, watchdog, counter saturation and reset recovery.
* Production board wrapper: **18 checkpoints**, with real 50 MHz / 54-clocks-per-bit framing, independently decoded response, raw KEY1 inhibition and KEY0 recovery.
* Accepted source/bench/ROM/golden-file hashes are checked before and after the run. Only copied testbench file paths, waveform dump scopes and a passive monitor probe are changed. See `simulation_receipt.json`, each suite's `simulation.log`, and `checked_wave_facts.json`.
* The copied board monitor also exposes a passive `decoded_byte` probe at byte commit. It does not change any DUT logic. For every image, **GTKWave's own values at the primary marker are compared against the VCD**, including signed/hexadecimal display formats; results are saved in `screenshots.json` and each image log.
* Views 19–26 use the accelerated protocol testbench: **8 clocks / 160 ns per serial bit**, with shortened timeout parameters. Their captions give production equivalents. They do not establish production baud timing. Views 01–17 use the production board wrapper.
* Domain-boundary tests are asserted in the UART log/CSV but deliberately not dumped during that long sweep; no nonexistent domain-boundary waveform is claimed. Busy/fault/abort masking, incomplete-load rejection and recovery are also asserted by the core regression.
* RTL waves do not establish analog signal integrity, electrical voltage levels, metastability MTBF, physical pin connectivity or post-route timing. The accepted Quartus build separately reports 8 DSP blocks, minimum setup slack +5.647 ns and minimum hold slack +0.119 ns at 50 MHz. Raising frequency would require a new constrained build and UART divider review; these waves prove only this configuration.

## How to read and reopen the evidence

Click each PNG for full resolution. Signed numerical signals use decimal; byte/CRC/shift/error-mask/loaded-mask buses use hexadecimal. Named vertical markers identify exact bit centers or commit edges. X values before the first reset edge are initialization, not accepted outputs. A screenshot is a selected example; the assertions and checked facts establish the broader claims.

Each image has matching `.gtkw`, `.tcl`, and `.log` files in `images/`. Reopen with GTKWave and the corresponding VCD path recorded in `screenshots.json`; use the `.tcl` to restore the exact zoom and markers. To reproduce everything from the workspace root:

```powershell
python tools/build_parallel8_wave_proof.py
```

To open an interactive viewer at the exact bit zoom (also works after extracting the evidence ZIP):

```powershell
python fpga/evidence/parallel8_wave_proof/open_wave.py 13_tx_exact_bits
python fpga/evidence/parallel8_wave_proof/open_wave.py 08_eight_lanes
```

Use `--list` to list all views; use `--gtkwave /path/to/gtkwave` on another computer. Zoom, pan and move markers normally in GTKWave. The opener restores each view's original signals, zoom range and named markers. Rendering uses GTKWave's native Tcl API; signal data formats follow the [GTKWave save-file format documented by PyVCD](https://pyvcd.readthedocs.io/en/latest/vcd.gtkw.html).

## Eight-lane arithmetic cross-check

At the first MAC update, the script checks every lane directly from the VCD. Accumulators have 16 fractional bits before activation; values below are signed raw integers.

| Lane | Before | Operand | Weight | Before + operand × weight = after |
|---|---:|---:|---:|---:|
'''
    for r in facts['first_mac_arithmetic']:
        intro+=f'| {r["lane"]} | {r["before"]} | {r["operand"]} | {r["weight"]} | {r["after"]} |\n'
    intro+='\nBeyond this small table, the VCD checker verifies **all 18,176 MAC accumulator updates and banked ROM weights** during the first inference, and checks its **25 activation groups**. See `checked_wave_facts.json`.\n'
    md=intro+'\n## Screenshot walkthrough\n\n'
    cards=[]
    for v in views:
        refs='; '.join(f'`fpga/{x}`' for x in v['rtl'])
        md+=f'### {v["name"]}: {v["title"]}\n\n![{v["title"]}]({v["image"]})\n\n{v["explanation"]}\n\nRTL: {refs}. Window: {v["start"]/1000:g}–{v["end"]/1000:g} ns; marker: {v["marker"]/1000:g} ns.\n\n'
        cards.append(f'<section id="{v["name"]}"><h2>{html.escape(v["name"]+": "+v["title"])}</h2><p>{html.escape(v["explanation"])}</p><a href="{v["image"]}"><img loading="lazy" src="{v["image"]}" alt="{html.escape(v["title"])}"></a><p class="ref">RTL: {html.escape(refs)}<br>Window {v["start"]/1000:g}–{v["end"]/1000:g} ns; marker {v["marker"]/1000:g} ns.</p></section>')
    (OUT/'README.md').write_text(md,encoding='utf-8')
    (OUT/'open_wave.py').write_text('''"""Open an evidence view interactively with its original zoom and markers."""
from pathlib import Path
import argparse, json, shutil, subprocess, sys
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='replace')
here=Path(__file__).resolve().parent
views=json.loads((here/'screenshots.json').read_text())
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('view',nargs='?',default='08_eight_lanes')
p.add_argument('--list',action='store_true')
p.add_argument('--gtkwave',default=shutil.which('gtkwave') or 'C:/iverilog/gtkwave/bin/gtkwave.exe')
args=p.parse_args()
if args.list:
    for v in views:print(v['name'],v['title'])
    raise SystemExit(0)
v=next((v for v in views if v['name']==args.view),None)
if v is None:p.error('Unknown view; use --list')
script=here/'interactive.tcl'
cmds=[f'gtkwave::setZoomRangeTimes {v["start"]} {v["end"]}',f'gtkwave::setMarker {v["marker"]}']
for letter,(t,label) in zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ',v['markers']):
    cmds.append(f'gtkwave::setNamedMarker {letter} {t} "{label}"')
script.write_text('\\n'.join(cmds)+'\\n')
subprocess.Popen([args.gtkwave,'-r',str(here/'proof.gtkwaverc'),'-S',str(script),str(here/v['waveform']),str(here/'images'/f'{v["name"]}.gtkw')],cwd=here)
''',encoding='utf-8')
    nav=' · '.join(f'<a href="#{v["name"]}">{v["name"]}</a>' for v in views)
    (OUT/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Parallel8 — GTKWave proof</title><style>body{font:17px/1.6 system-ui;background:#eef2f5;color:#142333;margin:0}main{max-width:1640px;margin:auto;padding:24px}h1{font-size:36px}section,.intro{background:white;padding:24px;margin:26px 0;border-radius:10px}img{width:100%;height:auto}a{color:#075cac}.ref,nav{font-size:14px}nav{line-height:2}code{overflow-wrap:anywhere}@media print{section{break-inside:avoid}nav{display:none}}</style><main><h1>Parallel8: actual GTKWave proof</h1><div class="intro"><p><b>50 MHz · nominal 921600 baud · 8N1 · signed Q8.8 · 8 MAC lanes</b></p><p>Fresh RTL simulation evidence, exported by GTKWave without image editing. These are simulation traces, not hardware scope/SignalTap captures.</p><p><b>PASS:</b> 236 network vectors / 54399 core assertions; 184 UART transactions / 268 assertions; 18 production board checkpoints. Inference: 6916 clocks = 138.32 µs. Response: 11 independently decoded bytes.</p><p>Read <a href="README.md">the full report</a> for active RTL scope, unused ROM clarification, arithmetic table, coverage limits and reproduction. <a href="checked_wave_facts.json">Checked facts</a> · <a href="simulation_receipt.json">Simulation receipt</a> · <a href="screenshots.json">Image hashes and exact commands</a>.</p><p>Board vector 1: [-57,76,42] raw Q8.8; response <b>5A A5 02 06 C7 FF 4C 00 2A 00 0F</b>. Views 19–26 use an accelerated protocol bench; captions state the timing differences. Residual validity is not motor permission.</p><nav>'+nav+'</nav></div>'+''.join(cards)+'</main></html>',encoding='utf-8')

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('--captures-only',action='store_true'); parser.add_argument('--board-only',action='store_true'); parser.add_argument('--only'); args=parser.parse_args()
    if not args.captures_only:run_simulations(('board',) if args.board_only else ('board','core','uart'))
    capture_views(args.only)
