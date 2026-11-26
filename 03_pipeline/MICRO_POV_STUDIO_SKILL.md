# MICRO-POV STUDIO SKILL — KITAB TEKNIS RESMI `JADI APA` (EP001–EP100+)

Dokumen ini adalah **satu-satunya rujukan teknis resmi** bagi seluruh agen & pipeline engineer untuk memproduksi episode 3D Micro-POV channel **Jadi Apa** (**Jadi Apa 3D**) secara modular, cepat, konsisten, dan 100% di cloud.

---

## 1. Arsitektur Modular 3 Lapisan (Anti-Rusak Lintas Episode)
DILARANG menaruh logika spesifik satu episode (mis. dapur kecoak, lambung, jalan raya) ke dalam mesin inti!

```text
03_pipeline/
├── core/                         # LAPISAN 1 — UNIVERSAL STUDIO CORE (EP001–EP100+)
│   ├── camera_presets.py         # 5 Arketipe Kamera POV + Beat Modifiers + Motion Blur
│   ├── mpfb_helpers.py           # Master Mas Dimas builder/loader, Leg IK, reach(), ARKit, grips
│   ├── paint_mas_dimas_tex.py    # UV texture painter (Crimson #A62C2B + "JADI APA")
│   ├── lighting_utils.py         # AgX + Cycles multi-GPU / EEVEE fallback + 2-Gate presets
│   ├── post.py                   # Camera finishing pass (soft lens, glow, vignette, film grain)
│   └── audio_utils.py            # faster-whisper word timestamps, 15ms micro-fade, -32dB room_tone
├── scripts/                      # LAPISAN 2 — GENERIC RUNNERS & UTILITIES
│   ├── build_and_render.py       # Generic runner: load `04_episodes/<ep>/scene_builder.py`
│   ├── build_storyboard_sheet.py # Studio 9-panel storyboard_sheet.png generator
│   ├── generate_tts.py           # Gemini 3.8 Flash TTS (Audio-First + cache Drive)
│   ├── compose_final.py          # faster-whisper ASS + 15ms micro-fade + room_tone + -14 LUFS
│   ├── fetch_assets.py           # Poly Haven CC0 fetcher + Mas Dimas / MPFB2 Drive cache sync
│   └── procedural_props.py       # Reusable procedural prop builders
└── MICRO_POV_STUDIO_SKILL.md     # Kitab teknis ini

04_episodes/
└── epXXX_<slug>/                 # LAPISAN 3 — ISOLATED EPISODE BUILDER
    ├── epXXX_spec.json           # Naskah, camera_archetype, motion_modifiers, room_tone, SFX/BGM
    ├── epXXX_metadata.md         # Judul, deskripsi, tag YouTube/TikTok/Reels
    └── scene_builder.py          # Builder staging khusus episode ini (tidak menyentuh episode lain!)
```

---

## 2. Karakter Maskot Permanen — "Mas Dimas" (`mas_dimas_ready.blend`)
- **Lokasi Cache Drive:** `02_assets/models_3d/mas_dimas_ready.blend` (100% tekstur ter-pack).
- **Spesifikasi Visual Wajib:**
  - **Kaus Oblong:** Crimson / Merah Bata (`#A62C2B`) dengan teks kapital tebal putih **`JADI APA`** di tengah dada (di-paint lewat UV `paint_mas_dimas_tex.py`, wajib diverifikasi lewat `mas_dimas_front_check.png` agar tidak terbalik/mirror dan bebas potongan seam UV).
  - **Kacamata:** Bingkai kotak hitam matte (`MasDimas_Glasses`) di-parent ketat (`BONE`) ke tulang `head`, area lensa terbuka / tanpa pantulan silau agar ekspresi mata melotot 100% terbaca di layar HP.
  - **Rambut & Bawahan:** Rambut pendek hitam natural (`short01`), celana pendek rumahan gelap (`bmesh` crop + `ShortsHemSolidify` + `Displace 0.006`), kaki **nyeker** (mesh `shoes*` dihapus total).
  - **Alas Kaki Kontinuitas:** Gunakan `snap_sandal_to_foot(human, sandal, side, frame)` saat Mas Dimas memakai sandal di kaki kiri/kanan, dan `snap_sandal_to_right_hand()` (*heel power-grip*, sol datar menghadap target, sikut *backswing*) saat sandal dipegang tangan kanan.

---

## 3. Pustaka 5 Arketipe Kamera POV (`core/camera_presets.py`)
> **ATURAN OVERRIDE ZACK-BLENDER-PACK:** Panduan *zero shake / dolly only* dari `Zack-Blender-Pack` berlaku untuk film orang ketiga, **BUKAN** untuk 3D Micro-POV! Channel **Jadi Apa** menggunakan gerak kamera organik sesuai subjek POV + `use_motion_blur = True` (`shutter = 0.40`) pada semua render video bergerak (`motion_check`, `preview`, `final`).

| Arketipe (`camera_archetype`) | Tinggi Default | Floor Clamp | Karakter Gerak & Kegunaan |
|---|---|---|---|
| `insect_ground` | `0.015 m` | `z >= 0.012 m` | Skitter shake cepat, macro DOF (`f/2.8–4.0`), cocok untuk kecoak, semut, serangga lantai |
| `aerial_erratic` | `0.45 m` | `z >= 0.025 m` | Terbang oleng, dynamic banking roll/yaw, flutter cepat (kecoak terbang, nyamuk, lalat) |
| `fluid_float` | `0.50 m` | bebas | Zero-G drift organik & buoyancy roll (sel darah, lambung, tetesan air) |
| `static_object_pov` | `0.10 m` | `z >= 0.008 m` | Terkunci di objek diam, bergetar/miring saat disentuh/diangkat tangan (HP, uang, charger) |
| `human_first_person` | `1.60 m` | `z >= 0.25 m` | Tinggi mata manusia, walk bob & chest breathing sway (sejarah, aksi POV manusia) |

**Beat Modifiers (`motion_modifiers` di `epXXX_spec.json`):**
`snap_jerk`, `bullet_time`, `whip_pan`, `impact_bump` (4–6 frame), `fov_rush`, `handheld_breath`, `erratic_wobble`, `rapid_wing_flutter`.

---

## 4. Safe-Zone 9:16 (`1080×1920`) & Subtitle Presisi
- **Upper-Third (y: 12%–48% dari atas):** Wajah ekspresif karakter & aksi utama WAJIB aman di area ini (khususnya close-up klimaks seperti Scene 8).
- **Top Badge:** `MarginV = 260` (Alignment 8 — aman di bawah bar status & judul Shorts/Reels).
- **Subtitle Utama (`.ass`):** `PlayResX=1080, PlayResY=1920`, `WrapStyle=2`, Bold `56pt`, `Outline=5`, `Shadow=2`, `MarginL/R=95`, `MarginV=380`, **2–3 kata (<=18 karakter)** per muncul.
- **Word-Level Sync (`faster-whisper`):** `core/audio_utils.py` mengekstrak timestamp per kata (`word_timestamps=True`) dari WAV VO yang sudah ter-cache agar subtitle presisi milidetik melewati jeda dramatis.
- **Kebersihan Audio:** Micro-fade `15 ms` di awal/akhir tiap potongan WAV scene (anti klik/pop) + `room_tone` dinamis (`-32 dB`) + BGM auto-ducking (`-22 dB`) + master `-14 LUFS`.

---

## 5. 2 Hard Gate Produksi (WAJIB DIPATUHI)
1. **HARD GATE 1 — STORYBOARD (`--mode storyboard`):**
   - Render hanya hero stills (`450×800`, 12 samples, `post.py` ON) → hasilkan `storyboard_sheet.png` (grid berlabel + kartu Aksi, Kamera, VO, SFX/BGM).
   - **DILARANG** melakukan baking penuh 24fps atau menyentuh/menjalankan render Colab/Kaggle sebelum user membalas **`ACC STORYBOARD`**.
2. **HARD GATE 2 — MOTION CHECK (`--mode motion_check`):**
   - Setelah `ACC STORYBOARD`, render full 24fps resolusi ringan (`360×640`, 8 samples, `EEVEE` dengan auto-fallback `Cycles` 8-sample jika headless Linux tanpa EGL, `use_motion_blur=True`, lengkap VO + SFX + `room_tone` + subtitle `faster-whisper`) → `motion_check_epXXX.mp4`.
   - Setelah gerak, pacing, dan safe-zone lolos → baru jalankan render **`final`** (`1080×1920`, 24fps, 24 samples, Kaggle T4 x2 / Colab T4).

---

## 6. Checklist Anti-Bug Wajib (`TROUBLESHOOTING.md` + Studio Rules)
- [ ] **JANGAN pernah men-zero shape key `$md-*`** (hanya animasikan `!ex-*` + `BOOST=1.6` + tulang `jaw`).
- [ ] **Pertahankan modifier `Hide helpers` (MASK)** di `Kid_body`; hapus hanya `Delete.*` agar kaki nyeker utuh.
- [ ] **Selalu `Displace 0.006`** pada mesh baju & `fix_teeth.py` pada gigi/gusi.
- [ ] **Selalu `pack_all()`** sebelum menyimpan `.blend` master atau render farm, dan pastikan `MISSING=[]` (nol tekstur pink).
- [ ] **Zero A-pose:** Selalu pose lengan/tangan/kaki pakai `doc_pose.py` + `reach()` + Leg IK terkalibrasi.
- [ ] **Kamera bersih (`camera_clear=ALL`):** Raycast 6 cm di depan lensa wajib bebas prop di semua panel/scene, dan clamp `z >= min_z`.
- [ ] **Kontinuitas properti:** Cek konsistensi alas kaki, properti tangan, dan posisi jam/saklar antar adegan yang berurutan.
- [ ] **OIDN wajib aktif** (`scene.cycles.denoiser = "OPENIMAGEDENOISE"`) — jangan pakai OptiX denoiser di GPU T4 Colab/Kaggle.
