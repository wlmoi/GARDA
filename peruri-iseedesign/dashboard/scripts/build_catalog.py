from pathlib import Path
import re, json, hashlib

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parent

def ref(path,line=1):
    return {'path':path,'line':line}

def parse_file(path):
    text=(REPO/path).read_text(encoding='utf-8-sig')
    result=[]
    for match in re.finditer(r'\bmodule\s+(\w+)\s*',text):
        end=text.index(';',match.end())
        header=text[match.end():end]
        if header.lstrip().startswith('#'):
            start=header.index('(')
            depth=1
            for i in range(start+1,len(header)):
                if header[i]=='(':depth+=1
                elif header[i]==')':depth-=1
                if depth==0:
                    header=header[i+1:]
                    break
        header=header[header.index('(')+1:header.rfind(')')]
        direction=''; width=1; signed=False; ports=[]
        for decl in header.split(','):
            decl=decl.strip()
            m=re.match(r'(input|output|inout)\b(.*)',decl,re.S)
            if m:
                direction=m.group(1); decl=m.group(2).strip(); signed=bool(re.search(r'\bsigned\b',decl))
                rng=re.search(r'\[(\d+)\s*:\s*(\d+)\]',decl)
                width=abs(int(rng.group(1))-int(rng.group(2)))+1 if rng else 1
                decl=re.sub(r'\[[^\]]+\]','',decl)
                decl=re.sub(r'\b(wire|reg|signed|unsigned)\b','',decl).strip()
            name=re.match(r'\w+',decl)
            if name:
                ports.append({'name':name.group(),'direction':direction,'bits':width,'signed':signed})
        result.append({'module':match.group(1),'file':path,'source':ref(path,text.count('\n',0,match.start())+1),'ports':ports,'sha256':hashlib.sha256((REPO/path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()})
    return result

desc={
 'igor_uart_top':('Antarmuka FPGA','Top board DE10-Nano','Menyinkronkan reset dan switch, menerjemahkan opcode UART ke DWA dan neural, lalu menampilkan status LED.','host',['igor_uart_protocol','igor_top','igor_neural_core','igor_neural_rom'],['UART 115200 8N1','Opcode 8 membaca ROM','Opcode 9 membaca siklus DWA','Opcode 10/11 memuat dan memulai neural','Opcode 12/13 membaca hasil dan siklus neural','Opcode 14 membaca kode v dan omega']),
 'igor_uart_protocol':('Protokol UART','Framing dan CRC8','Menerima paket 8 byte, memvalidasi CRC8 polinomial 0x07, mengeluarkan opcode 8 bit dan payload 32 bit, lalu membalas snapshot 32 bit.','host',['igor_uart_rx','igor_uart_tx'],['Request A5 OP DATA[31:0] CRC 5A','Response 5A OP DATA[31:0] CRC A5','Data little-endian','Fault pada frame error, CRC salah atau timeout']),
 'igor_uart_rx':('Penerima UART','Serial menjadi byte','Menyinkronkan RX dan mengambil satu byte 8 bit dengan sampling di tengah bit serta pemeriksaan stop bit.','host',[],['434 clock per bit pada 50 MHz','8N1','Flag valid dan error']),
 'igor_uart_tx':('Pengirim UART','Byte menjadi serial','Menggeser byte 8 bit ke TX dengan start bit dan stop bit, disertai sinyal busy.','host',[],['LSB first','8N1','434 clock per bit']),
 'igor_top':('Pengendali DWA','Planner empat tile','FSM IDLE, RUN, RESULT, FAULT mengelola konfigurasi, peta, empat rollout, pemilihan kandidat, deadline dan gerbang keluaran.','control',['igor_config_registers','igor_costmap_manager','igor_costmap_bank','igor_rollout_tile','igor_best_candidate_selector','igor_safety_security_gate','igor_status_logger'],['4 evaluator paralel','512 kandidat total','Gerbang satu-satunya penggerak tiga output command','Result lease dan map freshness default 1.000.000 siklus']),
 'igor_config_registers':('Konfigurasi terkunci','Batas gerak','Memuat konfigurasi 32 bit, memeriksa versi serta rentang, dan menolak write ketika terkunci atau planner sibuk.','control',[],['max_v dan max_dv masing-masing 5 bit','max_w dan max_dw masing-masing 7 bit','locked, valid dan fault 1 bit']),
 'igor_costmap_manager':('Pengelola costmap','Upload dan commit atomik','Memeriksa nomor urut, urutan alamat dan kelengkapan 16.384 byte sebelum mengganti bank aktif. Menghitung umur peta.','memory',[],['sequence dan age 32 bit','write address 15 bit = bank 1 + cell 14','Replay dan commit parsial ditolak','Write dibroadcast ke empat copy']),
 'igor_costmap_bank':('Memori costmap','Empat copy double buffer','RAM synchronous 32.768 x 8 per instance. Dua frame 128 x 128 disimpan untuk satu port baca independen per tile.','memory',[],['4 instance','32 KiB per copy','128 KiB total costmap','Data 8 bit','Alamat 15 bit']),
 'igor_candidate_generator':('Pembangkit kandidat','Dynamic window','Mendecode 9 bit indeks menjadi 16 kode kecepatan dan 32 kode belok, lalu memeriksa batas kecepatan serta perubahan dari command sebelumnya.','compute',[],['velocity 4 bit unsigned','omega 6 bit signed, -16 sampai 15','legal 1 bit']),
 'igor_rollout_tile':('Rollout tile','128 kandidat per evaluator','FSM INIT, STEP, WAIT_RAM, SCORE, FINISH menelusuri 20 pose per kandidat, menolak collision atau overflow dan menyimpan kandidat terbaik lokal.','compute',['igor_candidate_generator','igor_kinematic_step','igor_score_accumulator'],['4 instance dengan TILE_ID 0 sampai 3','Indeks diinterleave dengan increment 4','128 x 20 pose per tile','Cell >=254 dianggap tidak legal','score = 16 x cost + goal + velocity penalty']),
 'igor_kinematic_step':('Pembaruan pose','Kinematika fixed point','Menghitung next_x, next_y dan next_heading memakai perkalian displacement dengan lookup sinus/cosinus. Memeriksa overflow dan batas peta.','compute',['igor_trig_lut'],['x dan y signed 24 bit','heading unsigned 8 bit','2 instance trig LUT','Sin/cos signed 16 bit']),
 'igor_trig_lut':('Lookup trigonometri','Sinus dan cosinus','Memetakan fase 8 bit ke nilai sinus signed 16 bit. Cosinus memakai penambahan fase 64.','compute',[],['256 phase codes','value signed 16 bit','2 LUT per kinematic step']),
 'igor_score_accumulator':('Akumulator skor','Penjumlahan dengan overflow','Menjumlahkan prior dan increment 32 bit melalui hasil antara 33 bit untuk mendeteksi carry.','compute',[],['Input 2 x 32 bit','total 32 bit','overflow 1 bit']),
 'igor_best_candidate_selector':('Pemilih kandidat','Turnamen empat hasil','Membandingkan empat hasil tile melalui dua tingkat comparator. Skor terkecil menang, lalu indeks terkecil saat seri.','control',[],['valid 4 bit','indices 4 x 9 =36 bit','scores/costs/goals/velocities masing-masing 128 bit','Hasil index 9 bit + 4 critic 32 bit']),
 'igor_safety_security_gate':('Gerbang keselamatan','Izin akhir fail closed','Menghasilkan izin dan kode command hanya bila seluruh prasyarat terpenuhi. Reset, emergency, peta, konfigurasi, overflow, deadline, hasil dan batas gerak dapat menutup izin.','safety',[],['motor_enable 1 bit','v_command 5 bit unsigned','omega_command 7 bit signed','fault_code 8 bit, kode 1 sampai 11','Default semua keluaran gerak nol']),
 'igor_status_logger':('Pencatat status','Diagnostik gangguan','Menyimpan fault terakhir dan menambah penghitung saat terjadi perubahan fault sesuai kondisi logger.','safety',[],['fault 8 bit','event counter 32 bit']),
 'igor_neural_core':('Inti neural FPGA','Inferensi Q8.8 serial','Wrapper FPGA untuk ROM bobot dan datapath neural 24-64-64-4. Jalur ini terpisah dari DWA.','neural',['igor_neural_rom','igor_neural_datapath'],['18192 siklus per inferensi','Input dan output signed 16 bit','24 input','4 output']),
 'igor_neural_rom':('ROM model FPGA','6020 parameter Q8.8','Membaca ROM synchronous 8192 x 16 dari berkas model unified padded. 6020 word berisi bobot dan bias.','memory',[],['Address 13 bit','Data signed 16 bit','File .mem harus ikut disalin','Satu instance inferensi dan satu inspeksi UART']),
 'igor_neural_datapath':('Datapath neural FPGA','MAC serial dan aktivasi','Satu perkalian signed 16 x 16 menghasilkan product 32 bit ke accumulator 40 bit. Hidden ReLU, output clipping -256..256.','neural',[],['Didefinisikan di igor_neural_core.v','24-64-64-4','24 input + 128 hidden + 4 output word','Single MAC lane','Neural FPGA berbeda dengan dual-MAC ASIC']),
 'igor_de10_nano_wrapper':('Wrapper scene alternatif','Demo non-UART','Pembungkus scene lama dengan LED, switch dan core DWA. Berkas disertakan dalam proyek, tetapi bukan top aktif Quartus.','alternate',['igor_top'],['Tidak menjadi root proyek FPGA saat ini','Tidak punya port UART']),
 'tt_um_wlmoi_igor_neural_logic':('Top TinyTapeout aktif','Chip inferensi lengkap','Menyediakan register sinkron pin TinyTapeout untuk validasi model tetap, pemuatan input dan pembacaan inferensi 24-64-64-4.','asic',['igor_parameter_logic','igor_neural_datapath_logic'],['ui_in dan uo_out 8 bit','uio_in data tulis 8 bit','uio_out dan uio_oe selalu nol','CMOS5L, 8x4 tile','Model tidak dapat diganti setelah fabrikasi']),
 'igor_parameter_logic':('Logika parameter ASIC','Model immutable','6020 word model dipetakan ke konstanta standard-cell logic, dengan pembacaan pasangan even/odd. Tidak memakai SRAM fisik.','asic',[],['Address 13 bit','Read data, even dan odd masing-masing signed 16 bit','5888 weight +132 bias','Write interface dipertahankan untuk verifikasi model']),
 'igor_neural_datapath_logic':('Datapath neural ASIC','Dua MAC paralel','Dua lane perkalian signed dan pipeline pembacaan berpasangan mengeksekusi jaringan neural lengkap.','asic',['igor_activation_logic'],['3080 siklus inferensi','61,6 us pada target 50 MHz','Timing fisik belum qualified','Accumulator 40 bit']),
 'igor_activation_logic':('Aktivasi ASIC','Register tanpa SRAM','Menyimpan 152 word input dan hidden activation menggunakan flip-flop, dengan pembacaan even/odd.','asic',[],['152 x16 bit','Address 8 bit','Input 24 +hidden 64 +hidden 64','Output final disimpan datapath'])
}

modules=[]
for p in sorted((REPO/'rtl').glob('*.v')):
    modules+=parse_file(p.relative_to(REPO).as_posix())
asic=[]
for p in ['src/igor_neural_logic_top.v','src/igor_parameter_logic.v','src/igor_neural_datapath_logic.v','src/igor_activation_logic.v']:
    asic+=parse_file(p)
for m in modules+asic:
    title,subtitle,explanation,group,children,highlights=desc[m['module']]
    m.update(id=m['module'],title=title,subtitle=subtitle,explanation=explanation,group=group,children=children,highlights=highlights)

hierarchy=[
 ('igor_uart_top','serial','igor_uart_protocol',1),('igor_uart_protocol','receiver','igor_uart_rx',1),('igor_uart_protocol','transmitter','igor_uart_tx',1),
 ('igor_uart_top','core','igor_top',1),('igor_uart_top','neural','igor_neural_core',1),('igor_uart_top','inspection_rom','igor_neural_rom',1),
 ('igor_neural_core','weights','igor_neural_rom',1),('igor_neural_core','core','igor_neural_datapath',1),
 ('igor_top','cfg','igor_config_registers',1),('igor_top','maps','igor_costmap_manager',1),('igor_top','tiles[t].memory','igor_costmap_bank',4),('igor_top','tiles[t].tile','igor_rollout_tile',4),
 ('igor_top','selector','igor_best_candidate_selector',1),('igor_top','gate','igor_safety_security_gate',1),('igor_top','logger','igor_status_logger',1),
 ('igor_rollout_tile','gen','igor_candidate_generator',1),('igor_rollout_tile','stepper','igor_kinematic_step',1),('igor_rollout_tile','acc','igor_score_accumulator',1),
 ('igor_kinematic_step','s','igor_trig_lut',1),('igor_kinematic_step','c','igor_trig_lut',1),
 ('tt_um_wlmoi_igor_neural_logic','parameter_store','igor_parameter_logic',1),('tt_um_wlmoi_igor_neural_logic','neural','igor_neural_datapath_logic',1),('igor_neural_datapath_logic','activation_store','igor_activation_logic',1)
]

flows=[
 {'from':'UART_RX','to':'igor_uart_protocol','name':'serial RX','bits':1,'kind':'serial','detail':'115200 baud 8N1'},
 {'from':'igor_uart_protocol','to':'igor_uart_top','name':'opcode + payload + valid','bits':[8,32,1]},
 {'from':'igor_uart_top','to':'igor_config_registers','name':'cfg_data / write / lock','bits':[32,1,1]},
 {'from':'igor_uart_top','to':'igor_costmap_manager','name':'sequence / address / data','bits':[32,15,8]},
 {'from':'igor_costmap_manager','to':'igor_costmap_bank','name':'broadcast write','bits':[1,15,8],'instances':4},
 {'from':'igor_rollout_tile','to':'igor_costmap_bank','name':'read address + active bank','bits':[14,1],'instances':4},
 {'from':'igor_costmap_bank','to':'igor_rollout_tile','name':'cell cost','bits':8,'instances':4},
 {'from':'igor_rollout_tile','to':'igor_best_candidate_selector','name':'valid / index / score / cost / goal / velocity','bits':[1,9,32,32,32,32],'instances':4},
 {'from':'igor_best_candidate_selector','to':'igor_safety_security_gate','name':'index decoded as candidate v / omega','bits':[5,7]},
 {'from':'igor_safety_security_gate','to':'command output','name':'permit / v / omega / fault','bits':[1,5,7,8]},
 {'from':'igor_uart_top','to':'igor_neural_core','name':'input index / value / output index','bits':[5,16,2]},
 {'from':'igor_neural_rom','to':'igor_neural_datapath','name':'weight signed Q8.8','bits':16},
 {'from':'igor_neural_datapath','to':'igor_neural_rom','name':'ROM address','bits':13},
 {'from':'igor_neural_core','to':'igor_uart_top','name':'output value / latency','bits':[16,32]}
]

metrics=[
 {'id':'dwa_latency','label':'Kernel DWA','value':7938,'unit':'cycles','clock_hz':50000000,'microseconds':158.76,'status':'simulated','scope':'Evaluasi lengkap pada enam scene. Abort dan timeout jalur berbeda.','source':ref('evidence/audit/scene_latency.csv',1)},
 {'id':'poses','label':'Evaluasi pose per run','value':10240,'formula':'4 tile x128 kandidat x20 pose','status':'RTL structure','source':ref('rtl/igor_rollout_tile.v',6)},
 {'id':'neural_fpga','label':'Inferensi neural FPGA serial','value':18192,'unit':'cycles','microseconds':363.84,'status':'simulated','source':ref('verification/neural_cocotb_results.json',1)},
 {'id':'neural_asic','label':'Inferensi TinyTapeout dual MAC','value':3080,'unit':'cycles','microseconds_at_target':61.6,'status':'RTL/generic simulation','scope':'50MHz target, bukan hasil timing routed.','source':ref('evidence/neural_logic_verification.json',1)},
 {'id':'fpga_fit','label':'Resource DE10-Nano','status':'Quartus fit successful','value':{'alm':4964,'alm_capacity':41910,'registers':1554,'memory_bits':1051008,'m10k':131,'m10k_capacity':553,'dsp':10,'dsp_capacity':112},'source':ref('evidence/quartus/reports/DE10_NANO/igor.fit.summary',1)},
 {'id':'fpga_sta','label':'STA DE10-Nano','value':{'worst_setup_ns':0.146,'worst_hold_ns':0.120},'status':'STA report','scope':'Jangan salah menyebut 0.120ns sebagai setup slack.','source':ref('evidence/quartus/reports/DE10_NANO/igor.sta.summary',1)},
 {'id':'power','label':'Power Analyzer','value':506.69,'unit':'mW','status':'estimated','scope':'Vectorless Low confidence. Hanya FPGA report, bukan whole board/HPS/robot.','source':ref('evidence/audit/power/igor.pow.summary',1)},
 {'id':'faults','label':'Fault scenarios permit=0','value':9,'status':'simulated','source':ref('evidence/audit/fault_status.csv',1)},
 {'id':'asic_model','label':'Parameter ASIC','value':6020,'unit':'signed16 words','status':'RTL/generic verified','source':ref('evidence/neural_logic_verification.json',1)}
]

catalog={
 'schema':'igor-rtl-explorer-catalog-1','generated_date':'2026-10-15','team_display_name':'iSeeDesignITB',
 'count':{'canonical_fpga_source_files':19,'canonical_fpga_module_declarations':20,'active_asic_source_files':4},
 'fpga_top':'igor_uart_top','asic_top':'tt_um_wlmoi_igor_neural_logic','modules':modules,'asic_modules':asic,
 'hierarchy':[dict(parent=a,instance=b,child=c,count=d) for a,b,c,d in hierarchy], 'flows':flows,'metrics':metrics,
 'board':{'name':'DE10-Nano','device':'5CSEBA6U23I7','fabric':'Cyclone V','clock_hz':50000000,'qpf':'fpga_de10_nano/quartus/igor.qpf','qsf':'fpga_de10_nano/quartus/igor.qsf','sof':'fpga_de10_nano/quartus/output_files/igor.sof','portable_project':'ImplementationReadyQuartus/IGOR_DE10_NANO/quartus/igor.qpf','source':ref('fpga_de10_nano/quartus/igor.qsf',1),'uart':{'baud':115200,'data_bits':8,'parity':'none','stop_bits':1,'fpga_rx':{'pin':'V12','header':'JP1 pin1'},'fpga_tx':{'pin':'E8','header':'JP1 pin2'},'ground':'JP1 pin12 or30','voltage':'3.3V LVTTL','source':ref('fpga_de10_nano/quartus/pin_assignment.tcl',33)}},
 'board_hotspots':[
  {'id':'fabric','title':'Cyclone V SoC','description':'FPGA fabric menjalankan RTL IGOR. HPS ARM adalah domain prosesor tersendiri.','module':'igor_uart_top'},
  {'id':'gpio0','title':'GPIO0 / JP1','description':'RX V12 pin1, TX E8 pin2, logika3.3V. UART planner115200 dan UART STM1Mbps adalah proyek berbeda.','module':'igor_uart_protocol'},
  {'id':'clock','title':'Clock 50MHz','description':'Input FPGA_CLK1_50 pada V11. Clock dari board, bukan oscillator RTL.','module':'igor_uart_top'},
  {'id':'keys','title':'KEY0 dan KEY1','description':'KEY0 reset active-low. KEY1 emergency inhibit active-low.','module':'igor_safety_security_gate'},
  {'id':'switches','title':'SW[3:0]','description':'SW2 not-ready dan SW3 protective stop. SW0/1 unused pada top UART aktif.','module':'igor_uart_top'},
  {'id':'leds','title':'LED[7:0]','description':'{fault[3:0],done,busy,reset released,enable}.','module':'igor_status_logger'},
  {'id':'usb','title':'USB host HPS','description':'Rute USB controller STM memerlukan HPS/Linux host. GPIO FPGA bukan USB host.','module':None},
  {'id':'jtag','title':'USB-Blaster II / JTAG','description':'Untuk memprogram SOF FPGA dari Quartus, bukan port UART aplikasi.','module':None}
 ],
 'assets':{'existing_3d_models':[],'existing_dashboard_html':[],'architecture_svg':'docs/assets/architecture.svg','banner_svg':'docs/assets/igor-banner.svg','quartus_screenshot':'evidence/quartus/nano_resource.png','dwa_waveform':'evidence/waveforms/05_dwa_result.png','neural_waveform':'evidence/waveforms/06_neural_result.png','flowchart':'docs/flowcharts/IGOR_RTL_Flowchart.io'},
 'uncertainties':[
  'No existing glb/gltf/obj/stl model was found. Any generated board geometry is an explanatory illustration, not an official accurate CAD model.',
  'Logical floorplan rectangles are not physical placement or measured block area. FPGA ALM count is not ASIC gate count.',
  'Canonical rtl/ has19 files but20 modules. igor_neural_datapath is a second module inside igor_neural_core.v.',
  'Active FPGA source lists an alternative scene wrapper that is not reachable from active igor_uart_top.',
  'Full DWA plus costmap are FPGA-only. Current TinyTapeout active manifest contains neural inference only, not DWA, motor controller or FPGA UART.',
  'TinyTapeout RTL and synthesis verification are separate from routed DRC, LVS and extracted timing. Current physical status is read from evidence/tinytapeout/current/verification.json.',
  'FPGA programming and sensor-to-motor integrated physical acceptance not established by a SOF existing in the repository.',
  'Team presentation name is iSeeDesignITB.',
  'Current info.yaml selects full fixed-model neural inference. Earlier gate and SRAM experiments are historical references, not the active submission.',
  'Do not join115200 IGOR planner frames with1Mbps AA55 STM motor frames without an actual RTL bridge. They are different protocols and projects.',
  'Neural output is not yet connected to DWA ranking or final command gate in active FPGA top. A 522.60us sum is arithmetic projection, not measured integrated latency.'
 ]
}
OUTPUT=ROOT/'dist/data/rtl-catalog.json'
OUTPUT.parent.mkdir(parents=True,exist_ok=True)
OUTPUT.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert len(modules)==20
assert len(asic)==4
assert sum(len(m['ports']) for m in modules)>150
print(json.dumps({'fpga_modules':len(modules),'fpga_ports':sum(len(m['ports']) for m in modules),'asic_modules':len(asic),'output':str(OUTPUT)}))
