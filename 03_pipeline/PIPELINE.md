# PIPELINE SOP — CHANNEL MICRO-POV CLOUD PRODUCTION ENGINE (ZACK-BLENDER-PACK)

Dokumen ini adalah panduan arsitektur baku untuk memproduksi episode **3D Micro-POV Indonesia** (`epXXX_spec.json` → `final_epXXX.mp4`) **100% di cloud (Google Colab T4 / Kaggle GPU T4 x2 + Google Drive cache)** tanpa ketergantungan laptop lokal (RAM 4GB) dan tanpa langkah manual.

---

## 1. Prinsip Utama — Zero-Manual & Satu Pintu
- **100% Cloud:** Semua fetch aset, TTS, render Blender 5.2.2 headless, `post.py`, subtitle `.ass`, dan mixing FFmpeg jalan di Colab atau Kaggle.
- **Repo GitHub Ringan:** File media berat (`.blend`, `.mp4`, `.wav`, `.mp3`, `.hdr`, frame render > 25 MB) diabaikan oleh `.gitignore` dan disimpan di Google Drive (`/content/drive/MyDrive/channel-micro-pov/`).
- **Skill Pack Terintegrasi:** Referensi resmi `skills/zack-3d-short/`, `skills/blender-walk-example/`, dan `skills/blender-render-farm/` tersimpan langsung di repo untuk dokumentasi, helper posing (`doc_pose.py`), kamera look (`post.py`), dan switch engine (`eevee_switch.py`).

---

## 2. Spesifikasi Output Wajib
- **Resolusi:** `1080×1920` (Vertikal 9:16; preview `540×960`, storyboard `360×640`)
- **Frame Rate:** `24 fps` (default cepat & sinematik, hemat 20% frame vs 30 fps)
- **Codec Video:** H.264 (`libx264`), pixel format `yuv420p`, `+faststart`
- **Color Management & Camera Look:** **AgX** (`AgX - Medium High Contrast`, exposure `-0.45`) + Macro DOF (`f/2.8–4.0`) + pass `skills/blender-render-farm/scripts/post.py` (soft lens 35%, highlight glow, vignette 28%, luma film grain)
- **Audio:** AAC 192 kbps, 48 kHz stereo, normalisasi loudness `-14 LUFS` (VO `-6 dB`, SFX `-10 dB` dengan override presisi, BGM `-22 dB` dengan `sidechaincompress` auto-ducking)
- **Subtitle `.ass`:** `PlayResX: 1080`, `PlayResY: 1920`, `WrapStyle: 2`, Bold `56pt`, `Outline=5`, `Shadow=2`, `MarginL=95`, `MarginR=95`, `MarginV=380`, maksimal **2–3 kata (~16–18 karakter)** per baris.

---

## 3. Arsitektur 5 Tahap (Audio-First + MPFB2)

### Tahap 1 — Auto-Fetch Aset CC0 & Sync Rig MPFB2 (`fetch_assets.py`)
1. Menemukan `family_ready.blend` otomatis dari Google Drive (`/content/drive/MyDrive/Skill referensi/Zack Blender Pack/Zack-Blender-Pack/zack-3d-short/ready/family_ready.blend` atau `05_skills_ref/...`) atau `/kaggle/input/**`, lalu menyalinnya ke cache proyek `02_assets/models_3d/family_ready.blend`.
2. Mengunduh & men-cache **15 properti dapur nyata Poly Haven CC0** (`modern_wooden_cabinet`, `Shelf_01`, `cardboard_box_01`, `wooden_bowl_01/02`, `pot_enamel_01`, `brass_pan_01`, `metal_jug`, `jug_01`, `tea_set_01`, `electric_stove`, `wooden_cutting_board`, `WoodenChair_01`, `wicker_basket_02`, `wall_clock`), **3 tekstur PBR** (`interior_tiles`, `painted_plaster_wall`, `kitchen_wood`), dan **HDRI ruangan** (`small_empty_room_3`).

### Tahap 2 — Audio-First Voiceover & Pacing (`generate_tts.py`)
- Menggunakan **Gemini 3.8 Flash TTS** (`gemini-3.8-flash-tts`, fallback `gemini-3.8-flash-lite-tts`, voice `Puck`) dengan pemisahan ketat `vo_text` vs `speech_metadata.style`.
- Mendukung `--skip-existing` (menggunakan ulang cache VO di Drive tanpa memanggil API atau membutuhkan `GEMINI_API_KEY` jika seluruh WAV sudah tersedia).
- Default pacing ketat: `--fps 24`, `--pad-sec 0.06`, `--vo-speed 1.08` (memadatkan `EP001` dari 53 detik ke ~47–48 detik).
- Sinkronisasi presisi:
  - Scene 6: `vo_delay_sec = 0.15` agar `record_scratch` (`0.0s`, `0.25s`, `-14 dB`) tidak menimpa kata *"kaki"*.
  - Scene 8: `scream_offset_sec = audio_duration_sec + 0.05` (setelah *"Maaf ya, bang"* selesai), diikuti `cut_to_black_sec = scream_offset_sec + 0.35`.

### Tahap 3 — SFX & BGM CC0 (`prepare_audio.py`)
- Mengunduh SFX CC0/Public Domain terverifikasi (Wikimedia Commons) + synthesizer procedural Python (`numpy`/`scipy`) untuk 100% zero-failure.
- `wings_buzz_loud` dihaluskan dengan low-pass `1.8 kHz` dan level `-16 dB` agar tidak menutupi narasi VO.

### Tahap 4 — Blender 5.2.2 Scene Assembly, MPFB2 Acting & Render (`build_and_render.py` + `mpfb_human.py`)
- **Karakter Manusia Asli MPFB2 (`mpfb_human.py`):**
  - Membuka `family_ready.blend` (100% tekstur ter-pack), membuang studio & karakter non-perlu, merestyle pakaian kosan gelap (*kaus oblong* + celana gelap, `Displace 0.006`), `ENHANCED_SSS` matte skin, dan `fix_teeth.py` (gigi/gusi natural).
  - **Aturan Anti-Bug Wajib (`TROUBLESHOOTING.md`):**
    - JANGAN pernah me-reset shape key `$md-*` (hanya animasikan `!ex-*`).
    - Selalu pose lengan/tangan/kaki memakai `doc_pose.py` + world-space `reach()` + Leg IK terkalibrasi (tidak pernah A-pose kaku).
    - Ekspresi ARKit (`glare`/`angry`/`shock`/`panic`) menggunakan `BOOST = 1.6` + rotasi tulang `jaw` (`17° × jaw`).
    - **Sandal Anti-Melayang:** Setiap frame di Scene 1–7, `sandal_jepit_swallow` dihitung langsung dari frame telapak `wrist.R` (`wrist.head + palm_dir * 0.055 * scale + palm_normal * 0.045 * scale`) dan baru dilepas jatuh dengan gravitasi di Scene 8.
- **Set Dapur Padat & Lighting "Jam 2 Pagi":**
  - Albedo tembok/keramik/kulkas dibatasi `<= 0.56–0.62`, ambient biru malam `0.05–0.09`, flash neon di detik 1.05, backlight kuat dari belakang-atas karakter agar muka jatuh dalam bayangan kontras dramatis.
  - Sayap kecoak cokelat-amber transparan (`Alpha ~0.35`, berurat halus) di-parent langsung di sudut kiri-kanan bawah lensa kamera POV.
- **Engine Fleksibel & Auto-Resume:**
  - `--engine CYCLES`: otomatis pakai seluruh GPU NVIDIA (`OPTIX → CUDA` pada Colab T4 / Kaggle 2×T4) + Adaptive Sampling + `OPENIMAGEDENOISE` (anti-crash T4) + fallback CPU aman.
  - `--engine EEVEE`: mengadopsi `skills/blender-render-farm/scripts/eevee_switch.py` untuk render cepat 2–6 detik/frame.
  - Auto-resume melewati otomatis `frame_XXXX.png` berukuran `> 10 KB`.
  - Automated QC (`run_qc_checks`) memverifikasi `MISSING=[]`, zero unparented `Human.*`, `$md-*` intact, jarak grip sandal `< 0.25m`, dan camera raycast bersih sebelum render.

### Tahap 5 — Subtitle `.ass` & Final Mixing (`compose_final.py`)
- Menggabungkan `scene_01.mp4 .. scene_0N.mp4`, membuat subtitle `.ass` 9:16 anti-terpotong, mencampur VO + SFX + BGM auto-ducking `-14 LUFS`, lalu mengekspor `animatic_epXXX.mp4` / `preview_epXXX.mp4` / `final_epXXX.mp4`.

---

## 4. Notebook 1-Click Cloud
1. **Google Colab (T4 GPU + Drive):** `03_pipeline/render_episode_colab.ipynb` — cocok untuk storyboard QC, preview, revisi parsial (`SINGLE_SCENE = N`), maupun final render yang langsung tersimpan ke Google Drive.
2. **Kaggle GPU T4 x2 (Unattended Commit):** `03_pipeline/render_episode_kaggle.ipynb` — cocok untuk render final penuh (`Save Version → Save & Run All (Commit)`) yang bisa ditinggal tutup browser sampai `final_ep001.mp4` selesai di tab Output.

## 5. Aturan Revisi Parsial
Untuk merevisi satu adegan saja (misalnya adegan 4):
- Set `SINGLE_SCENE = 4` di notebook (atau `--scene 4` di CLI) untuk merender ulang hanya frame `scene_04`, lalu jalankan `compose_final.py` untuk merakit ulang `.mp4` final dalam hitungan detik.
