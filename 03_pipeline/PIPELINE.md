# PIPELINE SOP — ANTIGRAVITY PRODUCTION ENGINE (WINDOWS)

Dokumen ini adalah panduan eksekusi baku untuk AI Coding Agent di **Antigravity Desktop App (Windows)**.

## 1. Tujuan
Mengubah 1 file kontrak **`epXXX_spec.json`** menjadi video vertikal siap *upload* **`final_epXXX.mp4`** secara modular dan dapat direvisi per adegan.

## 2. Spesifikasi Output Wajib
- **Resolusi:** `1080x1920` (Vertikal 9:16)
- **Frame Rate:** `30 fps` (atau `60 fps` untuk adegan aksi cepat jika render ringan)
- **Codec Video:** H.264 (`libx264`), pixel format `yuv420p` (kompatibel penuh YouTube Shorts, TikTok, Reels)
- **Audio:** AAC 192kbps, 48kHz, normalisasi loudness `-14 LUFS` (VO dominan di `-6 dB`, SFX di `-10 dB`, BGM di `-22 dB` dengan *ducking* saat VO bicara)

## 3. Urutan Kerja Agen (End-to-End)
Setiap kali diminta mengeksekusi episode baru (misal `04_episodes/ep001_kecoak_dapur/ep001_spec.json`):

1. **Validasi Spec & Aset**
   - Baca `epXXX_spec.json` dan cocokkan strukturnya dengan `03_pipeline/spec_schema.json`.
   - Cek `02_assets/asset_catalog.json`. Jika file `.glb` atau `.wav` belum tersedia di folder lokal, gunakan *procedural low-poly builder* (untuk 3D) atau hasilkan placeholder SFX sintetis sementara, lalu catat daftar aset yang perlu dilengkapi user di `missing_assets.txt`.

2. **Generate Audio Voiceover & Timing Presisi (Audio-First!)**
   - **PENTING:** Selalu buat audio *Voiceover* TERLEBIH DAHULU sebelum mengunci durasi animasi 3D!
   - Generate file audio per adegan (`scene_01.wav`, `scene_02.wav`, ...) menggunakan skrip TTS lokal/API (misal Edge-TTS / ElevenLabs / rekaman manual user jika sudah ditaruh di `raw_render/vo/`).
   - Hitung durasi aktual setiap file audio VO (dalam detik), lalu gunakan durasi aktual itu untuk mengunci panjang *frame* tiap adegan 3D agar visual dan suara 100% sinkron.

3. **Build & Render 3D Scene**
   - **Opsi A — Blender Headless (Direkomendasikan untuk POV objek/ruangan):**
     - Jalankan skrip Python `build_scene.py` lewat `blender --background --python build_scene.py` dengan render engine **EEVEE Next**.
     - Terapkan *camera rig* POV sesuai `pov_height_m`, `fov_deg`, dan `camera_motion` di `spec.json`.
     - Render preview cepat dulu (`540x960`, 16 samples) untuk dicek user; setelah di-ACC, render final (`1080x1920`, 32–64 samples).
   - **Opsi B — Three.js + Playwright/Headless Capture (Alternatif super cepat):**
     - Generate scene Three.js deterministik (berbasis frame step, bukan real-time clock) dan capture PNG sequence via headless browser.

4. **Subtitle Dinamis (.ass / .srt)**
   - Generate subtitle otomatis dari teks VO dan timestamp aktual tiap adegan (maksimal 2–4 kata per baris, posisi tengah-bawah aman di margin `y = 25%` dari bawah, font bold sans-serif dengan outline hitam tebal).

5. **Compositing & Audio Mixing (FFmpeg)**
   - Gabungkan video render + track VO + track SFX tepat di timestamp `sfx_cue` + track BGM + burn-in subtitle menjadi `final_epXXX.mp4`.

## 4. Aturan Revisi Parsial
Jika user meminta revisi pada satu adegan saja (contoh: *"Revisi scene 4, sandalnya kurang cepat jatuh"*), agen WAJIB:
- Hanya merender ulang rentang frame `scene_04`, bukan seluruh video dari detik 0 (hemat waktu render).
- Merakit ulang file `.mp4` final lewat FFmpeg.
