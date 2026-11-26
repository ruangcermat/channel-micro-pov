# PIPELINE SOP — JADI APA 3D MICRO-POV STUDIO ENGINE (v2.0)

Dokumen ini adalah SOP produksi modular **100% Cloud** untuk channel **Jadi Apa** (**Jadi Apa 3D**) dengan karakter maskot permanen **Mas Dimas** (`EP001–EP100+`). Lihat kitab teknis lengkap di [`MICRO_POV_STUDIO_SKILL.md`](MICRO_POV_STUDIO_SKILL.md).

---

## 1. Arsitektur Modular 3 Lapisan
1. **Universal Studio Core (`03_pipeline/core/`):**
   - `camera_presets.py` (5 arketipe kamera POV: `insect_ground`, `aerial_erratic`, `fluid_float`, `static_object_pov`, `human_first_person` + beat modifiers + motion blur `shutter=0.40`)
   - `mpfb_helpers.py` & `paint_mas_dimas_tex.py` (Master permanen **Mas Dimas v2.0**: kaus Crimson `#A62C2B` bertuliskan **`JADI APA`** + garis aksen kuning, **tanpa kacamata**, rambut bervolume, kulit hangat Asia Tenggara, celana pendek gelap, nyeker, Leg IK, `reach()`, `snap_sandal_to_foot()`, `snap_sandal_to_right_hand()`)
   - `lighting_utils.py` (AgX Medium High Contrast, Cycles multi-GPU + OIDN, EEVEE auto-fallback, 2-Gate presets)
   - `post.py` (`skills/blender-render-farm/scripts/post.py` soft lens + glow + vignette + film grain)
   - `audio_utils.py` (`faster-whisper` word-level subtitle timestamps tersinkron `1 / VO_SPEED`, PyAV-free WAV decoder, micro-fade `15 ms`, dynamic `room_tone -32 dB`)
2. **Generic Runners (`03_pipeline/scripts/`):**
   - `build_and_render.py` memuat secara dinamis `04_episodes/<ep>/scene_builder.py` (produksi EP002+ mustahil merusak EP001!), mendukung `--frame-step` & `--max-frames` untuk uji cepat/smoke-test.
   - `generate_tts.py`, `prepare_audio.py`, `compose_final.py`, `build_storyboard_sheet.py`, `fetch_assets.py`.
3. **Isolated Episode Builder (`04_episodes/epXXX_<slug>/`):**
   - `epXXX_spec.json` + `scene_builder.py` khusus staging & koreografi episode tersebut.

---

## 2. 2 HARD GATE PRODUKSI (WAJIB DIPATUHI)

### HARD GATE 1 — STORYBOARD (`--mode storyboard`)
- Render hero frames (`270×480` fast draft, 4 samples Cycles + OIDN + `post.py`, selesai < 60 detik) dan tampilkan **`storyboard_sheet.png`** (9 panel lengkap dengan kartu *Scene & Waktu*, *Aksi & Kamera*, *VO*, dan *SFX / BGM*).
- **ATURAN KERAS:** **DILARANG** menyiapkan baking penuh 24fps atau menjalankan render Colab/Kaggle sebelum user membalas secara eksplisit: **`ACC STORYBOARD`**.

### HARD GATE 2 — MOTION CHECK (`--mode motion_check`)
- Hanya dijalankan **setelah** user memberi `ACC STORYBOARD`.
- Merender full 24fps resolusi ringan (`360×640`, 8 samples, `EEVEE` dengan auto-fallback `Cycles` 8-sample jika headless Linux tidak mendukung EGL) lalu menyusun `motion_check_epXXX.mp4` lengkap dengan VO (`15 ms` micro-fade), SFX, `room_tone -32 dB`, BGM auto-ducking, dan subtitle `faster-whisper`.
- Digunakan untuk verifikasi rasa gerak POV, timing komedi, dan safe-zone 9:16 sebelum masuk render **`final`** (`1080×1920`, 24fps, 24 samples di Kaggle GPU T4 x2 / Colab T4).

---

## 3. Spesifikasi Output & Audio-First
- **Resolusi:** `1080×1920` (9:16 final), `540×960` (preview), `360×640` (`motion_check`), `270×480` (fast draft `storyboard`).
- **Frame Rate:** `24 fps` + `use_motion_blur = True` (`shutter = 0.40`) pada mode video GPU & `preview`/`final`.
- **Audio:** Gemini 3.8 Flash TTS (`Puck`, `SKIP_EXISTING_VO=True`, `VO_SPEED=1.08`), micro-fade `15 ms` per clip WAV, `room_tone` dinamis `-32 dB`, SFX `-10 dB`, BGM `-22 dB` auto-ducking, master `-14 LUFS` (AAC 192 kbps, 48 kHz stereo).
- **Subtitle `.ass`:** `PlayResX: 1080`, `PlayResY: 1920`, `MarginL/R: 95`, `MarginV: 380`, Bold `56pt`, `Outline=5`, 2–3 kata per chunk berbasis `faster-whisper` word-level timestamps (`1 / VO_SPEED`).
- **Master Karakter Permanen:** `02_assets/models_3d/mas_dimas_ready.blend` (tersimpan di Google Drive & ikut dikemas di `epXXX_kaggle_bundle.zip`).

---

## 4. Notebook Cloud 1-Click + Auto Error Logger (`error_report.txt`)
1. **Google Colab (T4 GPU + Drive):** `03_pipeline/render_episode_colab.ipynb` — mendukung `storyboard`, `motion_check`, `preview`, `final`, revisi parsial `SINGLE_SCENE = N`, dan otomatis menulis **`error_report.txt`** ke Google Drive jika terjadi error.
2. **Kaggle GPU T4 x2 (Unattended Commit — 1-File Upload):** `03_pipeline/render_episode_kaggle.ipynb` — cukup upload 1 arsip **`epXXX_kaggle_bundle.zip`** (berisi `mas_dimas_ready.blend`, `timing_manifest.json`, `raw_render/vo/scene_*.wav` + `.words.json`), otomatis ekstrak, render 2×T4 + auto-resume (`>10 KB`) + `post.py` + `compose_final.py`, ekspor `final_epXXX.mp4` ke `/kaggle/working/`, dan otomatis simpan **`/kaggle/working/error_report.txt`** jika terjadi error runtime.
