# Expected result UART Parallel8

Input sama dengan `src/igor_pipeline/scripts/uart_test.py`:
64 observasi LiDAR bernilai 0.8, diikuti 10 nilai 0.0.
Setelah kuantisasi, 64 nilai pertama adalah 205 (Q8.8), sisanya 0.

| Hasil | Expected |
|---|---|
| UART | 9600, 8N1, flow control off |
| Request | 153 byte: `5a a5 01 94` + `cd 00` sebanyak 64 + `00 00` sebanyak 10 + CRC8 |
| Output Q8.8 | -46, 60, 34 |
| Residual | -0.1796875, 0.234375, 0.1328125 |
| Respons lengkap | `5a a5 02 06 d2 ff 3c 00 22 00 61` |
| CRC8 respons | 0x61; mencakup opcode, length dan payload |
| Uji 50 frame | sent 50, received 50, dropped 0 |
| Total respons | 550 byte untuk 50 transaksi; bukan per detik |
| Idle/reset | Tidak ada byte respons |

Ketiga nilai adalah residual model, bukan setpoint motor. Input test tetap,
sehingga setiap respons harus sama. Protokol fabric tidak membawa frame ID.
RTT harus diukur saat run; contoh terminal tidak mengarang angka RTT.

`expected.json` menyimpan input/output lengkap, hex TX/RX dan hash model.
`request.bin` dan `response.bin` menyimpan paket biner.
`expected_terminal.txt` adalah contoh hasil sukses, bukan hasil pengukuran Jetson.
`rtl_check/simulation.log` mencatat hasil pengujian input ini di RTL produksi.

Regenerasi oracle: `python tools/generate_uart_expected.py`.
