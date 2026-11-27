# CHANNEL BIBLE — JADI APA (MOBILE-FIRST 3D MICRO-POV INDONESIA, v4.0)

## 1. Identitas & Konsep Inti (RESMI DIKUNCI — v4.0)
- **Nama Channel:** **Jadi Apa** (handle cadangan: **@jadiapa3d**)
- **Unified Look-Dev (1 Bahasa Visual Tunggal):** **Tactile Matte Clay / Vinyl Diorama 3D** — estetika miniatur *stop-motion* premium berbahan *matte polymer clay* / *vinyl* taktil dengan tekstur mikro halus (sidik tekstur tanah liat halus, permukaan semi-matte lembut), pencahayaan sinematik kontras tinggi, dan **macro tilt-shift DOF** (*shallow depth of field* miniatur).
- **Karakter Maskot Permanen (`@MasDimas` di Google Flow):**
  - Pria muda anak kosan Indonesia yang ekspresif, **tanpa kacamata** agar ekspresi mata melotot, alis, dan kepanikan terbaca 100% tajam di layar HP.
  - **Ciri Visual Permanen:** Rambut hitam pendek bervolume (*textured crop*), kulit hangat Asia Tenggara bergaya *matte polymer clay*, kaus oblong **Merah Bata / Crimson (`#A62C2B`)** bertuliskan kapital tebal putih **`JADI APA`** + **garis aksen kuning** di dada, celana pendek rumahan gelap, dan **100% nyeker (*barefoot*)** di dalam kosan.
  - **Anchor Opening / Closing (Wajib Episode Non-Manusia):** Untuk episode dalam tubuh (mis. Sel Darah Putih) atau benda mati (mis. Kabel Charger), WAJIB membuka **2 detik pertama** (atau menutup di ending) dengan **`@MasDimas`** sebagai jangkar semesta sebelum/sesudah kamera masuk ke dunia mikro.
- **Format:** Faceless 3D Micro-POV Edutainment (Sudut Pandang Orang Pertama / Kedua: *"Bayangin kamu jadi..."*).
- **Premis Utama:** Memasukkan penonton langsung ke dalam tubuh, objek, hewan, atau situasi tertentu selama **35–42 detik** (naskah padat **80–95 kata**). Penonton tidak menonton ceramah, melainkan "menjadi" tokoh utama dalam diorama 3D mini-film yang lucu, tegang, sekaligus membuka wawasan.
- **Target Audiens:** Audiens Indonesia lintas usia (15–35 tahun) di YouTube Shorts, TikTok, dan Instagram Reels.
- **Posisi Unik (Pembeda dari Zack D. Films & Odd Tilt):**
  - Bukan anatomi klinis/ngilu ala Zack D. Films; bukan pula komedi sejarah penemuan ala Odd Tilt.
  - Fokus pada **pengalaman imersif Micro-POV bergaya Tactile Matte Clay / Vinyl Diorama**, observasi keseharian autentik Indonesia bersama **`@MasDimas`**, dan fakta sains/logika yang menyatu alami dengan cerita.

---

## 2. Gaya Bahasa & Standar Naskah (80–95 Kata | 35–42 Detik)
- **Target Panjang & Ritme VO:** **80–95 kata** untuk durasi ideal **35–42 detik** (ritme `gemini-3.8-flash-tts` suara **`Puck`**, `VO_SPEED = 1.08`).
- **Pemisahan Ketat `speech_metadata` vs `vo_text`:**
  - `vo_text` WAJIB berisi **murni ucapan lisan** — dilarang menyelipkan arahan akting/nada ke dalam `vo_text`. Semua arahan gaya bicara, tempo, dan emosi WAJIB dipisahkan ke `speech_metadata`.
  - **Wajib Eja Angka Lisan:** Semua angka di `vo_text` WAJIB dieja sebagai kata Indonesia alami (*"jam dua pagi"*, *"tiga ratus kilometer per jam"*, *"lima setengah sentimeter"* — BUKAN `02:00`, `300 km/jam`, atau `5,5 cm`).
- **Persona Narator:** Teman nongkrong yang cerdas, ekspresif, agak nyeleneh, dan jago mendramatisasi hal sepele. Wajib pakai kata **"kamu"** sejak detik pertama.
- **Aturan Anti-Kaku:**
  - ❌ DILARANG buka video dengan: *"Halo guys"*, *"Tahukah kamu"*, *"Pernahkah kalian berpikir"*, atau *"Secara ilmiah..."*.
  - ❌ DILARANG memakai bahasa terjemahan kaku (*"Anda kemudian mengalami..."*).
  - ✅ Kalimat pendek lisan (maksimal 10–14 kata/kalimat) + fakta sains sebagai **alasan kejadian di dalam cerita**.

---

## 3. Rumus Retensi, Mute Test & Ending
1. **Detik 0–3 (Hook Instan + Konflik + *Mute Test*):**
   - Wajib lolos ***Mute Test*** (`silent_readability`): bahkan tanpa suara, penonton langsung paham siapa subjek POV dan bahayanya dalam 0,5–1 detik pertama.
2. **Detik 4–14 (Eskalasi Pertama + Fakta Tersembunyi):** Munculkan ancaman nyata & fakta unik sebagai pemicu aksi.
3. **Detik 15–22 (*Mid-Video Re-Hook*):** Wajib ada lonjakan ketegangan/twist baru di pertengahan video agar kurva retensi tidak turun.
4. **Detik 23–38 (Klimaks & Payoff):** Puncak aksi absurd/relatable dengan ekspresi maksimal `@MasDimas`.
5. **Ending Tajam (`ending_type`):** Wajib pilih **`hard_cut_punchline`** atau **`seamless_loop`**. **Tanpa Top Badge Kuning:** DILARANG menambahkan *top badge* kuning di atas layar agar tidak pernah terjadi teks ganda dengan subtitle karaoke bawah maupun spoiler punchline.

---

## 4. Alur Produksi Baku — Arsitektur Mobile-First v4.0 (Zero Blender, Zero Colab)
Seluruh produksi episode (`EP001–EP100+`) mengikuti **5 Tahap Baku Audio-First & Mobile-First v4.0**:

1. **Tahap 1 — Naskah di Gemini (80–95 Kata | 35–42 Detik):**
   - Susun naskah padat melalui 4-Pass Writer's Room (Premis/Hook/Anchor → Ritme Lisan & Ejaan Angka + *Mute Test* → Audit Logika Ruang & Lokalitas Indonesia → Kompilasi `<ep_id>_vo_spec.json` berisi segmen `vo_text` murni + `speech_metadata` terpisah).
2. **Tahap 2 — Generate VO Utuh Audio-First di Antigravity Remote (`03_pipeline/generate_vo_v4.py`):**
   - Panggil **`gemini-3.8-flash-tts`** (`Puck`, pisahkan arahan gaya bicara ke `speech_metadata`, `vo_text` murni ucapan lisan & angka dieja).
   - Jalankan `faster-whisper` (`condition_on_previous_text=False`, anti-ekor nol-durasi) untuk menyusun **`vo_timing_manifest.json`** (durasi aktual tiap segmen + rekomendasi panjang klip Flow bulat ke atas **3–10 detik**) dan **`subtitles.ass`** (karaoke bawah, **TANPA top badge kuning**).
   - Simpan otomatis **`vo_master.wav`**, **`vo_timing_manifest.json`**, dan **`subtitles.ass`** ke Google Drive `04_episodes/epXXX/`.
3. **Tahap 3 — Paket Prompt Google Flow di Gemini:**
   - Gemini membaca `vo_timing_manifest.json` dari Drive, lalu mengeluarkan paket prompt **Tactile Matte Clay / Vinyl Diorama 3D** (keyframe stills Nano Banana + klip video Omni Flash 1.2) yang presisi sesuai durasi tiap segmen VO.
4. **Tahap 4 — Produksi Visual dari HP di Google Flow (`flow.google.com`):**
   - Kunci karakter **`@MasDimas`** & seluruh keyframe stills di **Nano Banana (0 kredit)** — buat End Frame dengan mengedit Start Frame agar kontinuitas ruang/properti 100% konsisten.
   - Generate klip video **Omni Flash 1.2** (`9:16`, **WAJIB 3–10 detik/klip**, upscale **`1080p` 0 kredit**, audio **foley only** tanpa musik/dialog/teks).
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
