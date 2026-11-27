# CHANNEL BIBLE — JADI APA (3D MICRO-POV INDONESIA, v3.0)

## 1. Identitas & Konsep Inti (RESMI DIKUNCI)
- **Nama Channel:** **Jadi Apa** (handle cadangan: **@jadiapa3d**)
- **Karakter Maskot Utama (Permanen):** **Mas Dimas** (`02_assets/models_3d/mas_dimas_ready.blend`)
  - Pria muda anak kosan Indonesia yang ekspresif, **tanpa kacamata** agar ekspresi mata melotot, alis, dan kepanikan terbaca 100% tajam di layar HP.
  - **Identitas Visual Kunci (*Unified Stylized Semi-Matte*):** Kaus oblong **Merah Bata / Crimson (`#A62C2B`)** bertuliskan kapital tebal putih **`JADI APA`** dengan **garis aksen kuning** di tengah dada, **rambut hitam pendek bervolume**, **kulit hangat Asia Tenggara** & pakaian dengan **`roughness 0.55–0.65`** (*soft-matte* bersih tanpa pori-pori tajam menyeramkan), celana pendek rumahan gelap, dan **100% nyeker (*barefoot*)** di dalam kosan.
  - **Jangkar Pembuka/Penutup (*Anchor Opening/Closing*):** Untuk episode non-manusia (dalam tubuh seperti Sel Darah Putih EP002, atau benda mati seperti Kabel Charger EP003), WAJIB membuka 2 detik pertama (atau menutup di ending) dengan **Mas Dimas** sebagai jangkar semesta sebelum/sesudah kamera masuk ke dunia mikro.
- **Format:** Faceless 3D Animated Edutainment — *Micro-POV* (Sudut Pandang Orang Pertama / Kedua: *"Bayangin kamu jadi..."*).
- **Premis Utama:** Memasukkan penonton langsung ke dalam tubuh, objek, hewan, atau situasi tertentu selama **35–42 detik** (target naskah padat **80–95 kata**). Penonton tidak menonton ceramah, melainkan "menjadi" tokoh utama di dalam mini-film yang lucu, tegang, sekaligus membuka wawasan.
- **Target Audiens:** Audiens Indonesia lintas usia (15–35 tahun) di YouTube Shorts, TikTok, dan Instagram Reels.
- **Posisi Unik (Pembeda dari Zack D. Films & Odd Tilt):**
  - Bukan anatomi klinis/ngilu ala Zack D. Films.
  - Bukan komedi sejarah penemuan benda ala Odd Tilt.
  - Fokus pada **pengalaman imersif 3D Micro-POV**, observasi keseharian autentik Indonesia bersama **Mas Dimas**, dan fakta sains/logika yang menyatu alami dengan cerita.

---

## 2. Gaya Bahasa & Standar Naskah (80–95 Kata | 35–42 Detik)
- **Target Panjang & Ritme VO:** **80–95 kata** untuk durasi ideal **35–42 detik** (ritme bicara Gemini 3.8 Flash TTS `Puck` ±2,2–2,4 kata/detik pada `VO_SPEED=1.08`).
- **Wajib Eja Angka Lisan:** Semua angka di `vo_text` WAJIB dieja sebagai kata Indonesia alami agar TTS tidak salah baca (*"jam dua pagi"*, *"tiga ratus kilometer per jam"*, *"lima setengah sentimeter"* — BUKAN `02:00`, `300 km/jam`, atau `5,5 cm`).
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
4. **Detik 23–38 (Klimaks & Payoff):** Puncak aksi absurd/relatable dengan ekspresi maksimal Mas Dimas.
5. **Ending Tajam (`ending_type`):** Wajib pilih **`hard_cut_punchline`** atau **`seamless_loop`**. **Anti-Spoiler Badge:** Jangan munculkan badge punchline di awal scene terakhir; tunda sampai detik punchline atau kosongkan.

---

## 4. Unified Look-Dev, Hybrid Pipeline, Golden Hero Zone & 4-Layer Audio
- **Unified Look-Dev (*Stylized Semi-Matte*):** 1 bahasa visual tunggal untuk seluruh channel — `roughness 0.55–0.65` bertekstur halus (manusia maupun objek non-manusia, BUKAN bola polos mentah) + **`AgX Medium High Contrast` + `Macro DOF` + `post.py`**.
- **Hybrid Production Pipeline (`render_pipeline`):**
  - `blender_3d` *(Default)*: Adegan POV bergerak di ruang 3D nyata (*whip-pan* 180°, perubahan FOV, *floor clamp*).
  - `parallax_25d`: Khusus adegan `static_object_pov` tenang tanpa perpindahan tempat.
  - `ai_i2v`: Khusus episode **Semesta Sejarah / Alam Ekstrem** berskala masif (Krakatau 1883, tsunami/kerumunan) via Google Flow / Veo.
- **5 Arketipe Kamera POV (`core/camera_presets.py`):** `insect_ground`, `aerial_erratic`, `fluid_float`, `static_object_pov`, `human_first_person` + *floor clamp* + *motion blur* (`shutter=0.40` saat final).
- **Golden Hero Zone 9:16 (`1080×1920`):** Wajah ekspresif & aksi utama WAJIB di **`x: 100–900px, y: 260–1250px`** (aman 100% dari bar atas, UI kanan, dan subtitle `MarginV=380`).
- **4-Layer Audio Mix (Master `-14 LUFS`):**
  1. **VO (`-6 dB`):** Gemini 3.8 Flash TTS (`Puck`, cached), *micro-fade* `15 ms`, subtitle karaoke **`faster-whisper`** (`1 / VO_SPEED`, filter anti-hallucination).
  2. **SFX (`-10 dB`):** Aksen fisik tajam sesuai beat animasi (`skitter_fast` diturunkan `-7 dB` di bawah VO).
  3. **BGM (`-22 dB`):** Auto-ducking otomatis saat VO aktif.
  4. **Room Tone (`-32 dB`):** Ambien kontinu (`night_fridge_hum`, dll.).

---

## 5. 4-Pass Writer's Room & Adaptive Multi-Keyframe Fast Storyboard Gate
Setiap episode baru (`EP002–EP100+`) WAJIB melewati **4-Pass Writer's Room**:
- **Pass 1:** Premis, Hook, 80–95 kata, *Mid-Video Re-Hook*, `ending_type`, `render_pipeline`, & `anchor_mascot` (jika non-manusia).
- **Pass 2:** Ritme lisan, ejaan angka, & `silent_readability` (*Mute Test*).
- **Pass 2.5 (Audit Logika Fisik & Hukum Anti-Senam Tulang):** Wajib isi `spatial_plan` & `prop_state_chain` dengan **titik ambil properti statis** (rak, meja, nakas — DILARANG melepas alas kaki/pakaian dari rig bergerak!).
- **Pass 3:** Kompilasi `epXXX_spec.json` & validasi ketat `03_pipeline/spec_schema.json`.

**Gate Produksi Tunggal Sebelum Render Final:**
1. **Adaptive Multi-Keyframe Fast Storyboard (`--mode storyboard`, `270×480`, 4 samples + OIDN, ~1–2 menit):**
   - Menggantikan video `motion_check`! Render **sebanyak keyframe yang diperlukan** (dikelompokkan rapi maks. 8–9 panel/sheet: `storyboard_sheet_1.png`, `storyboard_sheet_2.png`, dst.) mencakup seluruh transisi gerakan penting + **simulasi kotak subtitle ending**.
   - Agen WAJIB **Self-QC Vision** lalu **STOP TOTAL** menunggu balasan **`ACC STORYBOARD`** dari user.
2. **Final Render (`--mode final`, `1080×1920`, 24fps, `24 samples` + motion blur + `post.py`):** Hanya dijalankan setelah **`ACC STORYBOARD`**.
