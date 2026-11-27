# PIPELINE SOP — JADI APA 3D MICRO-POV STUDIO ENGINE (v3.0)

Dokumen ini adalah SOP produksi modular **100% Cloud** untuk channel **Jadi Apa** (**@jadiapa3d**) dengan karakter maskot permanen **Mas Dimas** (`EP001–EP100+`). Lihat kitab teknis lengkap di [`MICRO_POV_STUDIO_SKILL.md`](MICRO_POV_STUDIO_SKILL.md).

---

## 1. Arsitektur Modular 3 Lapisan & Unified Look-Dev
1. **Universal Studio Core (`03_pipeline/core/`):**
   - `camera_presets.py` (5 arketipe kamera POV: `insect_ground`, `aerial_erratic`, `fluid_float`, `static_object_pov`, `human_first_person` + beat modifiers + motion blur `shutter=0.40` untuk render `final`)
   - `mpfb_helpers.py` & `paint_mas_dimas_tex.py` (Master permanen **Mas Dimas v3.0 — Unified Stylized Semi-Matte**: kaus Crimson `#A62C2B` bertuliskan **`JADI APA`** + garis aksen kuning, **tanpa kacamata**, rambut hitam bervolume, kulit hangat Asia Tenggara & pakaian **`roughness 0.55–0.65`** *soft-matte* bersih tanpa pori-pori tajam, celana pendek gelap, **100% nyeker** di kosan, Leg IK, `reach()`, `snap_sandal_to_right_hand()`)
   - `fast_anim.py` (`FastKeyframeRecorder` menulis `Action`/`FCurve` langsung via `foreach_set("co", ...)` + `FastArmatureFK` bebas depsgraph → baking 1.161 frame **`~2,3 detik`**, turun dari 610 detik!)
   - `lighting_utils.py` (AgX Medium High Contrast + **Colab T4 Cycles CUDA ONLY**: `compute_device_type='CUDA'`, CPU `False`, `OPENIMAGEDENOISE` GPU `FAST`, `12` adaptive samples `0.05`/min `4`, `4` bounces/`vol=0`/`caustics=OFF`, `1024px` texture limit, `PNG compression=0` — nol EEVEE `llvmpipe`, nol OptiX black-frame!)
   - `post.py` (hanya dipakai untuk still `storyboard`; untuk video `final`/`preview`, efek *color grade + vignette + grain* dijalankan di **FFmpeg** `compose_final.py` dalam ~5 detik, bukan 1.161× CPU Python!)
   - `audio_utils.py` (`faster-whisper` word-level subtitle timestamps tersinkron `1 / VO_SPEED` + anti-hallucination filter + PyAV-free WAV decoder, micro-fade `15 ms`, dynamic `room_tone -32 dB`)
2. **Generic Runners (`03_pipeline/scripts/`):**
   - `build_and_render.py` memuat secara dinamis `04_episodes/<ep>/scene_builder.py`, mendukung `--frames-dir /tmp/render_frames/<ep>` agar **0 PNG ditulis ke Google Drive**, menerima passthrough `--cycles-device CUDA`, dan menjalankan **Pre-Flight Guard Frame 1** (fail-fast jika hitam `< 3.0` atau 0 CUDA GPU).
   - `build_storyboard_sheet.py` merakit **Adaptive Multi-Keyframe Fast Storyboard** (`storyboard_sheet_1.png`, `storyboard_sheet_2.png`, dst., maks. 8–9 panel/sheet + simulasi kotak subtitle ending).
   - `generate_tts.py`, `prepare_audio.py`, `compose_final.py` (FFmpeg Post-Look + subtitle karaoke bawah saja tanpa *top badge* ganda + `--cleanup-frames`), `fetch_assets.py`.
3. **Isolated Episode Builder (`04_episodes/epXXX_<slug>/`):**
   - `epXXX_spec.json` + `scene_builder.py` khusus staging & koreografi episode tersebut.

### Unified Look-Dev (*Stylized Semi-Matte*) & Jangkar Semesta
- **1 Bahasa Visual Tunggal:** Seluruh episode (manusia maupun non-manusia seperti Sel Darah Putih EP002 atau Kabel Charger EP003) WAJIB menggunakan permukaan *stylized semi-matte* (`roughness 0.55–0.65`) bertekstur halus (bukan bola polos mentah) dengan grading **`AgX Medium High Contrast` + `Macro DOF` + FFmpeg Post-Look** (`post.py` khusus still storyboard).
- **Anchor Opening / Closing:** Episode dalam tubuh atau benda mati WAJIB dibuka 2 detik pertama (atau ditutup di ending) dengan **Mas Dimas** sebagai jangkar semesta sebelum/sesudah kamera masuk ke dunia mikro.

---

## 2. Hybrid Production Pipeline (`render_pipeline` di `spec_schema.json`)
Setiap episode atau scene memilih jalur produksi paling efisien melalui field `render_pipeline`:
- **`blender_3d` *(Default)*:** Adegan POV bergerak di ruang 3D nyata (`insect_ground`, `aerial_erratic`, `fluid_float`, `human_first_person`, *whip-pan* 180°, perubahan FOV, *floor clamp*).
- **`parallax_25d`:** Khusus adegan `static_object_pov` tenang yang tidak berpindah tempat (gambar statis digerakkan kode 2.5D agar hemat waktu/token).
- **`ai_i2v`:** Khusus episode **Semesta Sejarah / Alam Ekstrem** berskala masif (mis. Krakatau 1883, tsunami, kerumunan besar) via Google Flow / Veo.

---

## 3. Adaptive Multi-Keyframe Fast Storyboard Gate & Colab T4 Fast Local Final Render
Mulai `EP001` dan seluruh episode selanjutnya (`EP002–EP100+`), pengecekan gerak & komposisi sebelum render `final` **TIDAK lagi merender video `motion_check`**, melainkan memakai **Adaptive Multi-Keyframe Fast Storyboard**:

1. **HARD GATE — ADAPTIVE MULTI-KEYFRAME FAST STORYBOARD (`--mode storyboard`):**
   - Resolusi **`270×480`** per panel, **`4 samples + OIDN`**, `use_persistent_data=True`, *motion blur* OFF → selesai dalam **~1–2 menit**.
   - **Jumlah panel & sheet adaptif (tidak dibatasi kaku 1 atau 2 sheet):** Render sebanyak yang diperlukan, dikelompokkan rapi maksimal **8–9 panel per sheet** (`storyboard_sheet_1.png`, `storyboard_sheet_2.png`, dst.) sehingga **setiap transisi gerakan penting** terlihat jelas.
   - Agen WAJIB melakukan **Self-QC Vision** pada seluruh panel sebelum menampilkan ke user.
   - **ATURAN KERAS:** **DILARANG** menjalankan render Colab final sebelum user membalas secara eksplisit: **`ACC STORYBOARD`**.
2. **COLAB T4 FAST LOCAL FINAL RENDER (`--mode final` — Hanya Setelah `ACC STORYBOARD`):**
   - **Direct FCurve Baking `< 3 Detik`:** Semua keyframe 1.161 frame ditulis sekaligus via `FastKeyframeRecorder` (`foreach_set("co", ...)`) + `FastArmatureFK`.
   - **Pure Cycles `CUDA` + `OIDN GPU FAST` + Pre-Flight Guard Frame 1:** `LD_PRELOAD=""`, `-- --cycles-device CUDA`, `device.use = (device.type == 'CUDA')` (CPU `False`), `OPENIMAGEDENOISE` (`RGB_ALBEDO_NORMAL`, `FAST`, `denoising_use_gpu=True`), `12` adaptive samples (`0.05`/min `4`), `max_bounces=4` (`volume=0`, `caustics=OFF`, `sample_clamp_indirect=10.0`), `use_simplify=True`, `texture_limit_render='1024'`, `PNG compression=0`. Pre-Flight Frame 1 langsung gagal jika hitam (`< 3.0`) atau 0 CUDA GPU.
   - **Aturan Keras Disk Lokal (`/tmp/render_frames/`):** Seluruh PNG mentah & video scene sementara WAJIB dirender di `--frames-dir /tmp/render_frames/<ep>` — **0 PNG ke Google Drive!** Usai `compose_final.py` menyalin **HANYA 1 file `final_epXXX.mp4`** ke Drive, `--cleanup-frames` otomatis menghapus `/tmp/render_frames/`.
   - **FFmpeg Post-Look & Subtitle Bersih (Tanpa Top Badge Ganda):** Efek *color grade (`eq`), vignette, film grain (`noise`)* dijalankan FFmpeg sebelum burn-in `.ass`, dan seluruh *top badge* kuning dimatikan agar tidak bertabrakan dengan subtitle karaoke bawah.

---

## 4. Hukum "Anti-Senam Tulang"
- **DILARANG** membuat koreografi tubuh rumit melepas alas kaki atau pakaian dari rig tubuh yang sedang bergerak.
- Untuk pengambilan properti (sandal, HP, alat dapur), selalu gunakan **titik ambil statis** (rak sandal, meja, nakas) atau pose *upper-body* + ekspresi wajah ARKit (`BOOST 1.6`).

---

## 5. Spesifikasi Output, Audio-First & Cloud Notebooks
- **Resolusi:** `1080×1920` (9:16 final), `540×960` (preview opsional), `270×480` (Adaptive Multi-Keyframe Fast Storyboard).
- **Audio:** Gemini 3.8 Flash TTS (`Puck`, `SKIP_EXISTING_VO=True`, `VO_SPEED=1.08`), micro-fade `15 ms` per clip WAV, `room_tone` dinamis `-32 dB`, SFX `-10 dB` (`skitter_fast` `-7 dB` di bawah VO), BGM `-22 dB` auto-ducking, master `-14 LUFS` (AAC 192 kbps, 48 kHz stereo).
- **Subtitle `.ass`:** `PlayResX: 1080`, `PlayResY: 1920`, `MarginL/R: 95`, `MarginV: 380`, Bold `56pt`, `Outline=5`, 2–3 kata per chunk berbasis `faster-whisper` (`1 / VO_SPEED`, anti-hallucination tail filter, **tanpa *top badge* kuning ganda**).
- **Notebook Cloud 1-Klik (2 Sel + Cache Blender & Whisper di Drive `03_pipeline/cache/` + `error_report.txt`):**
  - Google Colab T4 *(Utama — 2 Sel 1-Klik `CYCLES_CUDA` + `OIDN GPU`)*: `03_pipeline/render_episode_colab.ipynb`
  - Kaggle GPU T4 x2 *(Cadangan 1-File Bundle)*: `03_pipeline/render_episode_kaggle.ipynb`
