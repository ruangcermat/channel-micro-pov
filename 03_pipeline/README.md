# 3D Micro-POV — Zero-Manual Automated Production Pipeline

Arsitektur produksi *end-to-end* untuk mengubah `epXXX_spec.json` menjadi video vertikal 9:16 siap upload (`final_epXXX.mp4`) **100% di cloud (Google Colab T4 GPU + Google Drive cache)** tanpa render lokal maupun unduh aset manual.

## Struktur Pipeline (`03_pipeline/`)

| File | Fungsi |
|---|---|
| `render_episode_colab.ipynb` | **Notebook 1-Click Colab (T4 GPU)**: mount Drive → sync repo → install Blender 4.2 LTS → jalankan seluruh pipeline → tampilkan player preview & simpan `.mp4` ke Drive. |
| `scripts/fetch_assets.py` | Auto-fetcher CC0 via **Poly Haven Public API** (tekstur PBR keramik & kayu, HDRI ruangan, model GLTF furnitur) + cache ke Drive `02_assets/` + auto-update `asset_catalog.json`. |
| `scripts/procedural_props.py` | Modul procedural stylized low-poly Blender (`bpy`) untuk objek khas Indonesia: sandal jepit Swallow hijau-putih, genangan kuah & mi Indomie, rig antena + sayap kecoak foreground kamera, siluet manusia rigged, kulkas celah kolong 5.5cm, serta VFX angin/debu/speed-lines. |
| `scripts/generate_tts.py` | **Audio-First Voiceover** via **Gemini 3.8 Flash TTS** (`gemini-3.8-flash-tts`, fallback `gemini-3.8-flash-lite-tts`). Memisahkan `vo_text` (verbatim) dari `vo_delivery` + `voice_persona` lewat `speech_metadata` agar instruksi akting tidak pernah terbaca keras. Menghasilkan `timing_manifest.json` dari durasi aktual WAV. |
| `scripts/prepare_audio.py` | Auto-fetcher SFX CC0/Public Domain langsung via HTTP (Wikimedia Commons) + synthesizer Python (`numpy`/`scipy` + FFmpeg) untuk seluruh SFX & loop BGM (`sneaky_night_loop`, `intense_chase_synth`) dengan jaminan zero-failure. |
| `scripts/build_and_render.py` | Blender Linux headless + **Cycles GPU (OptiX/CUDA + OpenImageDenoise)**. Mendukung `--mode preview` (`540x960`, 16 samples), `--mode final` (`1080x1920`, 30fps, 32 samples), dan `--scene N` untuk revisi parsial 1 adegan. |
| `scripts/compose_final.py` | Auto-generator subtitle dinamis `.ass` (2–4 kata per muncul, bold putih/kuning, outline hitam tebal, margin aman `y = 25%` dari bawah) + FFmpeg mixing VO (`-6 dB`), SFX (`-10 dB`), BGM auto-ducking (`-22 dB`), dan normalisasi `-14 LUFS`. |
| `requirements.txt` | Dependensi Python (`google-genai>=2.24.0`, `numpy`, `scipy`, `requests`, `jsonschema`). |

## Cara Pakai Cepat (Google Colab — 1 Klik)
1. Buka `03_pipeline/render_episode_colab.ipynb` di Google Colab.
2. Pilih **Runtime → Change runtime type → T4 GPU**.
3. Tambahkan `GEMINI_API_KEY` di panel **Secrets** Colab (aktifkan *Notebook access*).
4. Pilih `RENDER_MODE = "preview"` (untuk QC cepat) atau `"final"` (`1080x1920`), lalu klik **Runtime → Run All**.
5. Untuk revisi 1 adegan saja (misal adegan 4), ubah `SINGLE_SCENE = 4` lalu jalankan ulang.

## Menjalankan Manual via CLI (Cloud VM / Linux)
```bash
# 1. Verifikasi / unduh aset CC0 ke cache
python3 03_pipeline/scripts/fetch_assets.py --spec 04_episodes/ep001_kecoak_dapur/ep001_spec.json

# 2. Generate Voiceover Audio-First (membutuhkan GEMINI_API_KEY, atau tambah --dry-run)
python3 03_pipeline/scripts/generate_tts.py --spec 04_episodes/ep001_kecoak_dapur/ep001_spec.json

# 3. Siapkan SFX & BGM CC0 + Procedural Synth
python3 03_pipeline/scripts/prepare_audio.py --spec 04_episodes/ep001_kecoak_dapur/ep001_spec.json

# 4. Render 3D Blender Headless (preview / final, opsional --scene N)
blender --background --python 03_pipeline/scripts/build_and_render.py -- \
  --spec 04_episodes/ep001_kecoak_dapur/ep001_spec.json --mode preview

# 5. Generate Subtitle .ass + Mixing Final -14 LUFS
python3 03_pipeline/scripts/compose_final.py \
  --spec 04_episodes/ep001_kecoak_dapur/ep001_spec.json --mode preview
```
