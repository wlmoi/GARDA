# Kode fault dan hubungan dengan output nol

Ada dua namespace. Cocokkan nama project, protokol, dan kode sebelum mengambil
kesimpulan dari log. Nilai raw Q8.8 policy dibagi 256; kode v/omega planner
memiliki kontrak lain yang dijelaskan pada arsitektur planner.

| Kode planner | Penyebab | Keluaran gerbang |
|---:|---|---|
| 0 | Seluruh syarat lolos | enable=1, kandidat v/omega diteruskan |
| 1 | Reset aktif | enable=0, v=0, omega=0 |
| 2 | E-stop | nol langsung; penyebab abort disimpan sampai reset |
| 3 | Protective stop | nol; penyebab disimpan |
| 4 | Ready/protocol/command contract tidak valid | nol |
| 5 | Peta invalid, belum lengkap, urutan salah, atau usang | nol |
| 6 | Konfigurasi belum valid/terkunci atau dimutasi | nol |
| 7 | Fault aritmetika rollout | nol |
| 8 | Deadline komputasi atau lease perintah habis | nol |
| 9 | Hasil belum valid, semua tile belum selesai, atau peta hasil berbeda | nol |
| 10 | Batas absolut v/omega terlampaui | nol |
| 11 | Batas perubahan v/omega terlampaui | nol |

Prioritas evaluasi mengikuti urutan pada `igor_safety_security_gate.v`, dengan
reset/E-stop/protective-stop lebih tinggi. `igor_top` mempertahankan penyebab
abort awal agar keadaan FAULT tidak menyamarkan penyebab menjadi ready=0.
Logger menaikkan `event_count` hanya pada perubahan ke fault nonnol dan
menjenuhkan counter pada `0xffffffff`. `last_fault` menyimpan penyebab terbaru
yang dicatat. Gate kombinatorial bisa berubah sebelum logger menerima clock;
lihat pasangan checkpoint E-stop 814535 ns dan 814551 ns.

UART planner opcode 7 membaca status aktif; 14 membaca v/omega; 15 membaca
event counter; 16 membaca retained cause. Semua query tersebut mengharuskan
payload nol. Capture hardware melakukan pembacaan berbracket; hasil UART
tetap sampling beberapa transaksi dan bukan snapshot satu siklus.

| Kode policy | Penyebab |
|---:|---|
| 0 | Belum ada fault sejak reset |
| 1 | E-stop |
| 2 | Framing / stop bit UART |
| 3 | Header salah |
| 4 | Opcode salah |
| 5 | Panjang payload salah |
| 6 | CRC salah |
| 7 | Inter-byte timeout / frame parsial |
| 8 | Observasi di luar domain |
| 9 | Byte baru saat load/inferensi/TX sibuk |
| 10 | Fault internal core |
| 11 | Residual kedaluwarsa |
| 12 | Watchdog inferensi |

Pada fault policy, guarded `action0/1/2=0` dan `safety_permit=0`; serializer
dibatalkan. Host tidak menerima respons sukses bernilai nol sebagai cara
menyatakan fault. Host harus mengirim STOP seluruh motor saat transaksi gagal.
Port debug dan history dapat dilihat pada VCD; bitstream board standar hanya
menampilkan empat bit error terakhir melalui LED dan tidak menyediakan query
status UART policy. Node yang dioptimalkan perlu dipertahankan pada build
SignalTap tersendiri. E-stop pada wrapper policy latched sampai KEY0 reset.

Bukti: `evidence/current_safety/cases.csv`, `top_checkpoints.csv`, dan
`verification/src_policy/artifacts/uart_checkpoints.csv`. Semua ini adalah
simulasi RTL sampai pengujian fisik yang sesuai dicatat terpisah.
