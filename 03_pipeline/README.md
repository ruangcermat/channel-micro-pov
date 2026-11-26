# 3D Micro-POV — Zero-Manual Cloud Production Pipeline (Blender 5.2.2 + MPFB2)

Arsitektur produksi *end-to-end* untuk mengubah `epXXX_spec.json` menjadi video vertikal 9:16 siap upload (`final_epXXX.mp4`) **100% di cloud (Google Colab T4 / Kaggle GPU T4 x2 + Google Drive cache)** mengadopsi standar look-dev **`Zack-Blender-Pack` (`skills/`)**.

## Struktur Pipeline (`03_pipeline/`)

| File | Fungsi |
|---|---|
| `render_episode_colab.ipynb` | **Notebook 1-Click Google Colab (T4 GPU + Drive):** auto-sync `family_ready.blend` dari Drive → clone/pull repo (opsional `GITHUB_TOKEN`) → install Blender **5.2.2 LTS** → pilih `RENDER_ENGINE` (`CYCLES`/`EEVEE`) & `RENDER_MODE` (`storyboard`/`preview`/`final`) → tampilkan `storyboard_grid.png` & player video. |
| `render_episode_kaggle.ipynb` | **Notebook Unattended Kaggle GPU T4 x2:** diadaptasi dari `skills/blender-render-farm/notebooks/kaggle_render.ipynb` untuk mode **Save & Run All (Commit)** agar bisa ditinggal tutup browser hingga `final_ep001.mp4` siap di tab Output. |
| `scripts/mpfb_human.py` | Loader & controller karakter manusia asli **MPFB2** (`family_ready.blend`): `ENHANCED_SSS` matte skin, `Displace 0.006` kaus kosan, `fix_teeth.py`, Leg IK terkalibrasi, world-space `reach()`, ARKit expressions (`BOOST=1.6` + tulang `jaw`), dan hand-anchored prop tracking (`wrist.R`) anti-melayang. |
| `scripts/fetch_assets.py` | Auto-fetcher **15 properti dapur nyata Poly Haven CC0** + 3 PBR textures + HDRI + auto-copy `family_ready.blend` dari Drive ke cache `02_assets/models_3d/`. |
| `scripts/procedural_props.py` | Properti khas Indonesia & Micro-POV rig: lantai keramik + tembok plester PBR, genangan kuah & mi Indomie, sandal jepit Swallow hijau-putih, kulkas celah kolong 5,5 cm, antena & sayap kecoak amber-cokelat transparan di tepi lensa, serta wind/speed lines halus. |
| `scripts/generate_tts.py` | **Audio-First Voiceover** Gemini 3.8 Flash TTS (`Puck`), default `24fps`, `pad=0.06s`, `vo_speed=1.08`, mendukung `--skip-existing` tanpa API call jika cache VO sudah tersedia. |
| `scripts/prepare_audio.py` | Auto-fetcher SFX CC0 + synthesizer Python (`numpy`/`scipy`) untuk seluruh SFX & loop BGM. |
| `scripts/build_and_render.py` | Blender **5.2.2** headless renderer dengan AgX + Macro DOF + `post.py`, pilihan `--engine CYCLES` (multi-GPU OptiX/CUDA + OIDN) / `--engine EEVEE`, auto-resume per frame (`> 10 KB`), dan automated QC checklist (`TROUBLESHOOTING.md`). |
| `scripts/compose_final.py` | Generator subtitle `.ass` 9:16 anti-terpotong (`MarginL/R=95`, `MarginV=380`, `56pt`, 2–3 kata/baris) + FFmpeg mixing `-14 LUFS` dengan timing presisi Scene 6 & Scene 8. |
| `requirements.txt` | Dependensi Python (`google-genai`, `numpy`, `scipy`, `Pillow`, `requests`, `jsonschema`). |

## Cara Pakai Cepat
- **Google Colab (QC Storyboard / Preview / Revisi):** Buka `03_pipeline/render_episode_colab.ipynb` → pilih Runtime **T4 GPU** → set `RENDER_MODE` & `RENDER_ENGINE` → **Runtime → Run All**.
- **Kaggle 2×T4 (Render Final Ditinggal Tidur):** Import `03_pipeline/render_episode_kaggle.ipynb` → aktifkan **GPU T4 x2** & **Internet On** → tambahkan Input Dataset berisi `family_ready.blend` (+ opsional `scene_01..08.wav`) → klik **Save Version → Save & Run All (Commit)**.
