# PIPELINE SOP — JADI APA 3D MICRO-POV STUDIO ENGINE (v3.0)

Dokumen ini adalah SOP produksi modular **100% Cloud** untuk channel **Jadi Apa** (**@jadiapa3d**) dengan karakter maskot permanen **Mas Dimas** (`EP001–EP100+`). Lihat kitab teknis lengkap di [`MICRO_POV_STUDIO_SKILL.md`](MICRO_POV_STUDIO_SKILL.md).

---

## 1. Arsitektur Modular 3 Lapisan & Unified Look-Dev
1. **Universal Studio Core (`03_pipeline/core/`):**
   - `camera_presets.py` (5 arketipe kamera POV: `insect_ground`, `aerial_erratic`, `fluid_float`, `static_object_pov`, `human_first_person` + beat modifiers + motion blur `shutter=0.40` untuk render `final`)
   - `mpfb_helpers.py` & `paint_mas_dimas_tex.py` (Master permanen **Mas Dimas v3.0 — Unified Stylized Semi-Matte**: kaus Crimson `#A62C2B` bertuliskan **`JADI APA`** + garis aksen kuning, **tanpa kacamata**, rambut hitam bervolume, kulit hangat Asia Tenggara & pakaian **`roughness 0.55–0.65`** *soft-matte* bersih tanpa pori-pori tajam, celana pendek gelap, **100% nyeker** di kosan, Leg IK, `reach()`, `snap_sandal_to_right_hand()`)
   - `fast_anim.py` (`FastKeyframeRecorder` menulis `Action`/`FCurve` langsung via `foreach_set("co", ...)` + `FastArmatureFK` bebas depsgraph → baking 1.153+ frame **< 3 detik**, turun dari 610 detik!)
   - `lighting_utils.py` (AgX Medium High Contrast, **`EEVEE` *(Default tercepat)*:** `BLENDER_EEVEE_NEXT`/`BLENDER_EEVEE`, `16 TAA samples`, raytracing/SSS berat OFF; **`CYCLES_GPU` *(Strict GPU)*:** `get_devices()` + `OPTIX`/`CUDA`, `10 samples`, `adaptive=0.05`, `max_bounces=4`/`vol=0`, abort keras jika 0 GPU — **0 silent CPU fallback!**)
   - `post.py` (hanya dipakai untuk still `storyboard`; untuk video `final`/`preview`, efek *color grade + vignette + grain* dijalankan di **FFmpeg** `compose_final.py` dalam ~5 detik, bukan 1.161× CPU Python!)
   - `audio_utils.py` (`faster-whisper` word-level subtitle timestamps tersinkron `1 / VO_SPEED` + anti-hallucination filter + PyAV-free WAV decoder, micro-fade `15 ms`, dynamic `room_tone -32 dB`)
2. **Generic Runners (`03_pipeline/scripts/`):**
   - `build_and_render.py` memuat secara dinamis `04_episodes/<ep>/scene_builder.py` (produksi EP002+ mustahil merusak EP001!), mendukung `--frames-dir /tmp/render_frames/<ep>` agar **0 PNG ditulis ke Google Drive**, dan mencetak `[ENGINE] Active: ... | GPU Devices: ...`.
   - `build_storyboard_sheet.py` merakit **Adaptive Multi-Keyframe Fast Storyboard** (`storyboard_sheet_1.png`, `storyboard_sheet_2.png`, dst., maks. 8–9 panel/sheet + simulasi kotak subtitle ending).
   - `generate_tts.py`, `prepare_audio.py`, `compose_final.py` (dengan FFmpeg Post-Look + `--cleanup-frames`), `fetch_assets.py`.
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

## 3. Adaptive Multi-Keyframe Fast Storyboard Gate & Fast Local Final Render
Mulai `EP001` dan seluruh episode selanjutnya (`EP002–EP100+`), pengecekan gerak & komposisi sebelum render `final` **TIDAK lagi merender video `motion_check`**, melainkan memakai **Adaptive Multi-Keyframe Fast Storyboard**:

1. **HARD GATE — ADAPTIVE MULTI-KEYFRAME FAST STORYBOARD (`--mode storyboard`):**
   - Resolusi **`270×480`** per panel, **`4 samples + OIDN`**, `use_persistent_data=True`, *motion blur* OFF → selesai dalam **~1–2 menit**.
   - **Jumlah panel & sheet adaptif (tidak dibatasi kaku 1 atau 2 sheet):** Render sebanyak yang diperlukan, dikelompokkan rapi maksimal **8–9 panel per sheet** (`storyboard_sheet_1.png`, `storyboard_sheet_2.png`, dst.) sehingga **setiap transisi gerakan penting** (masuk pintu, tekan saklar, tangan meraih properti dari titik statis, *bullet-time*, langkah kaki, awal/tengah/akhir *whip-pan*, ekspresi wajah, hingga **overlay simulasi kotak subtitle ending**) terlihat jelas.
   - Agen WAJIB melakukan **Self-QC Vision** pada seluruh panel sebelum menampilkan ke user.
   - **ATURAN KERAS:** **DILARANG** menyiapkan bundle atau menjalankan render Colab/Kaggle sebelum user membalas secara eksplisit: **`ACC STORYBOARD`**.
2. **FAST LOCAL FINAL PRODUCTION RENDER (`--mode final` — Hanya Setelah `ACC STORYBOARD`):**
   - **Direct FCurve Baking `< 3 Detik`:** Semua keyframe 1.153+ frame ditulis sekaligus via `FastKeyframeRecorder` (`foreach_set("co", ...)`) + `FastArmatureFK` (zero depsgraph update per frame).
   - **Aturan Keras Disk Lokal (`/tmp/render_frames/`):** Seluruh PNG mentah & video scene sementara WAJIB dirender di disk lokal cepat **`--frames-dir /tmp/render_frames/<ep>`** — **DILARANG menulis PNG ke Google Drive!** Setelah `compose_final.py` menyalin **HANYA 1 file `final_epXXX.mp4`** (~15–25 MB) ke Google Drive `04_episodes/epXXX_.../`, flag `--cleanup-frames` **otomatis menghapus** seluruh PNG di `/tmp/render_frames/`.
   - **Opsi Default — `EEVEE` *(Tercepat, < 5 menit di Colab T4)*:** Otomatis `BLENDER_EEVEE_NEXT` (4.2–4.5) / `BLENDER_EEVEE` (5.0+ & <=4.1), `taa_render_samples = 16`, raytracing/SSS berat OFF, **tidak pernah jatuh diam-diam ke Cycles CPU**.
   - **Opsi Raytraced — `CYCLES_GPU` *(~15–20 menit di Colab T4)*:** `get_devices()` + `OPTIX` (fallback `CUDA`), seluruh GPU ON & CPU OFF, `samples = 10`, `adaptive_threshold = 0.05`, `max_bounces = 4` (`diffuse=2, glossy=2, transmission=2, volume=0`), `use_persistent_data = True`. **Jika 0 GPU terdeteksi -> abort keras (`--python-exit-code 1`)!**
   - **FFmpeg Post-Look (Bukan CPU `post.py` Per-Frame):** Pada mode video (`final`/`preview`), `post.py` CPU dilewati otomatis; efek *color grade (`eq`), vignette, dan film grain (`noise`)* dijalankan langsung oleh **FFmpeg** tepat sebelum burn-in subtitle `.ass` (~5 detik untuk seluruh video, subtitle tetap tajam!).

---

## 4. Hukum "Anti-Senam Tulang"
- **DILARANG** membuat koreografi tubuh rumit melepas alas kaki atau pakaian dari rig tubuh yang sedang bergerak.
- Untuk pengambilan properti (sandal, HP, alat dapur), selalu gunakan **titik ambil statis** (rak sandal, meja, nakas) atau pose *upper-body* + ekspresi wajah ARKit (`BOOST 1.6`).

---

## 5. Spesifikasi Output, Audio-First & Cloud Notebooks
- **Resolusi:** `1080×1920` (9:16 final), `540×960` (preview opsional), `270×480` (Adaptive Multi-Keyframe Fast Storyboard).
- **Audio:** Gemini 3.8 Flash TTS (`Puck`, `SKIP_EXISTING_VO=True`, `VO_SPEED=1.08`), micro-fade `15 ms` per clip WAV, `room_tone` dinamis `-32 dB`, SFX `-10 dB` (dengan kontrol gain per-SFX seperti `skitter_fast` `-7 dB` di bawah VO), BGM `-22 dB` auto-ducking, master `-14 LUFS` (AAC 192 kbps, 48 kHz stereo).
- **Subtitle `.ass`:** `PlayResX: 1080`, `PlayResY: 1920`, `MarginL/R: 95`, `MarginV: 380`, Bold `56pt`, `Outline=5`, 2–3 kata per chunk berbasis `faster-whisper` word-level timestamps (`1 / VO_SPEED`, anti-hallucination tail filter, dan anti-spoiler badge pada punchline ending).
- **Notebook Cloud 1-Click (Baking <3s + Fast Local Render + Strict GPU/EEVEE + `error_report.txt`):**
  - Google Colab *(Utama — Default `EEVEE`, pilihan `CYCLES_GPU`)*: `03_pipeline/render_episode_colab.ipynb`
  - Kaggle GPU T4 x2 *(Cadangan 1-File Bundle)*: `03_pipeline/render_episode_kaggle.ipynb`
