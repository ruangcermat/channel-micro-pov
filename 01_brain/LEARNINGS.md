# LEARNINGS — KITAB PELAJARAN & CONTINUOUS IMPROVEMENT (v3.0)

File ini menyimpan aturan permanen hasil pelajaran produksi dan diperbarui setiap selesai audit 5 episode berdasarkan data di `PERFORMANCE_LOG.csv`. Setiap aturan yang masuk ke sini **WAJIB dipatuhi** pada semua episode berikutnya (`EP002–EP100+`).

---

## Pelajaran Permanen Pilot EP001 (DILARANG TERULANG DI EP002–EP100+)

1. **Hukum "Anti-Senam Tulang" & Titik Ambil Properti Statis:**
   - **DILARANG** membuat koreografi tubuh rumit melepas alas kaki atau pakaian dari rig tubuh yang sedang bergerak (rawan klip lantai, sandal melayang/lepas dari jari kaki, atau pose tulang aneh).
   - Di dalam rumah/kosan, **Mas Dimas selalu 100% nyeker (*barefoot*)** sejak awal sampai akhir. Untuk pengambilan properti (sandal, HP, alat dapur), selalu gunakan **titik ambil statis** (contoh `EP001`: rak sandal kayu rendah di bawah jam dinding `02:00` yang berisi sepasang sandal jepit Swallow hijau + 1 pasang sepatu santai) atau pose *upper-body* + ekspresi wajah ARKit (`BOOST 1.6`).

2. **Unified Look-Dev (*Stylized Semi-Matte*) & Jangkar Semesta:**
   - Kunci 1 bahasa visual tunggal untuk manusia maupun non-manusia: kulit & pakaian Mas Dimas serta objek episode non-manusia (Sel Darah Putih, Kabel Charger) wajib memakai permukaan *soft-matte* (**`roughness 0.55–0.65`**) bertekstur halus tanpa pori-pori tajam menyeramkan + grading identik **`AgX Medium High Contrast` + `Macro DOF` + `post.py`**.
   - Episode dalam tubuh atau benda mati WAJIB dibuka 2 detik pertama (atau ditutup ending) dengan **Mas Dimas** sebagai jangkar semesta.

3. **Asal-Usul Ruang, Pintu Tertutup & Kunci Tatapan (*Spatial & Eye-Line Lock*):**
   - Karakter tidak boleh muncul dari dinding kosong; setiap ruangan wajib punya pintu masuk/keluar logis (`spatial_plan`).
   - Begitu karakter masuk ruangan (`~00:02.0`), **tutup rapat daun pintu (`rot_z = 0°`)** agar ruangan terasa realistis dan otomatis membentuk sudut **buntu** (*"kanan buntu"* bersama rak/kardus saat *whip-pan*).
   - Begitu lampu menyala dan karakter melihat subjek POV, **kunci arah kepala & tatapan mata ke target** (JANGAN menoleh kembali ke pintu kosong!).
   - Untuk langkah/hentakan kaki (seperti Scene 05 menutup kolong kulkas), animasikan ayunan langkah cepat & alami — **DILARANG** menggantung kaki diam di udara berdetik-detik!
   - Saat sprint kamera FOV lebar (`112°`), jaga lintasan di tengah jalur/garis nat agar tepi furnitur sudut bawah tidak menyerempet lensa.

4. **Orientasi Grip Benda Genggam & Lokalitas Indonesia:**
   - Benda genggam (sandal, pisau, sapu) dipegang di ujung pangkalnya dengan permukaan kerja menghadap arah target/aksi (sol hijau datar menghadap depan-bawah, bukan tegak seperti bet pingpong, dan **0% jari menembus objek**).
   - Pastikan `shoulder01.L/R` selalu masuk `POSE_BONES` (di-reset & di-keyframe setiap frame).
   - Selalu audit detail statis aset CC0 (jam dinding Poly Haven `10:10` → putar ke `02:00` dengan jarum hitam tegas).

5. **Adaptive Multi-Keyframe Fast Storyboard Gate (Pengganti Video `motion_check`) & Hybrid Pipeline:**
   - Hentikan penggunaan render video `motion_check` yang lambat di CPU. Ganti dengan **Adaptive Multi-Keyframe Fast Storyboard** (`270×480`, `4 samples + OIDN`, `persistent_data=True`, *motion blur* OFF — selesai ~1–2 menit).
   - **JANGAN batasi jumlah sheet/panel secara kaku:** render sebanyak keyframe transisi yang diperlukan (maks. 8–9 panel/sheet: `storyboard_sheet_1.png`, `storyboard_sheet_2.png`, dst.) termasuk **simulasi kotak subtitle ending**. Wajib **Self-QC Vision** → **STOP TOTAL** menunggu **`ACC STORYBOARD`** sebelum menyiapkan bundle atau render `final`.
   - Pilih `render_pipeline` paling hemat di `spec_schema.json`: `blender_3d` (default bergerak 3D), `parallax_25d` (`static_object_pov` tenang), atau `ai_i2v` (Sejarah/Alam Ekstrem berskala masif via Google Flow / Veo).

6. **Audio Mix, Anti-Hallucination Whisper & Anti-Spoiler Ending:**
   - `faster-whisper` dengan `initial_prompt` dapat memicu *hallucination loop* kata nol-durasi di ekor keheningan (menyebabkan subtitle akhir macet). WAJIB aktifkan `condition_on_previous_text=False`, dekoder WAV 16kHz `float32` bebas PyAV, filter pemotong ekor nol-durasi, dan skala presisi `1 / VO_SPEED`.
   - **Anti-Spoiler Badge:** Jangan tampilkan badge teks punchline ending sejak awal scene terakhir; tunda hingga detik punchline (mis. `00:45.5`) atau kosongkan badge atas scene terakhir.
   - Pastikan SFX kontinyu bernada ramai (seperti `skitter_fast`) diturunkan sekitar **`-7 dB` di bawah VO** agar narasi cepat tetap 100% jernih.

---

## Siklus Audit Performa: Menunggu Batch 1 (`EP001–EP005`)

### Hipotesis Awal yang Sedang Diuji di Batch 1:
1. **Durasi Ideal:** 35–42 detik (**80–95 kata**) untuk mengejar *Average Percentage Viewed (APV)* > 95%.
2. **Hook Paling Kuat:** Waktu/situasi spesifik Indonesia + objek POV + *Mute Test* visual di 2,5 detik pertama.
3. **Pemicu Komentar:** Ending `hard_cut_punchline` / `seamless_loop` + *pinned comment* pertanyaan terbuka.

### Format Catatan Audit (Diisi Mulai Audit Batch 1):
- **Yang Terbukti Berhasil (Pertahankan & Gandakan):** *(menunggu data 48 jam & 7 hari EP001–EP005)*
- **Yang Gagal / Bikin Penonton Swipe (Hentikan):** *(menunggu data audit)*
- **Penyesuaian Teknis (Visual / Audio / Pacing):** *(menunggu data audit)*
