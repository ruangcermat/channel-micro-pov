# CHANNEL BIBLE — JADI APA (MOBILE-FIRST 3D MICRO-POV INDONESIA, v4.2)

## 1. Identitas & Konsep Inti (RESMI DIKUNCI — v4.2)
- **Nama Channel:** **Jadi Apa** (handle cadangan: **@jadiapa3d**)
- **Unified Look-Dev (1 Bahasa Visual Tunggal):** **Tactile Matte Clay / Vinyl Diorama 3D** — estetika miniatur *stop-motion* premium berbahan *matte polymer clay* / *vinyl* taktil dengan tekstur mikro halus (sidik tekstur tanah liat halus, permukaan semi-matte lembut), pencahayaan sinematik kontras tinggi, dan **macro tilt-shift DOF** (*shallow depth of field* miniatur).
- **Karakter Maskot Permanen (`@MasDimas` di Google Flow):**
  - Pria muda anak kosan Indonesia yang ekspresif, **tanpa kacamata** agar ekspresi mata melotot, alis, dan kepanikan terbaca 100% tajam di layar HP.
  - **Ciri Visual Permanen:** Rambut hitam pendek bervolume (*textured crop*), kulit hangat Asia Tenggara bergaya *matte polymer clay*, kaus oblong **Merah Bata / Crimson (`#A62C2B`)** bertuliskan kapital tebal putih **`JADI APA`** + **garis aksen kuning** di dada, celana pendek rumahan gelap, dan **100% nyeker (*barefoot*)** di dalam kosan.
  - **Anchor Opening / Closing (Wajib Episode Non-Manusia):** Untuk episode dalam tubuh (mis. Sel Darah Putih) atau benda mati (mis. Kabel Charger), WAJIB membuka **2 detik pertama** (atau menutup di ending) dengan **`@MasDimas`** sebagai jangkar semesta sebelum/sesudah kamera masuk ke dunia mikro.
- **Format:** Faceless 3D Micro-POV Edutainment (Sudut Pandang Orang Pertama / Kedua: *"Bayangin kamu jadi..."*).
- **Premis Utama:** Memasukkan penonton langsung ke dalam tubuh, objek, hewan, atau situasi tertentu selama **30–42 detik** (naskah padat **70–95 kata**). Penonton tidak menonton ceramah, melainkan "menjadi" tokoh utama dalam diorama 3D mini-film yang lucu, tegang, sekaligus membuka wawasan.
- **Target Audiens:** Audiens Indonesia lintas usia (15–35 tahun) di YouTube Shorts, TikTok, dan Instagram Reels.
- **Posisi Unik (Pembeda dari Zack D. Films & Odd Tilt):**
  - Bukan anatomi klinis/ngilu ala Zack D. Films; bukan pula komedi sejarah penemuan benda ala Odd Tilt.
  - Fokus pada **pengalaman imersif Micro-POV bergaya Tactile Matte Clay / Vinyl Diorama**, observasi keseharian autentik Indonesia bersama **`@MasDimas`**, dan fakta sains/logika yang menyatu alami dengan cerita.

---

## 2. Gaya Bahasa & Standar Naskah (70–95 Kata | 30–42 Detik)
- **Target Panjang & Ritme VO:** **70–95 kata** untuk durasi padat **30–42 detik** (ritme `gemini-3.8-flash-tts` suara permanen **`Fenrir`**, **`VO_SPEED = 1.02`** — dilarang menumpuk `VO_SPEED >= 1.08` dengan arahan "sangat cepat"). Padat tanpa basa-basi agar *Average Percentage Viewed (APV)* tembus > 95%.
- **Pemisahan Ketat `speech_metadata` vs `vo_text` & Kalibrasi `Fenrir`:**
  - `vo_text` WAJIB berisi **murni ucapan lisan** — dilarang menyelipkan arahan akting/nada ke dalam `vo_text`. Semua arahan gaya bicara, tempo, dan emosi WAJIB dipisahkan ke `speech_metadata.style` dengan arahan yang **membumi** (hindari lonjakan teatrikal, falsetto, atau perintah "sangat cepat" yang membuat kata tertelan).
  - **Auto Verbatim & Speed QC Gate:** Setiap segmen WAJIB lolos audit mentah `faster-whisper` (`1.7–2.9 kata/detik`, kesamaan teks `≥ 0.82`, kata ganti POV seperti `kamu`/`kakimu`/`pantatmu`/`ukuranmu` 100% utuh) dan wajib hapus/timpa bersih file VO yang ditolak.
  - **Wajib Eja Angka Lisan:** Semua angka di `vo_text` WAJIB dieja sebagai kata Indonesia alami (*"jam dua pagi"*, *"tiga ratus kilometer per jam"*, *"lima setengah sentimeter"* — BUKAN `02:00`, `300 km/jam`, atau `5,5 cm`).
- **Persona Narator:** Teman nongkrong yang cerdas, ekspresif, agak nyeleneh, dan jago mendramatisasi hal sepele. Wajib pakai kata **"kamu"** sejak detik pertama.
- **Aturan Anti-Kaku:**
  - ❌ DILARANG buka video dengan: *"Halo guys"*, *"Tahukah kamu"*, *"Pernahkah kalian berpikir"*, atau *"Secara ilmiah..."*.
  - ❌ DILARANG memakai bahasa terjemahan kaku (*"Anda kemudian mengalami..."*).
  - ✅ Kalimat pendek lisan (maksimal 10–14 kata/kalimat) + fakta sains sebagai **alasan kejadian di dalam cerita**.

---

## 3. Rumus Retensi v4.2, Rotasi 4 Hook, Curiosity-Loop & Tes Private Share
1. **Rotasi 4 Arketipe Hook (Detik 0–3 + Lolos *Mute Test*):**
   Wajib rotasi lintas episode agar pembukaan tidak terasa repetitif:
   - **Hook 1 — Krisis *In-Media-Res*:** Langsung lempar penonton ke detik bahaya/kaget tanpa pengantar (*"Jam dua pagi, lampu dapur mendadak nyala..."*).
   - **Hook 2 — Ironi / Kontras Absurd:** Pertentangan lucu antara ekspektasi dan nasib sial subjek POV (*"Kerjamu cuma satu, tapi majikanmu maksa..."*).
   - **Hook 3 — Ancaman Sains / Countdown Nyata:** Fakta biologis/fisika ekstrem yang langsung memicu ketegangan detik itu juga.
   - **Hook 4 — *Relatable* Keseharian Indonesia:** Situasi kosan/jalanan super akrab yang langsung bikin penonton merasa *"anjir ini gue banget"*.
   - Setiap hook wajib lolos ***Mute Test*** (`silent_readability`): bahkan tanpa suara, subjek POV dan bahayanya terbaca dalam 0,5–1 detik pertama.
2. **Curiosity-Loop ("Tapi / Akibatnya"):**
   - **DILARANG** menyusun alur datar bertipe *"Lalu... Lalu... Kemudian..."*.
   - Setiap transisi antar-beat WAJIB dihubungkan sebab-akibat/hambatan berantai memakai logika **"Tapi..."** (hambatan baru/twist) atau **"Akibatnya..."** (konsekuensi langsung) sehingga penonton terkunci sampai akhir.
3. **Visual Pattern Interrupt Tiap 2–4 Detik via Timecode `[0-3s]`:**
   - Di dalam naskah & Scene Map, wajib pecah ritme visual dengan penanda timecode eksplisit (**`[0-3s]`**, **`[3-6s]`**, **`[6-9s]`**, dst.) — pastikan ada perubahan visual nyata (ganti sudut kamera, *whip-pan*, ekspresi ekstrem, *macro push-in*, aksi fisik, atau perubahan cahaya) setiap **2–4 detik** agar mata tidak pernah bosan.
4. **Mid-Video Re-Hook (Detik 14–22) & Ending Tajam (`ending_type`):**
   - Wajib ada lonjakan ketegangan/twist baru di pertengahan video dan ending **`hard_cut_punchline`** atau **`seamless_loop`**. **Tanpa Top Badge Kuning:** DILARANG menambahkan *top badge* kuning di atas layar agar tidak pernah terjadi teks ganda dengan subtitle karaoke bawah maupun spoiler punchline.
5. **Tes Private Share WA/DM (Wajib Lolos Sebelum Finalisasi Naskah):**
   - Uji setiap naskah dengan 1 pertanyaan keras: *"Apakah penonton bakal nge-forward video ini ke grup WA atau DM teman dengan komentar 'gue banget' / 'gila baru tahu'?"* Jika tidak ada momen *relatable* atau *twist* yang layak dibagikan secara pribadi, rombak sebelum lanjut!

---

## 4. Alur Produksi Baku — Arsitektur Mobile-First v4.2 (Zero Blender, Zero Colab)
Seluruh produksi episode (`EP001–EP100+`) mengikuti **5 Tahap Baku Audio-First & Mobile-First v4.2**:

1. **Tahap 1 — 4-Pass Writer's Room di Gemini (70–95 Kata | 30–42 Detik):**
   - **Pass 1 (Arsitektur & Hook):** Tentukan premis, pilih **1 dari 4 Arketipe Hook**, jangkar `@MasDimas` (jika non-manusia), rantai **Curiosity-Loop ("Tapi / Akibatnya")**, *Mid-Video Re-Hook*, dan `ending_type`.
   - **Pass 2 (WAJIB — Self-Roast Kejam Penonton Bosan):** Evaluasi draf secara brutal dari sudut pandang penonton TikTok/Shorts yang siap *swipe* dalam 1 detik. **WAJIB temukan & rombak minimal 3 titik lemah** (mis. kalimat datar/ceramah, jeda visual > 4 detik, transisi tanpa *"Tapi/Akibatnya"*, atau gagal **Tes Private Share WA/DM**).
   - **Pass 3 (Ritme Lisan, Timecode & Logika Ruang):** Poles bahasa lisan padat 70–95 kata (eja semua angka), kunci **Visual Pattern Interrupt tiap 2–4d (`[0-3s]`, `[3-6s]`, ...)**, lolos *Mute Test*, dan audit logika ruang/lokalitas Indonesia.
   - **Pass 4 (Kompilasi VO Spec):** Hasilkan `04_episodes/<ep_id>/<ep_id>_vo_spec.json` berisi segmen `vo_text` murni ucapan lisan + `speech_metadata` terpisah.
2. **Tahap 2 — Generate VO Utuh Audio-First di Antigravity Remote (`03_pipeline/generate_vo_v4.py`):**
   - Panggil **`gemini-3.8-flash-tts`** (`Fenrir`, **`VO_SPEED = 1.02`**, pisahkan arahan gaya bicara membumi ke `speech_metadata.style`, `vo_text` murni ucapan lisan & angka dieja) lalu wajib lolos **Auto Verbatim & Speed QC Gate** (`faster-whisper` mentah `1.7–2.9 kata/detik`, kesamaan `≥ 0.82`, kata POV utuh, auto-retry hingga 2×).
   - Jalankan `faster-whisper` (`condition_on_previous_text=False`, anti-ekor nol-durasi) untuk menyusun **`vo_timing_manifest.json`** (durasi aktual tiap segmen + rekomendasi panjang klip Flow bulat ke atas **3–10 detik**) dan **`subtitles.ass`** (karaoke bawah, **TANPA top badge kuning**).
   - Timpa bersih (nol duplikat) **`vo_master.wav`**, **`vo_timing_manifest.json`**, dan **`subtitles.ass`** ke Google Drive `04_episodes/epXXX/`.
3. **Tahap 3 — Gerbang Tabel Scene Map (*Text Only*) → Paket Prompt Google Flow di Gemini:**
   - **GERBANG WAJIB — Tabel Scene Map (*Text Only*):** Setelah membaca `vo_timing_manifest.json` dari Drive, Gemini WAJIB menyajikan **Tabel Scene Map berbasis teks terlebih dahulu** (kolom: `Shot`, `Timecode [0-3s]`, `Durasi VO & Klip Flow ≤10s`, `Lokasi/Master Empty Location`, `Aksi & Visual Pattern Interrupt`, `Planned Exit Transition`, dan `Audio Foley Only`) untuk ditinjau/ACC user **SEBELUM** menulis paket prompt Flow!
   - **Flow Prompt Pack (Setelah Scene Map ACC):** Barulah Gemini mengeluarkan paket prompt **Tactile Matte Clay / Vinyl Diorama 3D** (Master Empty Location + karakter `@MasDimas` + keyframe stills Nano Banana 0-kredit + prompt klip Omni Flash 1.2) yang presisi sesuai durasi tiap segmen VO.
4. **Tahap 4 — Produksi Visual dari HP di Google Flow (`flow.google.com`):**
   - Kunci **Master Empty Location** & karakter **`@MasDimas`** + seluruh keyframe stills di **Nano Banana (0 kredit)** (buat End Frame dengan mengedit Start Frame).
   - Generate klip video **Omni Flash 1.2** memakai strategi **360p Draft-First (`Outputs=1`) → Omni Edit di 360p → Upscale `1080p` gratis (0 kredit)** hanya untuk *Keepers* (`9:16`, **WAJIB 3–10 detik/klip**, audio **foley only** tanpa musik/dialog/teks).
   - Unggah seluruh klip mentah ke Google Drive `04_episodes/epXXX/raw_clips/shot_01.mp4`, `shot_02.mp4`, dst.
5. **Tahap 5 — Auto-Assembly & Master Export di Antigravity Remote (`03_pipeline/assemble_flow_v4.py`):**
   - Tarik `vo_master.wav`, `vo_timing_manifest.json`, `subtitles.ass`, dan `raw_clips/shot_*.mp4` dari Drive.
   - Potong bersih kelebihan durasi tiap klip di FFmpeg agar 100% pas dengan durasi segmen VO (**DILARANG *freeze frame* terakhir**).
   - Campur **3-Layer Audio Master (`-14 LUFS`)**:
     1. **VO (`-6 dB`):** `vo_master.wav` dominan & jernih.
     2. **Native Foley Flow (`-10 dB` + auto-ducking):** Suara foley organik bawaan klip Omni Flash 1.2 yang otomatis merunduk saat VO berbicara.
     3. **BGM CC0 (`-22 dB` + auto-ducking):** Musik pengiring ringan yang otomatis merunduk di bawah VO.
   - Bakar subtitle karaoke **`subtitles.ass`** (**Golden Hero Zone `1080×1920`**, `MarginV=380`, **TANPA top badge kuning dobel**) dan simpan **1 file `final_epXXX.mp4`** (`1080×1920`, `libx264`, `-crf 18`, `-pix_fmt yuv420p`) langsung ke Google Drive `04_episodes/epXXX/`.

---

## 5. Golden Hero Zone 9:16 & Standar Framing Mobile (`1080×1920`)
- **Golden Hero Zone:** Wajah ekspresif `@MasDimas` & aksi utama WAJIB berada di **`x: 100–900px, y: 260–1250px`** agar 100% aman dari bar atas, tombol UI kanan TikTok/Shorts/Reels, dan zona subtitle bawah (`MarginV = 380`).
- **Teks Layar Tunggal:** Hanya subtitle karaoke bawah (2–3 kata per chunk, ≤ 18 karakter, putih tebal beroutline hitam + sorotan kuning). Nol teks bawaan dari prompt Flow, nol *top badge* kuning ganda.
