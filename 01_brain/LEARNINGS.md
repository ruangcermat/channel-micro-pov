# LEARNINGS — KITAB PELAJARAN & ATURAN PERMANEN JADI APA (v4.2)

File ini menyimpan aturan permanen hasil pelajaran produksi dan diperbarui setiap selesai audit 5 episode berdasarkan data di `PERFORMANCE_LOG.csv`. Setiap aturan di sini **WAJIB dipatuhi** pada semua episode **Arsitektur Mobile-First v4.2** (`EP001–EP100+`).

---

## A. Pelajaran Permanen Logika Ruang, Lokalitas & Audio (Warisan Pilot EP001)

1. **Asal-Usul Ruang, Pintu Tertutup & Kunci Tatapan (*Spatial & Eye-Line Lock*):**
   - Karakter tidak boleh muncul tiba-tiba dari dinding kosong; setiap ruangan wajib punya pintu masuk/keluar logis yang konsisten lintas shot.
   - Begitu `@MasDimas` masuk ruangan, **pintu kamar kanan wajib tertutup rapat** di shot-shot berikutnya agar ruangan terasa realistis dan otomatis membentuk sudut **buntu** (*"kanan buntu"* bersama rak sandal & tumpukan kardus).
   - Begitu lampu menyala dan karakter melihat subjek POV, **kunci arah kepala & tatapan mata ke target** (jangan menoleh kembali ke pintu kosong!).
   - Di dalam rumah/kosan, `@MasDimas` selalu **100% nyeker (*barefoot*)** dan mengambil properti (sandal jepit Swallow hijau, HP, alat dapur) dari **titik ambil statis** (rak sandal rendah di bawah jam `02:00`, meja, nakas).
   - Selalu cek detail lokalitas Indonesia di setiap keyframe still sebelum generate video: jam dinding menunjukkan **`02:00`** (bukan `10:10`), sandal jepit Swallow hijau-putih, saklar Broco, lantai keramik bernat, dan properti kosan autentik.

2. **Anti-Hallucination `faster-whisper` & Presisi Timing Audio-First:**
   - `faster-whisper` dapat memicu *hallucination loop* kata nol-durasi di ekor keheningan (membuat subtitle akhir macet). WAJIB aktifkan **`condition_on_previous_text=False`**, dekoder WAV 16kHz `float32` bebas PyAV, pemotong ekor nol-durasi (`end - start <= 0.015s`), dan skala presisi `1 / VO_SPEED`.
   - `vo_text` WAJIB murni ucapan lisan dengan **semua angka dieja** (*"jam dua pagi"*, *"tiga ratus kilometer per jam"*); arahan gaya bicara/nada WAJIB dipisahkan ke `speech_metadata` agar tidak pernah dibacakan oleh `gemini-3.8-flash-tts`.

3. **Anti-Spoiler Ending & Audio Mix Bersih (`-14 LUFS`):**
   - Jangan pernah membocorkan punchline ending lewat teks di awal shot terakhir.
   - Campurkan 3 layer audio secara seimbang (**VO `-6 dB`** dominan, native foley klip Flow `-10 dB` + *sidechain ducking*, BGM CC0 `-22 dB` + *sidechain ducking*, master **`-14 LUFS`**). Prompt klip Flow WAJIB meminta **foley only — tanpa musik, tanpa dialog, tanpa teks**.

4. **Pelajaran Kalibrasi VO `Fenrir` (Pilot EP001 — Dilarang Terulang):**
   - **Default Permanen `Fenrir` + `VO_SPEED = 1.02`:** Dilarang menumpuk `VO_SPEED >= 1.08` dengan frasa global `"ritme cepat"` atau arahan `"sangat cepat"` per segmen — penumpukan tempo membuat `Fenrir` melesat > `3.0 kata/detik` hingga menelan konsonan dan salah baca kata ganti POV (`"kakimu"` → `"kakinya"`, `"celah rak"` menyatu).
   - **Arahan `speech_metadata.style` Membumi (Anti-Teatrikal & Anti-Falsetto):** Gunakan arahan akting yang natural, mengalir seperti teman nongkrong, dengan suara dada mantap untuk momen tegang — hindari kata pemancing nada teatrikal/melengking (`"heboh dramatis penuh kepanikan"`, `"patah-patah"`) agar `Fenrir` tidak melonjak falsetto atau memutus frasa secara kaku.
   - **Wajib Lolos Auto Verbatim & Speed QC Gate + Clean Overwrite:** Setiap segmen WAV mentah WAJIB diaudit otomatis oleh `faster-whisper` (`condition_on_previous_text=False`, tanpa `initial_prompt`) terhadap `vo_text` dengan kecepatan bicara **`1.7–2.9 kata/detik`**, kesamaan teks `≥ 0.82`, dan verifikasi kata ganti POV (`kamu`, `kakimu`, `pantatmu`, `ukuranmu`, dst.). Segmen cacat wajib langsung dihapus & auto-retry hingga 2× dengan arahan artikulasi tenang, dan file master (`vo_master.wav`, `vo_timing_manifest.json`, `subtitles.ass`) selalu ditimpa bersih tanpa meninggalkan duplikat (`vo_master (1).wav`) di lokal maupun Google Drive.

---

## B. Aturan Permanen Google Flow v4.2 (Mobile-First Omni Flash 1.2)

4. **(a) Kunci Stills 0-Kredit Dulu (Edit Start Frame untuk End Frame):**
   - Selalu generate dan ACC seluruh keyframe stills di **Nano Banana (0 kredit)** sebelum membakar kredit video.
   - Untuk shot transisi, buat **End Frame** dengan **mengedit Start Frame** (bukan generate dari nol) agar tata ruang, pencahayaan, properti, dan penampilan `@MasDimas` 100% konsisten.

5. **(b) Mode `Frames` dan `Omni Extend` Khusus Web (`flow.google.com`):**
   - Mode `Frames` (Start/End Frame) dan `Omni Extend` hanya tersedia di antarmuka Web.
   - Saat bekerja dari HP, WAJIB buka **`flow.google.com`** melalui **Chrome HP dengan mode Desktop (*Desktop site*)** aktif.

6. **(c) Mode `Frames` dan `Ingredients` Terpisah di Video Standar:**
   - Pada mode Video standar Google Flow, fitur `Frames` (Start/End Frame) dan `Ingredients` (referensi karakter/objek `@MasDimas`) berada di jalur terpisah — jangan mencampur ekspektasi keduanya sekaligus dalam satu prompt Video standar; pilih mode yang paling tepat untuk tiap shot.

7. **(d) Wajib Klip ≤ 10 Detik (`3–10 Detik / Klip`):**
   - Setiap klip video **Omni Flash 1.2** WAJIB berdurasi **3 sampai 10 detik** (bulat ke atas dari durasi segmen VO di `vo_timing_manifest.json`).
   - **DILARANG** generate klip 11–15 detik karena memicu **tarif 2× lipat kredit** dan menghilangkan fasilitas **upscale 1080p gratis (0 kredit)**. Jika segmen VO > 10 detik, WAJIB pecah menjadi 2 shot ≤ 10 detik.

8. **(e) Kunci `Flow Agent` ke `Ask for permission: Always`:**
   - Wajib setel pengaturan `Flow Agent` ke **`Ask for permission: Always`** agar agen Flow tidak pernah mengeksekusi generasi video berbayar atau menghabiskan kredit tanpa persetujuan eksplisit user.

9. **(f) Potong Kelebihan Durasi Klip di FFmpeg (DILARANG *Freeze Frame* Terakhir):**
   - Karena klip Flow berdurasi bulat (`3–10d`) sedikit lebih panjang dari durasi VO aktual (mis. VO `4,2d` → klip Flow `5d`), `03_pipeline/assemble_flow_v4.py` WAJIB memotong bersih kelebihan ekor klip lewat FFmpeg (`-t`) agar ritme visual selalu hidup dan pas 100% dengan VO — **DILARANG membekukan (*freeze*) frame terakhir**.

10. **(g) Matikan Semua Top Badge Kuning:**
    - Seluruh *top badge* kuning (`on_screen_text`) di atas layar dimatikan permanen di `subtitles.ass` (`generate_vo_v4.py` & `assemble_flow_v4.py`) agar tidak pernah bertabrakan / teks ganda dengan subtitle karaoke bawah (`JAM 2 PAGI` vs `JAM DUA PAGI.`).

11. **(h) Master Empty Location Kosong Tanpa Karakter + Deskripsi Ruang Identik Antar-Shot:**
    - Sebelum merakit keyframe shot mana pun, wajib generate & kunci 1 still **Master Empty Location** (ruangan kosong 100% tanpa karakter di Nano Banana 0-kredit) sebagai jangkar tata ruang.
    - Di seluruh prompt antar-shot dalam ruangan yang sama, WAJIB salin-tempel **deskripsi ruang yang 100% identik** (posisi pintu, warna dinding, pencahayaan, properti utama) agar latar diorama tidak berubah-ubah antar klip.

12. **(i) Strategi `360p` Draft-First (`Outputs=1`) → `Omni Edit` di `360p` → Upscale `1080p` Gratis Hanya untuk *Keepers* `≤ 10s`:**
    - DILARANG langsung generate banyak variasi (`Outputs > 1`) atau langsung merender resolusi tinggi.
    - Selalu uji klip pertama di **`360p` dengan `Outputs = 1`** untuk memverifikasi gerak & akting. Jika ada cacat minor, perbaiki lewat **`Omni Edit` tetap di `360p`**. Baru lakukan **Upscale `1080p` gratis (0 kredit)** khusus untuk klip final (*Keepers*) yang berdurasi **`≤ 10 detik`**.

13. **(j) *Planned Exit Transition* di Akhir Klip:**
    - Setiap klip Flow WAJIB merancang ***Planned Exit Transition*** di 0,5–1 detik terakhir (mis. *whip-pan* cepat, *camera rush* ke objek/bayangan, pintu menutup, atau sapuan properti melewati lensa) agar sambungan potongan antar-shot di FFmpeg terasa menyatu, dinamis, dan tidak kaku.

14. **(k) Hukum Maksimal 3 Percobaan + Pengingat Klik Ulang Picker `@` di Flow UI:**
    - **Hukum Maksimal 3 Percobaan:** Jika sebuah shot gagal/aneh setelah **3 kali percobaan**, **STOP** membakar kredit — ganti sudut kamera, sederhanakan aksi, atau perbaiki keyframe still-nya di Nano Banana 0-kredit sebelum mencoba lagi.
    - **Pengingat Klik Ulang Picker `@`:** Setiap kali menempel (*paste*) prompt atau mengulang generasi di Flow UI, WAJIB **klik ulang picker `@`** untuk memilih `@MasDimas` / ingredient terkait agar benar-benar terikat sebagai referensi visual aktif (bukan sekadar teks `@MasDimas` biasa!).

---

## Siklus Audit Performa: Menunggu Batch 1 (`EP001–EP005`)

### Hipotesis Awal yang Sedang Diuji di Batch 1:
1. **Durasi Ideal:** **30–42 detik (70–95 kata)** untuk mengejar *Average Percentage Viewed (APV)* > 95%.
2. **Hook Paling Kuat:** Rotasi 4 Arketipe Hook + visual *Tactile Matte Clay Diorama* + *Mute Test* di 2,5 detik pertama.
3. **Pemicu Share & Komentar:** Lolos **Tes Private Share WA/DM** + ending `hard_cut_punchline` / `seamless_loop` + *pinned comment* pertanyaan terbuka.

### Format Catatan Audit (Diisi Mulai Audit Batch 1):
- **Yang Terbukti Berhasil (Pertahankan & Gandakan):** *(menunggu data 48 jam & 7 hari EP001–EP005)*
- **Yang Gagal / Bikin Penonton Swipe (Hentikan):** *(menunggu data audit)*
- **Penyesuaian Teknis (Visual / Audio / Pacing):** *(menunggu data audit)*
