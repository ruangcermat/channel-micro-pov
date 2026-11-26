# CHANNEL BIBLE — JADI APA (3D MICRO-POV INDONESIA, v2.0)

## 1. Identitas & Konsep Inti (RESMI DIKUNCI)
- **Nama Channel:** **Jadi Apa** (handle cadangan: **@jadiapa3d**)
- **Karakter Maskot Utama (Permanen):** **Mas Dimas** (`02_assets/models_3d/mas_dimas_ready.blend`)
  - Pria muda anak kosan Indonesia yang ekspresif, **tanpa kacamata** agar ekspresi mata melotot, alis, dan kepanikan terbaca 100% tajam di layar HP.
  - **Identitas Visual Kunci:** Kaus oblong **Merah Bata / Crimson (`#A62C2B`)** bertuliskan kapital tebal putih **`JADI APA`** dengan **garis aksen kuning** di tengah dada, **rambut hitam pendek bervolume** (siluet atas-depan tegas, bukan topi renang gepeng), **kulit hangat Asia Tenggara** (*warm natural tone*), celana pendek rumahan gelap, dan kaki **nyeker** / **sandal jepit Swallow hijau** sesuai kontinuitas adegan.
  - Muncul berulang lintas episode (Semesta Kosan, Dalam Tubuh, Jalanan) agar penonton langsung mengenali brand **Jadi Apa** dalam < 1 detik.
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
    - *Salah:* "Kecoak memiliki organ bernama cerci yang mendeteksi hembusan angin."
    - *Benar:* "Dua antena di pantatmu langsung nangkep angin dari ayunan tangannya."

---

## 3. Rumus Retensi, Mute Test & Ending
1. **Detik 0–3 (Hook Instan + Konflik + *Mute Test*):**
   - Wajib lolos ***Mute Test*** (`silent_readability`): bahkan tanpa suara, penonton langsung paham siapa subjek POV dan bahayanya dalam 0,5–1 detik pertama (contoh: bayangan siluet kecoak + kuah mi berkilau + pintu kamar terbuka).
2. **Detik 4–14 (Eskalasi Pertama + Fakta Tersembunyi):** Munculkan ancaman nyata & fakta unik sebagai pemicu aksi.
3. **Detik 15–22 (*Mid-Video Re-Hook*):** Wajib ada lonjakan ketegangan/twist baru di pertengahan video agar kurva retensi tidak turun (contoh: jalur kabur diblokir kaki bersandal / buntu total).
4. **Detik 23–38 (Klimaks & Payoff):** Puncak aksi absurd/relatable dengan ekspresi maksimal Mas Dimas.
5. **Ending Tajam (`ending_type`):** Wajib pilih salah satu — **`hard_cut_punchline`** (potong langsung ke hitam di puncak tawa/teriakan) atau **`seamless_loop`** (kalimat akhir nyambung mulus ke kalimat pembuka). Tanpa penutup basa-basi (*"Jangan lupa like & subscribe"*).

---

## 4. Standar Visual, Golden Hero Zone 9:16 & 4-Layer Audio Mix
- **Visual & Look-Dev:** Blender 5.2.2 LTS + **MPFB2 (Mas Dimas)** + properti nyata **Poly Haven CC0** + **AgX Medium High Contrast** + **Macro DOF** + camera finish **`post.py`**.
- **5 Arketipe Kamera POV (`core/camera_presets.py`):** `insect_ground`, `aerial_erratic`, `fluid_float`, `static_object_pov`, `human_first_person` + *floor clamp* + *motion blur* (`shutter=0.40`) + *secondary motion*.
- **Golden Hero Zone 9:16 (`1080×1920`):**
  - Seluruh wajah ekspresif, tangan menggenggam prop, dan subjek hero WAJIB berada di dalam **`x: 100–900px, y: 260–1250px`** (aman 100% dari bar atas, ikon kanan TikTok/Shorts/Reels, dan subtitle `MarginV=380`).
- **4-Layer Audio Mix (Master `-14 LUFS`):**
  1. **VO (`-6 dB`):** Gemini 3.8 Flash TTS (`Puck`), *micro-fade* `15 ms` tiap potongan scene, subtitle karaoke presisi milidetik via **`faster-whisper`** (`word_timestamps=True`).
  2. **SFX (`-10 dB`):** Aksen fisik tajam sesuai beat animasi (saklar, hentakan sandal, deru sayap, teriakan).
  3. **BGM (`-22 dB`):** Auto-ducking otomatis saat VO aktif.
  4. **Room Tone (`-32 dB`):** Lapisan ambien ruangan kontinu sesuai latar (contoh: `night_fridge_hum` untuk dapur kosan jam 2 pagi).

---

## 5. 4-Pass Writer's Room & 2 Hard Gate Produksi
Setiap episode baru (`EP002–EP100+`) WAJIB melewati **4-Pass Writer's Room** sebelum menulis kode 3D:
- **Pass 1 — Premis, Hook & Draf Naskah:** Kunci premis POV, jumlah kata **80–95 kata**, *Mid-Video Re-Hook* detik 15–22, dan `ending_type`.
- **Pass 2 — Ritme Lisan, Ejaan Angka & Mute Test:** Pastikan nol angka mentah di VO, kalimat lisan cepat, dan isi field `silent_readability`.
- **Pass 2.5 — Audit Logika Fisik (*Physical Logic Audit*):** Wajib isi **`spatial_plan`** (pintu masuk/keluar, jalur jalan karakter, lokasi saklar/jam statis) dan **`prop_state_chain`** (asal-usul & perpindahan setiap benda dari awal sampai akhir, termasuk tulang parent & kontak tanah).
- **Pass 3 — Kompilasi `epXXX_spec.json` & Validasi Schema:** Validasi ketat terhadap `03_pipeline/spec_schema.json`.

Dilanjutkan **2 Hard Gate Visual** sebelum render final:
1. **Hard Gate 1 — Fast Draft Storyboard (`--mode storyboard`, `270×480`, 4 samples < 1 menit):** Agen wajib Self-QC visual seluruh 9 panel lalu tampilkan `storyboard_sheet.png`. **STOP** hingga user membalas **`ACC STORYBOARD`**.
2. **Hard Gate 2 — Motion Check (`--mode motion_check`, `360×640`, 8 samples + VO/SFX/BGM/Room Tone/Subtitle):** Cek rasa gerak kamera, akting, dan Golden Hero Zone sebelum render **`final`** (`1080×1920`, 24fps, 24 samples).
