# Teknik optimasi RTL IGOR: weights, bias, dan accumulator

Untuk cerita desain lengkap beserta 30 kelompok fun facts, angka fitted, screenshot GUI Quartus dan pustaka vendor, baca [Fun facts dan keputusan desain Parallel8](FUN_FACTS_AND_DESIGN_RATIONALE.md).

Dokumen ini menjelaskan teknik yang sudah digunakan oleh core Parallel8 dan
kandidat penghematan berikutnya. Istilah yang digunakan adalah **weights**,
**bias**, dan **accumulator**. Kandidat belum mengubah RTL atau image pada board.

Lihat [block diagram core sederhana](IGOR_CORE_DIAGRAM.md) untuk alur memory,
input, weights, bias, accumulator, activation dan output; file draw.io dapat diedit.

## Cara perhitungan satu neuron

- **Weights** menentukan kontribusi setiap input terhadap neuron.
- **Bias** menjadi nilai awal perhitungan neuron.
- **Accumulator** menyimpan hasil penjumlahan sementara selama seluruh input diproses.

```text
accumulator = bias << 8
untuk setiap input:
    accumulator = accumulator + input × weights
hasil = activation(accumulator)
```

Input, weights, dan bias saat ini memakai kode integer dengan skala 1/256.
Perkalian menghasilkan skala 1/65.536, sehingga bias digeser delapan bit
sebelum masuk accumulator. Activation mengambil hasil pembagian aritmetika
dengan 256, lalu menerapkan ReLU/clamp sesuai layer. Urutan operasi, signed
arithmetic, pembulatan, dan batas saturasi harus tetap konsisten.
Implementasi: [igor_src_policy_core.v](../experiments/parallel8/igor_src_policy_core.v).

## Teknik yang sudah digunakan

| Teknik | Implementasi Parallel8 | Manfaat |
|---|---|---|
| Delapan lane MAC | Delapan weights dibaca dan delapan accumulator diperbarui bersamaan pada state MAC | Memproses delapan neuron secara paralel |
| Banking weights dan bias | Delapan bank ROM sinkron, masing-masing 4.096 × 16 bit | Menyediakan data untuk delapan lane tanpa satu port bersama |
| Reuse operand | Satu input dibagikan ke delapan lane | Menggunakan input yang sama untuk delapan weights berbeda |
| Reuse MAC | Setiap lane memakai kembali multiplier dan accumulator untuk input berikutnya | Tidak membuat multiplier terpisah untuk setiap koneksi jaringan |
| Aktivasi sederhana | Pergeseran/pemilihan bit, pembanding, ReLU dan clamp | Menghindari pembagian umum atau fungsi floating-point |

Hasil build saat ini: **3.303 ALM, 6.277 register, 64 M10K, 8 DSP**.
Latensi core: **6.916 siklus × 20 ns = 138,32 µs**, pada 50 MHz.
Sumber: [Fitter summary](../experiments/parallel8/output_files/igor_src_policy.fit.summary),
[timing summary](../experiments/parallel8/output_files/igor_src_policy.sta.summary),
dan [acceptance receipt](../experiments/parallel8/artifacts/acceptance.json).
ALM adalah satuan resource logika Cyclone V; bukan luas ASIC atau jumlah ALU.

## Kandidat optimasi berikutnya

### 1. Simpan weights dan bias dalam signed 9-bit

Pemeriksaan langsung delapan file `bank0.mem` sampai `bank7.mem` pada
18 Oktober 2026 menemukan rentang seluruh weights dan bias aktif
**−123 sampai 129**. Signed 8-bit tidak cukup untuk 129; signed 9-bit cukup.
Setiap bank memiliki 2.297 kata parameter dan dipad sampai 4.096 kata.

Representasi internal 16-bit dapat dieksplorasi menjadi 9-bit dengan
**nilai integer dan skala yang sama**. Data negatif harus di-encode dalam
two's complement 9-bit, kemudian di-sign-extend saat diperlukan. Ini tidak
memerlukan pembulatan ulang weights atau bias selama seluruh nilainya tetap
terwakili. Model baru wajib diperiksa ulang rentangnya.

Lebar penyimpanan logis berkurang **43,75%**: `(16−9)/16`.
Untuk delapan bank berkapasitas sama, kebutuhan logis berubah dari
524.288 menjadi 294.912 bit. **Jumlah M10K aktual belum diketahui** sampai
kompilasi; konfigurasi blok, kedalaman dan banking menentukan hasil fisiknya.
Antarmuka input/output 16-bit dapat tetap dipertahankan.

### 2. Tentukan lebar accumulator dari batas matematis

Accumulator saat ini signed 40-bit. Kandidat lebar lebih kecil harus
dibuktikan dengan batas setiap neuron, termasuk seluruh partial sum:

```text
|partial sum| <= |bias| × 256 + Σ(|input maksimum| × |weights|)
```

Batas input harus mengikuti domain tiap layer: observasi yang diterima core
dan rentang hidden activation tidak sama. Batas atas/bawah harus muat dalam
signed accumulator yang dipilih, sebelum activation melakukan clamp.
Pengurangan lebar berpotensi menghemat register dan adder; jumlah ALM yang
dihemat baru dapat dinyatakan dari hasil Fitter. Jangan memotong accumulator
hanya berdasarkan hasil beberapa contoh simulasi.

### 3. Pindahkan hidden activation dari register ke memori blok

Hidden activation memiliki **(128+64) × 16 = 3.072 bit penyimpanan logis**.
Array ini merupakan kandidat pemetaan ke memori blok agar register dan mux
pembacaan berkurang. Angka 3.072 bukan jaminan pengurangan 3.072 fitted register.
Port, banking, dan tambahan latensi baca sinkron perlu disesuaikan dengan FSM.
Jumlah M10K dapat bertambah meskipun ALM/register turun.

### 4. Optimalkan pemetaan multiplier dan accumulator ke DSP

Periksa apakah multiplier, adder accumulator, dan register terkait dapat
memanfaatkan fasilitas DSP secara lebih lengkap. Tujuannya mengurangi logika
ALM di sekitar operasi MAC. Signed arithmetic, reset, enable, dan urutan update
harus cocok dengan kemampuan DSP Cyclone V. Jangan mengklaim DSP berkurang
hanya karena weights dipersempit; granularitas DSP menentukan pemetaan aktual.

Panduan resmi: [Altera — inferensi multiplier, DSP dan memori dari HDL](https://docs.altera.com/r/docs/683283/18.1/design-compilation-user-guide-quartus-prime-standard-edition/inferring-multiplier-dsp-and-memory-functions-from-hdl-code?contentId=wmnswszCTQKsOuMH4H_cqw).

### 5. Gunakan clock enable dan jadwal baca yang efisien

Hentikan pembaruan register/data memori saat tidak diperlukan dengan clock
enable yang sesuai. Sasaran utamanya menurunkan switching dan daya dinamis;
penghematan ALM tidak otomatis terjadi. Hindari membuat gated clock dari
logika biasa. Kandidat prefetch dapat membaca weights berikutnya sambil MAC
menggunakan data sebelumnya, tetapi kebutuhan register/control bisa bertambah.

### 6. Pertahankan keseimbangan area dan latensi

Mengurangi jumlah lane atau berbagi lebih banyak operator dapat menghemat
DSP, tetapi menambah siklus. Karena target core **<160 µs**, delapan lane
dipertahankan sebagai titik awal optimasi. Resource minimum bukan satu-satunya
kriteria: hasil numerik, safety, timing dan latensi harus tetap terpenuhi.

## Kriteria penerimaan

1. Buat kandidat terpisah; pertahankan SOF yang sudah berhasil diprogram.
2. Periksa weights/bias hasil encoding dan seluruh hidden/output terhadap
   oracle integer; hasil harus identik jika tekniknya lossless.
3. Uji batas input, overflow accumulator, saturation, reset, abort, E-stop,
   transaksi tidak valid, watchdog dan recovery yang terdampak perubahan.
4. Jalankan Quartus full compilation dan periksa seluruh timing corner,
   pin assignment, ALM/register/M10K/DSP serta latensi core <160 µs.
5. Catat source, laporan, SHA256 dan SOF kandidat. Perubahan daya memerlukan
   analisis ulang dengan kondisi yang sebanding; ALM lebih kecil belum tentu
   menghasilkan daya total lebih kecil.

**Status:** teknik pada bagian "sudah digunakan" didukung build Parallel8.
Teknik pada bagian "kandidat" adalah usulan; belum ada angka penghematan
hasil kompilasi atau perubahan bitstream dari dokumen ini.
