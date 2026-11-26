# MICRO-POV STUDIO SKILL — KITAB TEKNIS RESMI `JADI APA` (v2.0 | EP001–EP100+)

Dokumen ini adalah **satu-satunya rujukan teknis resmi** bagi seluruh agen & pipeline engineer untuk memproduksi episode 3D Micro-POV channel **Jadi Apa** (**@jadiapa3d**) secara modular, cepat, konsisten, dan 100% di cloud.

---

## 1. Arsitektur Modular 3 Lapisan (Anti-Rusak Lintas Episode)
DILARANG menaruh logika spesifik satu episode (mis. dapur kecoak, lambung, jalan raya) ke dalam mesin inti!

```text
03_pipeline/
├── core/                         # LAPISAN 1 — UNIVERSAL STUDIO CORE (EP001–EP100+)
│   ├── camera_presets.py         # 5 Arketipe Kamera POV + Beat Modifiers + Floor Clamp + Motion Blur
│   ├── mpfb_helpers.py           # Master Mas Dimas builder/loader, Leg IK, reach(), bone-parent sandal, grips
│   ├── paint_mas_dimas_tex.py    # UV texture painter (Crimson #A62C2B + "JADI APA" + garis kuning)
│   ├── lighting_utils.py         # AgX + Fast Draft Storyboard (<60s) + Cycles multi-GPU / EEVEE fallback
│   ├── post.py                   # Camera finishing pass (soft lens, glow, vignette, film grain)
│   └── audio_utils.py            # faster-whisper word timestamps, 15ms micro-fade, -32dB room_tone
├── scripts/                      # LAPISAN 2 — GENERIC RUNNERS & UTILITIES
│   ├── build_and_render.py       # Generic runner: load `04_episodes/<ep>/scene_builder.py`
│   ├── build_storyboard_sheet.py # Studio 9-panel storyboard_sheet.png generator
│   ├── generate_tts.py           # Gemini 3.8 Flash TTS (Audio-First + cache Drive)
│   ├── compose_final.py          # faster-whisper ASS + 15ms micro-fade + room_tone + -14 LUFS
│   ├── fetch_assets.py           # Poly Haven CC0 fetcher + Mas Dimas / MPFB2 Drive cache sync
│   └── procedural_props.py       # Reusable procedural prop builders (ruangan, pintu, sandal, antena/sayap)
└── MICRO_POV_STUDIO_SKILL.md     # Kitab teknis ini

04_episodes/
└── epXXX_<slug>/                 # LAPISAN 3 — ISOLATED EPISODE BUILDER
    ├── epXXX_spec.json           # Naskah, spatial_plan, prop_state_chain, camera_archetype, room_tone
    ├── epXXX_metadata.md         # Judul, deskripsi, tag YouTube/TikTok/Reels
    └── scene_builder.py          # Builder staging khusus episode ini (tidak menyentuh episode lain!)
```

---

## 2. Karakter Maskot Permanen — "Mas Dimas" (`mas_dimas_ready.blend`)
- **Lokasi Cache Drive:** `02_assets/models_3d/mas_dimas_ready.blend` (100% tekstur ter-pack).
- **Spesifikasi Visual Wajib (v2.0 — TANPA KACAMATA):**
  - **Kaus Oblong:** Crimson / Merah Bata (`#A62C2B`) dengan teks kapital tebal putih **`JADI APA`** + **garis aksen kuning** tepat di tengah dada (UV-painted via `paint_mas_dimas_tex.py`, diverifikasi lewat `mas_dimas_front_check.png` agar tidak mirror & bebas potongan seam UV).
  - **Wajah & Rambut:** **TANPA kacamata** (ekspresi mata & alis 100% terbuka), **rambut hitam pendek bervolume** (siluet *textured crop* matte dengan volume atas-depan & poni ringan, bukan topi renang gepeng), alis gelap natural, dan **kulit hangat Asia Tenggara** (*warm natural tone*).
  - **Bawahan & Alas Kaki:** Celana pendek rumahan gelap (`bmesh` crop + `ShortsHemSolidify` + `Displace 0.006`), kaki **nyeker** (`shoes*` dihapus total).
  - **Kontinuitas Alas Kaki & Grip:**
    - Gunakan **`attach_sandal_to_foot_bone(human, sandal, side="L")`** untuk parent ketat (`BONE`) sandal ke tulang `foot.L`, lalu naikkan kaki bersandal sebesar **`+0.018 m`** (`left_sole_lift=0.018`) agar seluruh sol hijau+putih berada utuh di atas keramik (`z >= +0.001 m`, nol tenggelam).
    - Gunakan **`snap_sandal_to_right_hand()`** dengan pronasi pergelangan tangan (`twist=-38°`), genggam ujung pangkal tumit (*heel*), permukaan sol datar hijau menghadap **depan-bawah ke arah target** (BUKAN berdiri tegak seperti bet pingpong), dan **0% jari menembus sol**.

---

## 3. Pustaka 5 Arketipe Kamera POV (`core/camera_presets.py`)
> **ATURAN OVERRIDE ZACK-BLENDER-PACK:** Panduan *zero shake / dolly only* berlaku untuk film orang ketiga, **BUKAN** untuk 3D Micro-POV! Channel **Jadi Apa** memakai gerak kamera organik sesuai subjek POV + `use_motion_blur = True` (`shutter = 0.40`) pada render bergerak (`motion_check`, `preview`, `final`), dan `use_motion_blur = False` pada gambar diam `storyboard`.

| Arketipe (`camera_archetype`) | Tinggi Default | Floor Clamp | Karakter Gerak & Kegunaan |
|---|---|---|---|
| `insect_ground` | `0.015 m` | `z >= 0.012 m` | Skitter shake cepat, macro DOF (`f/2.8–4.0`), kecoak, semut, serangga lantai |
| `aerial_erratic` | `0.45 m` | `z >= 0.025 m` | Terbang oleng, dynamic banking roll/yaw, rapid wing flutter (kecoak terbang, nyamuk) |
| `fluid_float` | `0.50 m` | bebas | Zero-G drift organik & buoyancy roll (sel darah, lambung, tetesan air) |
| `static_object_pov` | `0.10 m` | `z >= 0.008 m` | Terkunci di objek diam, bergetar/miring saat disentuh tangan (HP, uang, charger) |
| `human_first_person` | `1.60 m` | `z >= 0.25 m` | Tinggi mata manusia, walk bob & chest breathing sway (sejarah, aksi POV manusia) |

**Beat Modifiers (`motion_modifiers`):** `snap_jerk`, `bullet_time`, `whip_pan`, `impact_bump` (4–6 frame), `fov_rush`, `handheld_breath`, `erratic_wobble`, `rapid_wing_flutter`.

---

## 4. Golden Hero Zone 9:16 & 4-Layer Audio Mix
- **Golden Hero Zone (`1080×1920`):** Wajah ekspresif & aksi utama WAJIB berada di **`x: 100–900px, y: 260–1250px`** (aman 100% dari bar atas, UI kanan, dan subtitle `MarginV=380`).
- **4-Layer Audio Mix (`-14 LUFS`):** `VO -6 dB` (`faster-whisper` word-level karaoke `.ass` + `15 ms` micro-fade), `SFX -10 dB`, `BGM -22 dB` (auto-ducking), `Room Tone -32 dB` (mis. `night_fridge_hum`).

---

## 5. 2 Hard Gate Produksi & Fast Draft Storyboard (< 1 Menit)
1. **HARD GATE 1 — FAST DRAFT STORYBOARD (`--mode storyboard`):**
   - Resolusi **`270×480`** (1/4 skala 1080×1920), **`4 samples` + OpenImageDenoise**, `use_persistent_data=True`, `use_motion_blur=False` → selesai **< 60 detik** untuk 9 panel → `storyboard_sheet.png`.
   - Agen **WAJIB Self-QC Vision** terhadap seluruh 6 aturan di bawah sebelum menampilkan ke user, lalu **STOP** hingga user membalas **`ACC STORYBOARD`**.
2. **HARD GATE 2 — MOTION CHECK (`--mode motion_check`):**
   - Full 24fps `360×640`, 8 samples (EEVEE / Cycles fallback) + `use_motion_blur=True` + 4-Layer Audio Mix + subtitle `faster-whisper` → `motion_check_epXXX.mp4`.
   - Lolos Gate 2 → baru lanjut render **`final`** (`1080×1920`, 24fps, 24 samples, `use_motion_blur=True`).

---

## 6. Pelajaran Pra-Produksi & Produksi Pilot EP001 (DILARANG TERULANG)
1. **Asal-Usul & Tujuan Ruang (*Spatial Origin & Destination*):** Karakter tidak boleh muncul dari dinding kosong; wajib ada pintu masuk/jalur logis (`spatial_plan`) menuju tujuan jelas (mis. keluar pintu kamar kanan → saklar di samping kanan kulkas).
2. **Kausalitas & Kontak Tanah (*Prop State Chain & Ground Contact*):** Benda wajib punya asal-usul (`prop_state_chain`), di-parent ketat (`BONE`) ke tulang terkait, dan tinggi kaki menapak wajib menambah ketebalan sol (`z = +0.018 m`) agar alas kaki tidak pernah tembus lantai.
3. **Orientasi Grip Benda Genggam:** Benda seperti sandal/pisau dipegang di pangkalnya dengan permukaan kerja menghadap arah aksi, bukan tegak seperti bet pingpong, dan **0% tembus jari**.
4. **Lokalitas Indonesia & Anti-Spoiler:** Pakaian, alas kaki, kulit, rambut, dan properti autentik Indonesia; jangan tampilkan objek kejutan sebelum waktunya di VO; wajib cek & ubah detail statis aset CC0 (contoh: jam dinding `10:10` → jam naskah `02:00`).
5. **Batas Aset Prosedural & 5 Arketipe Kamera POV:** Dilarang membangun anatomi atau aksesoris wajah (kacamata/tubuh) dari balok kode mentah; wajib MPFB2/CC0 proper + 5 Arketipe Kamera POV + *floor clamp* + *motion blur* + *secondary motion*.
6. **Fast Storyboard + Self-QC Vision + 2 Hard Gate:** Storyboard memakai Fast Draft (`270×480`, 4 samples < 1 menit); agen wajib inspeksi visual sendiri sebelum lapor ke user; patuhi Gate 1 (`storyboard_sheet.png`) dan Gate 2 (`motion_check`) sebelum `final`.

---

## 7. Checklist Anti-Bug MPFB2 (`TROUBLESHOOTING.md`)
- [ ] Jangan pernah zero `$md-*` body shape keys (hanya `!ex-*` + `BOOST=1.6` + tulang `jaw`).
- [ ] `shoulder01.L/R` WAJIB masuk `POSE_BONES` agar selalu di-reset & di-keyframe setiap frame.
- [ ] Pertahankan `Hide helpers` MASK di `Kid_body`; hapus hanya `Delete.*` agar kaki nyeker utuh.
- [ ] Selalu `Displace 0.006`, `fix_teeth.py`, `pack_all()`, `MISSING=[]`, `shoes=0`, `camera_clear=ALL`, dan denoiser `OPENIMAGEDENOISE`.
