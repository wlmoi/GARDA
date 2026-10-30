"""Reviewed FSM descriptions: existing RTL behavior, not replacement RTL."""
PAGES = []


def page(key, title, source, register, kind, states, transitions, reset, notes, ranks=None):
    PAGES.append(dict(key=key, title=title, source=source, register=register, kind=kind,
                      states=[dict(id=s[0], label=s[1], action=s[2]) for s in states],
                      transitions=[dict(source=e[0], target=e[1], label=e[2]) for e in transitions],
                      reset=reset, notes=notes, ranks=ranks or []))


page('00_overview','PETA FSM — JALUR PARALLEL8 AKTIF','experiments/parallel8/igor_src_policy.qsf',
 'Hierarchy proyek Parallel8','OVERVIEW: kotak adalah modul/controller, bukan state satu FSM',[
 ('RX','UART RX','state[1:0]: page04'),('PARSER','FRAME PARSER','position[7:0]: page03'),
 ('MODE','POLICY CONTROLLER','mode[3:0]: page02'),('CORE','CORE PARALLEL8','state[3:0]: page01'),
 ('TX','UART TX','busy + bit_index/count: page05'),('STOP','RESET / E-STOP','Synchronizer + latch: page06/07'),
 ('LEASE','RESULT LEASE','result_valid + timer: page08')],[
 ('RX','PARSER','rx_data[7:0]; rx_valid / rx_error (1-bit)'),('PARSER','MODE','CRC + domain sah -> mode LOAD'),
 ('MODE','CORE','core_load/core_start/core_abort; index[6:0]; value[15:0]'),
 ('CORE','MODE','core_done/core_fault; output_value[15:0]; latency[31:0]'),
 ('MODE','TX','tx_data[7:0]; tx_send (1-bit)'),('TX','MODE','tx_busy (1-bit)'),
 ('STOP','MODE','rst_n / estop_active (1-bit)'),('MODE','LEASE','CAP2 -> result_valid=1; timeout/reject ->0')],
 '',[
 'Mulai page01 untuk FSM core. Page02..08 mencakup controller pendukung yang aktif pada proyek Parallel8.',
 'Page09..17 adalah source serial / planner / neural legacy: arsip penjelasan, bukan semuanya terinstansiasi pada Parallel8.',
 'Lingkaran/oval pada halaman FSM = state. Kotak halaman overview/struktur = blok fungsi, bukan enum state.',
 'Semua transisi memakai clock edge kecuali reset asinkron dan mask stop kombinasi yang disebutkan eksplisit.',
 'Tidak ada modifikasi RTL, bobot, pin, atau SOF dari dokumentasi ini.' ],[['RX','PARSER','MODE'],['CORE','TX','LEASE'],['STOP']])

page('18_three_process','ACUAN STRUKTUR THREE-PROCESS — BUKAN REFACTOR LIVE','rtl/igor_src_policy/igor_src_policy_uart.v',
 'Model struktur rekomendasi, bukan nama state RTL','STRUCTURE: pembagian tugas kode untuk kandidat berikutnya',[
 ('SEQ','1. STATE REGISTER','always @(posedge clk / reset)\ncurrent_state <= next_state'),
 ('NEXT','2. NEXT-STATE LOGIC','always @*\nnext_state=current_state; case + default'),
 ('OUT','3. OUTPUT LOGIC / REGISTER','Decode state + input/datapath\nPulse default0; output penting diregister')],[
 ('SEQ','NEXT','current_state[N-1:0]'),('NEXT','SEQ','next_state[N-1:0]'),
 ('SEQ','OUT','current_state[N-1:0] + input/data yang diperlukan')],
 '',[
 'RTL core/policy sekarang menggabungkan state update, next-state dan register datapath dalam always clocked; ini gaya sequential yang sah.',
 'Moore: output=f(state). Mealy: output=f(state,input). Mealy yang diregister menunggu clock; tidak selalu berarti respons tanpa latensi.',
 'Moore decode kombinasi tidak otomatis bebas glitch. Registrasi output + CDC/reset yang benar menentukan kestabilan fisik.',
 'Assignment tidak lengkap dalam always @* dapat membentuk latch; tidak menulis register dalam always posedge berarti hold flip-flop.',
 'Default case membantu perilaku RTL ilegal; proteksi state fisik tetap perlu verifikasi encoding/safe-FSM di synthesis, bukan sekadar gambar.',
 'Enum/localparam bernama membantu review. Nilai state di halaman lain disalin dari source, bukan janji encoding hasil Fitter.',
 'Refactor three-process harus menjaga timing pulse, prioritas reject, nonblocking pipeline, oracle integer, safety, dan hasil build sebelum mengganti SOF.' ],[['SEQ','NEXT','OUT']])


CORE_STATES = [
 ('IDLE','IDLE (0)','Terima start bila 74 input lengkap'),
 ('BIAS_ADDRESS','BIAS_ADDRESS (1)','address[11:0] = bias_base + (neuron >> 3)'),
 ('BIAS_WAIT','BIAS_WAIT (2)','Tunggu data ROM sinkron'),
 ('BIAS_TAKE','BIAS_TAKE (3)','acc[39:0] = sign-extend(bias) << 8; k=0'),
 ('WEIGHT_ADDRESS','WEIGHT_ADDRESS (4)','Set address[11:0] dan operand[15:0]'),
 ('WEIGHT_WAIT','WEIGHT_WAIT (5)','Tunggu weight[lane][15:0]'),
 ('MAC','MAC (6)','8 accumulator += sign-extended product; weight_address++'),
 ('ACTIVATE','ACTIVATE (7)','Simpan 8 hidden atau 3 actions; catat saturation')]
CORE_EDGES = [
 ('IDLE','IDLE','!start / load_input sah menyimpan input'),
 ('IDLE','BIAS_ADDRESS','start sah / busy=1; done=0; layer=0; neuron=0'),
 ('BIAS_ADDRESS','BIAS_WAIT','1 clock / alamat bias terdaftar'),
 ('BIAS_WAIT','BIAS_TAKE','1 clock / data bias siap'),
 ('BIAS_TAKE','WEIGHT_ADDRESS','1 clock / bias masuk accumulator'),
 ('WEIGHT_ADDRESS','WEIGHT_WAIT','1 clock / alamat dan operand terdaftar'),
 ('WEIGHT_WAIT','MAC','1 clock / weights siap'),
 ('MAC','WEIGHT_ADDRESS','k < input_count-1 / k++'),
 ('MAC','ACTIVATE','k == input_count-1'),
 ('ACTIVATE','BIAS_ADDRESS','neuron+8 < output_count / neuron+=8'),
 ('ACTIVATE','BIAS_ADDRESS','neuron+8 >= output_count && layer!=2 / layer++; neuron=0'),
 ('ACTIVATE','IDLE','neuron+8 >= output_count && layer==2 / busy=0; done=1')]
CORE_NOTES = [
 'Prioritas sebelum case: !rst_n > abort > fault tersimpan > protokol load/start tidak sah > case(state).',
 'Abort: state=IDLE, loaded=0, busy=done=0, actions=0; fault sticky tidak dihapus. Fault hanya dihapus reset.',
 'Pelanggaran: input_index>=74: code1; load saat busy:2; start saat busy:3; input belum lengkap:4; load+start:5 (sesuai prioritas if).',
 'Default state ilegal: IDLE, busy=done=0, loaded=0, fault=1, error_code=6. Tidak ada state FAULT terpisah.',
 'output_value[15:0] = actions[output_index] hanya bila done && !fault && !abort && output_index<3; selain itu nol.',
 'busy/done/fault dan datapath adalah register; output mask kombinasi bergantung input. Bukan klaim seluruh core Moore murni.',
 '6.916 clock / 138,32 us @50 MHz; waktu ROM WAIT sudah termasuk. Diagram tidak menambah siklus baru.' ]
page('01_core_parallel8','CORE PARALLEL8 — 8 STATE','experiments/parallel8/igor_src_policy_core.v',
     'state[3:0]','FSM eksplisit; kontrol sinkron + datapath register; output gating kombinasi',
     CORE_STATES, CORE_EDGES, 'IDLE; semua flag/counter utama=0', CORE_NOTES,
     [['IDLE','BIAS_ADDRESS','BIAS_WAIT','BIAS_TAKE'],['ACTIVATE','MAC','WEIGHT_WAIT','WEIGHT_ADDRESS']])

page('02_policy_mode','TRANSAKSI POLICY — LOAD, RUN, CAPTURE, TX','rtl/igor_src_policy/igor_src_policy_uart.v',
 'mode[3:0]','FSM eksplisit; pulse/output register; safety_permit kombinasi',[
 ('RX','RX (0)','Tunggu frame observasi sah'),('LOAD','LOAD (1)','core_load=1; index[6:0]=load_index; value[15:0]'),
 ('START','START (2)','core_start=1; infer_timer=0'),('RUN','RUN (3)','Tunggu core_done; watchdog aktif'),
 ('CAP0','CAP0 (4)','sample0=core_output_value; output_index=1'),('CAP1','CAP1 (5)','sample1=core_output_value; output_index=2'),
 ('CAP2','CAP2 (6)','sample2; CRC; result_valid=1; response_valid=1'),('TX','TX (7)','Kirim 11 byte; tx_send=1 pada slot siap'),
 ('TX_START_LAST','TX_START_LAST (8)','Tunggu transmitter menerima byte CRC terakhir'),
 ('TX_END_LAST','TX_END_LAST (9)','Tunggu byte terakhir selesai')],[
 ('RX','RX','belum ada frame sah'),('RX','LOAD','CRC cocok && seluruh observasi valid / load_index=0'),
 ('LOAD','LOAD','load_index<73 / load_index++'),('LOAD','START','load_index==73 / jadwalkan core_load terakhir'),
 ('START','RUN','1 clock / core_start terdaftar'),('RUN','RUN','!core_done && tidak ada reject'),
 ('RUN','CAP0','core_done / output_index=0; simpan core_latency'),('CAP0','CAP1','1 clock'),('CAP1','CAP2','1 clock'),
 ('CAP2','TX','1 clock / tx_index=0'),('TX','TX','tx_busy || tx_send: tunggu; slot siap && index<10: index++'),
 ('TX','TX_START_LAST','!tx_busy && !tx_send && tx_index==10 / tx_send=1'),
 ('TX_START_LAST','TX_START_LAST','!tx_busy'),('TX_START_LAST','TX_END_LAST','tx_busy'),
 ('TX_END_LAST','TX_END_LAST','tx_busy'),('TX_END_LAST','RX','!tx_busy')],
 'RX; position=0; hasil/flag/pulse=0',[
 'Prioritas: estop > core_fault saat mode!=RX > rx_error > rx_valid saat mode!=RX > infer timeout > inter-byte timeout > stale result > parser + case(mode).',
 'reject(code): mode=RX, position=0, result_valid=0, core_abort=1, tx_cancel=1; counter rejected saturating + history fault.',
 'E-stop: mode=RX; result_valid=0; core_abort=1; tx_cancel=1. Error1 dicatat pada rising event stop, bukan setiap clock.',
 'Default mode ilegal: reject(10). RX parser fault codes: framing2, header3, opcode4, length5, CRC6, timeout7, range8, busy9, core10, stale11, watchdog12.',
 'core_load/core_start/core_abort/tx_send/tx_cancel/response_valid diberi default 0 tiap clock; state dapat menjadikannya 1.',
 'Nonblocking assignment: LOAD terakhir diterima core pada clock START; core_start dari START diterima core pada clock RUN berikutnya.',
 'response_valid pulse pada CAP2, bukan saat stop bit terakhir selesai. safety_permit=result_valid && !estop_active && !core_fault.',
 'debug_state F saat E-stop dan E saat core_fault adalah overlay debug; bukan tambahan state mode=F/E.' ],
 [['RX','LOAD','START'],['RUN','CAP0','CAP1'],['CAP2','TX'],['TX_START_LAST','TX_END_LAST']])

page('03_frame_parser','PARSER OBSERVASI — HEADER, PAYLOAD, CRC','rtl/igor_src_policy/igor_src_policy_uart.v',
 'position[7:0] + parity payload_index[0]','Kontrol parser berbasis counter; nama fase adalah alias penjelas',[
 ('P0','position=0','Cari header 0x5A'),('P1','position=1','Cari header 0xA5'),
 ('P2','position=2','Opcode harus 0x01; mulai CRC'),('P3','position=3','Length harus 0x94 (148 byte)'),
 ('LOW','position=4,6,...,150','Simpan low_byte[7:0]; CRC update'),
 ('HIGH','position=5,7,...,151','Simpan received_word[15:0]; cek domain; CRC update'),
 ('CRC','position=152','Bandingkan byte CRC; invalid_observation diperiksa')],[
 ('P0','P0','rx_data!=0x5A'),('P0','P1','rx_data==0x5A / result_valid=0'),
 ('P1','P1','rx_data==0x5A'),('P1','P2','rx_data==0xA5'),('P1','P0','byte lain / reject(3)'),
 ('P2','P3','rx_data==0x01'),('P2','P0','opcode salah / reject(4)'),
 ('P3','LOW','rx_data==0x94 / invalid_observation=0'),('P3','P0','length salah / reject(5)'),
 ('LOW','HIGH','rx_valid / low_byte=rx_data; position++'),
 ('HIGH','LOW','position<151 / position++; domain salah: flag invalid'),
 ('HIGH','CRC','position==151 / seluruh 74 word selesai'),
 ('CRC','P0','CRC salah: reject(6); range salah: reject(8)'),
 ('CRC','P0','CRC && domain sah / mode=LOAD; accepted++ saturating')],
 'position=0; crc=0; invalid_observation=0',[
 'Setiap panah konsumsi byte hanya pada rx_valid=1, mode=RX, dan tidak dikalahkan prioritas reject/E-stop. Tanpa byte: fase ditahan.',
 'payload_index=position-4; received_word={rx_data,low_byte}; urutan little-endian. LiDAR0..63:0..256; field64..73:-256..256.',
 'Parser global reset/reject mengembalikan position=0. Inter-byte timeout hanya ketika position!=0 dan tidak ada rx_valid.',
 'Default case(position) di source berarti pemrosesan payload, bukan guard illegal-position tersendiri. Alias LOW/HIGH hanya menjelaskan rentang posisi legal.',
 'CRC8 Maxim reflected 0x8C; opcode, length dan payload masuk CRC, dua header tidak. mode tidak menjadi LOAD sebelum CRC+domain sah.' ],
 [['P0','P1','P2'],['P3','LOW','HIGH'],['CRC']])

page('04_uart_rx','UART RX — SAMPLE START, DATA, STOP','rtl/igor_uart_rx.v','state[1:0]',
 'FSM eksplisit numerik; valid/error/data register',[
 ('S0','state=0 | IDLE','Tunggu sync=0; idle line tinggi'),('S1','state=1 | START_CHECK','Tunggu setengah bit; validasi start'),
 ('S2','state=2 | DATA','shift[bit_index]=sync; sample delapan bit'),('S3','state=3 | STOP','Tunggu satu bit; validasi stop')],[
 ('S0','S0','sync=1'),('S0','S1','sync=0 / count=CLKS_PER_BIT/2-1'),
 ('S1','S1','count!=0 / count--'),('S1','S2','count==0 && sync==0 / index=0; count=BIT-1'),
 ('S1','S0','count==0 && sync==1 / false start'),('S2','S2','count!=0: count--; sample && index<7: index++'),
 ('S2','S3','count==0 && bit_index==7 / sample bit terakhir'),
 ('S3','S3','count!=0 / count--'),('S3','S0','count==0 && sync==1 / valid=1; data[7:0]=shift'),
 ('S3','S0','count==0 && sync==0 / error=1')],
 'state=0; valid=error=0; data=0; meta=sync=1',[
 'meta/sync adalah dua flop sinkronisasi RX asinkron. Sample dipakai dari sync, bukan langsung rx.',
 'valid dan error default0 tiap clock; pulse hanya pada penyelesaian STOP. Default case(state): state=0.',
 'Pada proyek Parallel8 BIT_CYCLES=(50.000.000+921600/2)/921600=54. Nominal921600, aktual50MHz/54.',
 'IDLE/START_CHECK/DATA/STOP adalah alias diagram; RTL memakai angka0..3, bukan enum bernama.' ],[['S0','S1'],['S3','S2']])

page('05_uart_tx','UART TX — CONTROLLER BERBASIS BUSY/COUNTER','rtl/igor_uart_tx.v',
 'busy + bit_index[3:0] + count[15:0]','Fase implisit; bukan register enum empat state',[
 ('IDLE','busy=0 | IDLE','tx=1; tunggu send'),('START','busy=1, bit_index=0','shift={1,data[7:0],0}; tx=start bit0'),
 ('DATA','busy=1, bit_index=1..8','tx=shift[0]; kirim data LSB-first'),('STOP','busy=1, bit_index=9','tx=stop bit1')],[
 ('IDLE','IDLE','!send'),('IDLE','START','send / busy=1; count=BIT-1; index=0'),
 ('START','START','count!=0 / count--'),('START','DATA','count==0 / shift right; index=1; reload count'),
 ('DATA','DATA','count!=0: count--; count==0 && index<8: shift; index++'),
 ('DATA','STOP','count==0 && bit_index==8 / shift; index=9'),('STOP','STOP','count!=0 / count--'),
 ('STOP','IDLE','count==0 && bit_index==9 / busy=0')],
 'busy=0; shift=10\'h3ff; bit_index=count=0',[
 'tx=busy ? shift[0] : 1. Tidak ada variabel state eksplisit; diagram memecah fase counter untuk penjelasan.',
 'send saat busy diabaikan. Wrapper hanya memberi pulse saat !tx_busy && !tx_send.',
 'Reset transmitter dari policy: rst_n && !estop_active && !tx_cancel; stop/cancel dapat membatalkan transmisi.',
 'Tidak menambahkan default state atau illegal-counter recovery yang tidak tertulis pada source.' ],[['IDLE','START'],['STOP','DATA']])

page('06_reset_sync','BOARD RESET — ASSERT ASINKRON, RELEASE SINKRON','experiments/parallel8/igor_src_policy_de10_nano.v',
 'reset_sync[1:0]','Fase implisit shift-register; bukan enum',[
 ('R0','reset_sync=00','rst_n=0'),('R1','reset_sync=01','rst_n masih0'),('R2','reset_sync=11','rst_n=1')],[
 ('R0','R1','KEY[0]=1; posedge FPGA_CLK1_50'),('R1','R2','KEY[0]=1; posedge berikutnya'),('R2','R2','KEY[0]=1'),
 ('R2','R0','KEY[0]=0 (asinkron)'),('R1','R0','KEY[0]=0 (asinkron)'),('R0','R0','KEY[0]=0')],
 'KEY0 ditekan -> 00 tanpa menunggu clock',[
 'rst_n=reset_sync[1]. Pelepasan memerlukan dua rising edge, tidak langsung mengikuti tombol.',
 'Nilai10 akibat gangguan bukan fase normal; operasi shift berikutnya menghasilkan01. Ini bukan klaim proteksi SEU.',
 'Clock50MHz. Seluruh kontrol menggunakan domain clock yang sama; gambar bukan bukti MTBF/CDC sign-off.' ])

page('07_estop_latch','BOARD E-STOP — RAW INHIBIT + STICKY LATCH','experiments/parallel8/igor_src_policy_de10_nano.v',
 'stop_latched + stop_sync[1:0]','Flag sticky + synchronizer; bukan enum',[
 ('CLEAR','stop_latched=0','stop_active tetap bisa1 dari raw/sync'),('LATCH','stop_latched=1','stop_active=1; tetap sampai reset')],[
 ('CLEAR','CLEAR','KEY[1]=1'),('CLEAR','LATCH','KEY[1]=0 pada rising edge'),('LATCH','LATCH','KEY1 dilepas/ditekan'),
 ('LATCH','CLEAR','!rst_n (asinkron)')],
 'stop_latched=0; stop_sync=00',[
 'stop_active = !KEY[1] | stop_sync[1] | stop_latched. Tekanan raw langsung menginhibit tanpa menunggu latch.',
 'stop_sync <= {stop_sync[0],!KEY[1]}; jalur sampled memakai dua flop. Lepaskan KEY1 lalu reset KEY0 untuk recovery.',
 'Raw stop masih aktif jika KEY1 ditahan saat reset. CLEAR bukan jaminan permit aktif.',
 'Di policy ada synchronizer estop lagi; estop_active=estop | estop_sync. Jangan menyebut seluruh jalur stop Moore murni.' ])

page('08_result_lease','HASIL POLICY — VALIDITY, LEASE, DAN MASK','rtl/igor_src_policy/igor_src_policy_uart.v',
 'result_valid + result_timer[31:0]','Kontrol implisit flag/counter; permit kombinasi',[
 ('INVALID','result_valid=0','safety_permit=0; action0/1/2=0'),('VALID','result_valid=1','Permit juga memerlukan !estop_active && !core_fault')],[
 ('INVALID','VALID','mode==CAP2 / result_timer=0; response_valid pulse'),
 ('VALID','INVALID','header awal5A diterima pada RX / mulai frame baru'),
 ('VALID','INVALID','stale timeout / reject(11)'),('VALID','INVALID','reject lain atau E-stop'),
 ('INVALID','INVALID','belum ada hasil baru sah'),('VALID','VALID','timer belum habis; tidak ada invalidasi')],
 'result_valid=0; result_timer=0',[
 'Timer bertambah ketika result_valid=1. Default RESULT_TIMEOUT_CYCLES=1.000.000 (20ms @50MHz).',
 'safety_permit=result_valid && !estop_active && !core_fault; core_fault sendiri menutup permit meskipun flag validity belum diubah.',
 'Action mask kombinasi mengeluarkan0 saat permit0. Residual nol bukan perintah motor nol; host masih bertanggung jawab stop.',
 'Pulse response_valid di CAP2 terpisah dari result_valid yang ditahan dan dari selesainya UART TX.' ])

# Same eight names, but serial address/counter update differs from Parallel8.
serial_states=[(s[0],s[1],s[2]) for s in CORE_STATES]
serial_states[1]=('BIAS_ADDRESS','BIAS_ADDRESS (1)','address[14:0]=bias_base+neuron')
serial_states[6]=('MAC','MAC (6)','Satu accumulator += product; weight_address++')
serial_states[5]=('WEIGHT_WAIT','WEIGHT_WAIT (5)','Tunggu weight[15:0] dari ROM')
serial_states[7]=('ACTIVATE','ACTIVATE (7)','Simpan satu hidden/action; catat saturation')
serial_edges=CORE_EDGES[:9]+[
 ('ACTIVATE','BIAS_ADDRESS','neuron != output_count-1 / neuron++'),
 ('ACTIVATE','BIAS_ADDRESS','neuron==output_count-1 && layer!=2 / layer++; neuron=0'),
 ('ACTIVATE','IDLE','neuron==output_count-1 && layer==2 / busy=0; done=1')]
page('09_baseline_serial','LAMPIRAN — CORE SOURCE SERIAL (BUKAN PARALLEL8)','rtl/igor_src_policy/igor_src_policy_core.v',
 'state[3:0]','FSM eksplisit baseline terpisah; satu MAC',serial_states,serial_edges,
 'IDLE; flag utama0', CORE_NOTES[:5]+['Baseline54.348 clock; angka6.916 clock milik Parallel8, bukan FSM serial ini.'],
 [['IDLE','BIAS_ADDRESS','BIAS_WAIT','BIAS_TAKE'],['ACTIVATE','MAC','WEIGHT_WAIT','WEIGHT_ADDRESS']])

page('10_legacy_neural','LAMPIRAN — NEURAL LEGACY 24→64→64→4','rtl/igor_neural_core.v',
 'igor_neural_datapath.state[3:0]','FSM eksplisit numerik; alias state pada diagram',[
 ('N0','state=0 | IDLE','Start hanya jika24 input lengkap + weights_ready'),
 ('N1','state=1 | BIAS_ADDRESS','address[12:0]=bias_base+neuron'),('N2','state=2 | BIAS_WAIT','Tunggu ROM'),
 ('N3','state=3 | BIAS_TAKE','accumulator=bias<<8; k=0'),('N4','state=4 | WEIGHT_ADDRESS','address=base+neuron*input_count+k; operand'),
 ('N5','state=5 | WEIGHT_WAIT','Tunggu ROM'),('N6','state=6 | MAC','accumulator=sum'),
 ('N7','state=7 | ACTIVATE','Simpan hidden/output; hidden positive saturation -> fault')],[
 ('N0','N0','!start; start tidak sah -> fault=1'),('N0','N1','start && loaded==24\'hffffff && weights_ready && !fault && !load_input'),
 ('N1','N2','1 clock'),('N2','N3','1 clock'),('N3','N4','1 clock'),('N4','N5','1 clock'),('N5','N6','1 clock'),
 ('N6','N4','k<input_count-1 / k++'),('N6','N7','k==input_count-1'),('N7','N1','neuron<output_count-1 / neuron++'),
 ('N7','N1','neuron terakhir && layer!=2 / layer++; neuron=0'),('N7','N0','neuron terakhir && layer==2 / busy=0; done=1; loaded=0')],
 'state=0; flags=0',[
 'Default state: busy=done=0; fault=1; state=0. Fault sticky sampai reset; output dimask oleh fault dan weights_ready.',
 'load_input salah atau start saat busy mengeset fault, tetapi source ini tidak memiliki global abort/fault-return seperti Parallel8; komputasi bisa berlanjut.',
 'Nama alias bukan enum RTL. Ini blok legacy terpisah; bukan core74input yang saat ini diprogram.' ],[['N0','N1','N2','N3'],['N7','N6','N5','N4']])

page('11_planner','LAMPIRAN — PLANNER TOP + FAIL-CLOSED','rtl/igor_top.v','state[2:0]',
 'FSM eksplisit; busy/done Moore decode; gate input-dependent',[
 ('IDLE','IDLE (0)','Tunggu start; belum ada hasil aktif'),('RUN','RUN (1)','4 tile paralel; elapsed++; simpan snapshot config/map'),
 ('RESULT','RESULT (2)','done=1; gate mengecek hasil + lease + map'),('FAULT','FAULT (3)','Fault tersimpan; control fault/penyebab dilatch')],[
 ('IDLE','IDLE','!start dan interlock sehat'),('IDLE','RUN','start && map_ok && cfg_ok && ready && !stop && !control_fault / tile_start=1'),
 ('IDLE','FAULT','stop / !ready / start tidak sah'),('RUN','FAULT','!map_ok || !cfg_ok || !ready || stop || tile_fault'),
 ('RUN','FAULT','elapsed>=DEADLINE_CYCLES-1 / timed_out=1; fault8'),
 ('RUN','RESULT','semua tile_done && !tile_start && elapsed>=2'),('RUN','RUN','belum done; tidak fault/timeout'),
 ('RESULT','RESULT','!start dan interlock/map/config sehat'),('RESULT','RUN','start sah / snapshot baru; elapsed=0'),
 ('RESULT','FAULT','stop / !ready / !map_ok / !cfg_ok / start tidak sah'),('FAULT','FAULT','sampai reset')],
 'IDLE; flag/control/timer0',[
 'stop=estop || protective_stop. Default state ilegal -> FAULT, control_fault=1, latched_fault=4.',
 'RESULT dapat tetap RESULT saat lease habis; safety gate tetap menutup motor. Jangan menggambar lease selalu mengubah state ke FAULT.',
 'busy=(state==RUN), done=(state==RESULT). motor_enable/v/omega berasal dari safety gate kombinasi dengan default output0.',
 'FAULT tidak pulih oleh start; perlu reset. Fault fisik aktif tetap punya prioritas live di fault_code.' ],[['IDLE','RUN'],['FAULT','RESULT']])

page('12_rollout','LAMPIRAN — ROLLOUT TILE (4 INSTANCE)','rtl/igor_rollout_tile.v','state[2:0]',
 'FSM eksplisit; hasil dan fault register',[
 ('IDLE','IDLE (0)','Tunggu start'),('INIT','INIT (1)','Reset pose/biaya; x=y=16384; cek window'),
 ('STEP','STEP (2)','Integrasi x/y/heading; legal &= !outside && !overflow'),
 ('WAIT_RAM','WAIT_RAM (3)','Tunggu baca costmap sinkron'),('SCORE','SCORE (4)','Tambah map_data; cek obstacle/overflow'),
 ('FINISH','FINISH (5)','Hitung score; update best dengan tie-break index')],[
 ('IDLE','IDLE','!start'),('IDLE','INIT','start / candidate_index=TILE_ID; reset hasil'),('INIT','STEP','1 clock'),
 ('STEP','WAIT_RAM','1 clock'),('WAIT_RAM','SCORE','1 clock'),('SCORE','STEP','pose<HORIZON-1 / pose++'),
 ('SCORE','FINISH','pose==HORIZON-1'),('FINISH','INIT','candidate_index<508 / candidate_index+=4'),
 ('FINISH','IDLE','candidate_index>=508 / done=1')],
 'IDLE; done/best_valid/arithmetic_fault0',[
 'Prioritas !rst_n > abort_run > case(state). abort_run -> IDLE, done=best_valid=0.',
 'Default ilegal -> IDLE, done=best_valid=0, arithmetic_fault=1. Tidak ada state FAULT lokal.',
 'HORIZON default20. Masing-masing tile mengerjakan128 index dengan langkah4; empat tile mencakup512 kandidat.',
 'done ditahan di IDLE sampai start/reset/abort, bukan otomatis pulse satu clock.' ],[['IDLE','INIT','STEP'],['FINISH','SCORE','WAIT_RAM']])

page('13_demo','LAMPIRAN — SEQUENCER DEMO BOARD','rtl/igor_de10_nano_wrapper.v','demo_state[3:0]',
 'FSM eksplisit numerik; cfg/map/start decode bergantung state',[
 ('D8','state=8 | RESET_WAIT1','Tidak menerbitkan command'),('D9','state=9 | RESET_WAIT2','Tidak menerbitkan command'),
 ('D0','state=0 | CFG_WRITE','cfg_write=1'),('D1','state=1 | CFG_LOCK','cfg_lock=1; sample scenario'),
 ('D2','state=2 | MAP_BEGIN','map_begin=1; address=0'),('D3','state=3 | MAP_WRITE','map_write=1; tulis byte map'),
 ('D4','state=4 | MAP_COMMIT','map_commit=1'),('D5','state=5 | START','start=1; delay_count=0'),
 ('D6','state=6 | WAIT','Tunggu counter delay; bukan tunggu done'),('D7','state=7 | DEFAULT_TRAP','Tidak ada decode command aktif')],[
 ('D8','D9','1 clock'),('D9','D0','1 clock'),('D0','D1','1 clock'),('D1','D2','1 clock'),('D2','D3','1 clock'),
 ('D3','D3','address belum terakhir / address++'),('D3','D4','address==16383 || (scenario==3 && address==100)'),
 ('D4','D5','1 clock'),('D5','D6','1 clock'),('D6','D6','delay_count!=900000 / count++'),
 ('D6','D2','delay_count==900000 / sequence++; sample scenario'),('D7','D7','default case ->7')],
 'demo_state=8',[
 'Semua kode selain0..6,8,9 masuk default ->7; state7 juga mengikuti default sehingga tersangkut sampai reset.',
 'Nama state adalah alias penjelas. Source memakai angka; tidak ada fault latch tambahan pada sequencer demo.',
 'Ini demo planner terpisah, bukan wrapper Parallel8 UART.' ],[['D8','D9','D0'],['D1','D2','D3'],['D4','D5','D6'],['D7']])

page('14_legacy_parser','LAMPIRAN — PARSER UART LEGACY','rtl/igor_uart_protocol.v','pos[3:0]',
 'Kontrol parser numerik + protocol_fault sticky',[
 ('P0','pos=0 | HEADER','Cari 0xA5; init CRC'),('P1','pos=1 | OPCODE','Simpan opcode[7:0]; CRC'),
 ('PAY','pos=2..5 | PAYLOAD','Simpan4 byte payload[31:0]; CRC'),('CRC','pos=6 | CRC','received_crc=rx_data'),
 ('END','pos=7 | TAIL','Tail harus0x5A; cek CRC dan !protocol_fault')],[
 ('P0','P0','rx_data!=0xA5'),('P0','P1','rx_valid && 0xA5'),('P1','PAY','rx_valid / pos=2'),
 ('PAY','PAY','rx_valid && pos<5 / pos++'),('PAY','CRC','rx_valid && pos==5'),('CRC','END','rx_valid'),
 ('END','P0','tail/CRC sah && !protocol_fault / command_valid=1; respond_delay=4'),
 ('END','P0','tail/CRC salah / protocol_fault=1')],
 'pos=0; protocol_fault=0',[
 'Tanpa rx_valid posisi ditahan kecuali timeout/rx_error. rx saat sending atau respond_delay!=0 -> fault dan pos0.',
 'Timeout saat pos!=0 dan timer>=RX_TIMEOUT_CYCLES -> pos0,fault1. rx_error juga mengeset fault dan pos0.',
 'Source memakai beberapa if berurutan dalam satu always, bukan satu prioritas else-if global: assignment terakhir ke register yang sama menang.',
 'Default pos ilegal -> pos0,fault1. protocol_fault sticky; command_valid default0 tiap clock; CRC MSB-first0x07.',
 'Opcode/payload diperiksa lagi oleh igor_uart_top; invalid_command sticky bukan FSM enum.' ],[['P0','P1','PAY'],['END','CRC']])

page('15_legacy_response','LAMPIRAN — SNAPSHOT DAN RESPONSE UART LEGACY','rtl/igor_uart_protocol.v',
 'respond_delay[3:0] + sending + out_pos[3:0]','Kontrol implisit counter/flag; fase bukan enum',[
 ('IDLE','IDLE','respond_delay=0; sending=0'),('WAIT','respond_delay=4..3','Delay core side effect'),
 ('SNAP','respond_delay=2','response_sample[31:0]=response_data'),('BUILD','respond_delay=1','Build out_frame[63:0]; sending=1; out_pos=0'),
 ('SEND','sending=1','Kirim8 byte via tx_send ketika transmitter siap')],[
 ('IDLE','WAIT','command diterima / respond_delay=4'),('WAIT','WAIT','delay=4 / decrement'),('WAIT','SNAP','delay=3 / decrement'),
 ('SNAP','BUILD','1 clock / decrement'),('BUILD','SEND','1 clock / delay=0'),
 ('SEND','SEND','tx_busy || tx_send: tunggu; byte index<7: kirim lalu index++'),
 ('SEND','IDLE','!tx_busy && !tx_send && out_pos==7 / byte terakhir dijadwalkan; sending=0')],
 'delay=0; sending=0; tx_send=0',[
 'sending=0 bukan bukti UART stop bit terakhir sudah selesai; berbeda dengan TX_START_LAST/TX_END_LAST di policy baru.',
 'tx_send default0 tiap clock. Frame LSB-byte-first dari out_frame={A5,response_crc,response_sample,opcode,5A}.',
 'Diagram mengelompokkan kombinasi counter yang normal; tidak menambah enum atau guard illegal-counter baru.' ])

page('16_costmap','LAMPIRAN — COSTMAP ATOMIC COMMIT','rtl/igor_costmap_manager.v','loading + fault + valid + count[14:0]',
 'Kontrol implisit flags; map lama bisa tetap valid saat loading',[
 ('READY','loading=0, fault=0','valid bisa0 atau1; age terus bertambah'),
 ('LOAD','loading=1, fault=0','Tulis inactive bank; alamat harus count'),('FAULT','fault=1','loading=0; gate map_ok tertutup')],[
 ('READY','LOAD','begin_frame sah / sequence>committed_sequence; count=0'),
 ('LOAD','LOAD','write_byte && ram_wr / count++'),
 ('LOAD','READY','commit_frame && count==16384 && !busy && !fault / bank flip; valid=1; age=0'),
 ('READY','FAULT','conflict atau write/commit tidak sah atau begin sequence tidak sah'),
 ('LOAD','FAULT','conflict / begin ulang / write salah / commit belum lengkap atau busy'),('FAULT','FAULT','fault sticky; reset untuk pulih')],
 'READY; valid=0; age=0xffffffff; bank0',[
 'Prioritas conflict > begin_frame > write_byte > commit_frame; tanpa command register kontrol ditahan.',
 'ram_wr=write_byte && loading && !fault && !conflict && count<16384 && frame_addr==count.',
 'fresh=valid && age<FRESH_CYCLES. Kadaluarsa tidak otomatis mengganti loading/fault; gate tetap melihat fresh0.',
 'valid lama tidak harus0 saat LOAD/FAULT; map_ok di top juga mensyaratkan !map_fault. Diagram bukan enum RTL.' ])

page('17_config','LAMPIRAN — CONFIG WRITE, LOCK, FAULT','rtl/igor_config_registers.v','locked + valid + fault',
 'Pengelompokan flags; bukan enum',[
 ('EMPTY','locked=0, valid=0, fault=0','Belum ada config sah'),('VALID','locked=0, valid=1, fault=0','Config bisa ditulis ulang'),
 ('LOCK','locked=1, valid=1, fault=0','Config terkunci'),('FAULT','fault=1','cfg_ok tertutup sampai reset')],[
 ('EMPTY','VALID','wr sah / simpan batas; valid=1'),('VALID','VALID','wr sah ulang'),('VALID','LOCK','lock_request && !busy / locked=1'),
 ('EMPTY','FAULT','lock_request tanpa config sah / valid=0'),('EMPTY','FAULT','wr tidak sah / valid=0'),
 ('VALID','FAULT','wr tidak sah atau lock saat busy / valid=0'),('LOCK','FAULT','wr apa pun / valid=0'),
 ('LOCK','LOCK','tidak ada wr; lock_request sah tetap locked'),('FAULT','FAULT','fault sticky; tidak dibersihkan oleh wr')],
 'EMPTY; seluruh batas0',[
 'wr lebih diprioritaskan daripada lock_request; keduanya bersamaan ditolak. Validasi reserved bits dan rentang dilakukan sebelum simpan.',
 'Guard wr: !locked && !busy && !lock_request && format/range sah. Tidak ada unlock selain reset.',
 'fault dapat tetap1 ketika write berikutnya mengubah valid/data jika belum locked; label FAULT berarti fault sticky, bukan semua register dibekukan.',
 'cfg_ok di top=cfg_valid && locked && !cfg_fault. Tidak ada state enum baru pada source.' ],[['EMPTY','VALID'],['FAULT','LOCK']])
