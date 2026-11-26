# LEARNINGS — KITAB PELAJARAN & CONTINUOUS IMPROVEMENT (v2.0)

File ini menyimpan aturan permanen hasil pelajaran produksi dan diperbarui setiap selesai audit 5 episode berdasarkan data di `PERFORMANCE_LOG.csv`. Setiap aturan yang masuk ke sini **WAJIB dipatuhi** pada semua episode berikutnya (`EP002–EP100+`).

---

## Pelajaran Pra-Produksi & Produksi Pilot EP001 (DILARANG TERULANG)

1. **Asal-Usul & Tujuan Ruang (*Spatial Origin & Destination*):**
   - Karakter **tidak boleh muncul entah dari mana** di depan dinding polos/kosong.
   - Setiap ruangan wajib memiliki **pintu masuk/keluar logis** (`spatial_plan`) dan jalur gerak yang masuk akal menuju tujuan aksi (contoh `EP001`: Mas Dimas keluar dari pintu kamar kayu sedikit terbuka di dinding kanan dengan cahaya kamar hangat → melangkah ke saklar lampu Broco di samping kanan kulkas).
   - Hindari tangen visual (misalnya kepala karakter menutup jam dinding `02:00` di belakangnya).

2. **Kausalitas & Kontak Tanah (*Prop State Chain & Ground Contact*):**
   - Setiap properti hero wajib memiliki **rantai status kausal** (`prop_state_chain`) dari awal sampai akhir (contoh `EP001`: sepasang sandal jepit hijau dipakai di kedua kaki di `01A/01B` saat menekan saklar dengan tangan kosong → baru dicopot sebelah kanan di `Scene 02–07` sehingga kaki kanan nyeker dan kaki kiri TETAP memakai sandal hijau → sandal kanan terlepas jatuh di `Scene 08`).
   - Alas kaki yang dipakai di kaki wajib di-**parent ketat (`BONE`) ke tulang kaki terkait** (`foot.L` / `foot.R`) agar tidak pernah terpisah atau melayang dari jari kaki.
   - Saat kaki bersandal menapak lantai, ketinggian tulang kaki wajib memperhitungkan ketebalan sol (**`z = +0.018 m`**) dengan rotasi sol **100% datar horizontal** sehingga seluruh sol hijau + putih berada utuh di atas permukaan keramik (`z >= +0.001 m`) dan **tidak pernah tenggelam menembus lantai**.

3. **Orientasi Grip Benda Genggam (Anti-Bet Pingpong & Anti-Tembus Jari):**
   - Benda genggam (sandal, pisau, sapu, HP) wajib dipegang pada **ujung pangkal/pegangannya** (*heel/handle*) dengan **permukaan kerja menghadap ke arah target/aksi** (untuk sandal: sol rata hijau menghadap **depan-bawah ke arah lantai/kamera** siap mengeplak, BUKAN berdiri tegak menyamping seperti bet pingpong/es loli).
   - Terapkan pronasi pergelangan tangan + offset sepanjang normal telapak tangan + tekukan jari moderat melingkari tepi atas pangkal agar **0% jari menembus sol/objek**.
   - Pastikan tulang bahu (`shoulder01.L/R`) masuk daftar `POSE_BONES` yang selalu di-reset & di-keyframe setiap frame agar tidak pernah terjadi akumulasi rotasi bahu atau lengan tembus dada.

4. **Lokalitas Indonesia & Anti-Spoiler:**
   - Pakaian, alas kaki, warna kulit hangat Asia Tenggara, rambut bervolume natural, dan properti ruangan (saklar Broco, kalender dinding, sandal Swallow hijau, kuah Indomie, kolong kulkas) harus 100% terasa autentik Indonesia.
   - **Anti-Spoiler:** Jangan tampilkan objek kejutan sebelum waktunya disebut di VO (mis. jangan tampilkan sandal di tangan pada `01B` sebelum `Scene 02`).
   - **Wajib Audit Detail Statis Aset CC0:** Selalu periksa dan ubah detail bawaan aset CC0 agar cocok dengan naskah (contoh: jarum jam dinding bawaan Poly Haven selalu `10:10` → WAJIB diputar ke `02:00` dengan kontras jarum hitam tegas).

5. **Batas Aset Prosedural & 5 Arketipe Kamera POV:**
   - **DILARANG** membuat anatomi manusia atau aksesoris wajah (kacamata kotak kaku, badan balok) dari primitif kode mentah — wajib memakai rig **MPFB2** proper (`mas_dimas_ready.blend`, tanpa kacamata) dan aset **Poly Haven CC0**.
   - Wajib gunakan **5 Arketipe Kamera POV** (`insect_ground`, `aerial_erratic`, `fluid_float`, `static_object_pov`, `human_first_person`) + *floor clamp* (`z >= min_z`) + *motion blur* (`shutter=0.40` untuk video bergerak) + *secondary motion* (antena independen, kepakan sayap cepat, kedipan mata alami).

6. **Fast Storyboard + Self-QC Vision + 2 Hard Gate:**
   - Mode `storyboard` wajib berjalan cepat sebagai **Fast Draft QC** (**`270×480`**, **4 samples + OIDN**, `persistent_data=True`, *motion blur* OFF → selesai **< 1 menit** untuk 9 panel).
   - Agen **WAJIB melakukan Self-QC Vision** (membuka dan memeriksa sendiri setiap panel render terhadap seluruh 5 poin di atas) dan memperbaiki cacat fisik/visual terlebih dahulu sebelum menampilkan ke user.
   - Produksi wajib berhenti di **Hard Gate 1 (`storyboard_sheet.png` → tunggu `ACC STORYBOARD`)** lalu **Hard Gate 2 (`motion_check` `360×640` 8 samples + audio/subtitle)** sebelum render `final` (`1080×1920`, 24 samples).

---

## Siklus Audit Performa: Menunggu Batch 1 (`EP001–EP005`)

### Hipotesis Awal yang Sedang Diuji di Batch 1:
1. **Durasi Ideal:** 35–42 detik (**80–95 kata**) adalah titik manis untuk mengejar *Average Percentage Viewed (APV)* > 95%.
2. **Hook Paling Kuat:** Langsung sebutkan waktu/situasi spesifik khas Indonesia + objek POV + *Mute Test* visual di 2,5 detik pertama.
3. **Pemicu Komentar:** Ending `hard_cut_punchline` / `seamless_loop` + *pinned comment* pertanyaan terbuka tentang objek POV berikutnya.

### Format Catatan Audit (Diisi Mulai Audit Batch 1):
- **Yang Terbukti Berhasil (Pertahankan & Gandakan):** *(menunggu data 48 jam & 7 hari EP001–EP005)*
- **Yang Gagal / Bikin Penonton Swipe (Hentikan):** *(menunggu data audit)*
- **Penyesuaian Teknis (Visual / Audio / Pacing):** *(menunggu data audit)*
