# MICRO-POV STUDIO SKILL — KITAB TEKNIS RESMI `JADI APA` (v3.0 | EP001–EP100+)

Dokumen ini adalah **satu-satunya rujukan teknis resmi** bagi seluruh agen & pipeline engineer untuk memproduksi episode 3D Micro-POV channel **Jadi Apa** (**@jadiapa3d**) secara modular, konsisten lintas episode, cepat, dan 100% di cloud.

---

## 1. Arsitektur Modular 3 Lapisan (Anti-Rusak Lintas Episode)
DILARANG menaruh logika spesifik satu episode (mis. dapur kecoak, lambung, jalan raya) ke dalam mesin inti!

```text
03_pipeline/
├── core/                         # LAPISAN 1 — UNIVERSAL STUDIO CORE (EP001–EP100+)
│   ├── camera_presets.py         # 5 Arketipe Kamera POV + Beat Modifiers + Floor Clamp + Motion Blur
│   ├── mpfb_helpers.py           # Master Mas Dimas v3.0 (semi-matte 0.55–0.65), Leg IK, reach(), grips
│   ├── paint_mas_dimas_tex.py    # UV texture painter (Crimson #A62C2B + "JADI APA" + garis kuning)
│   ├── lighting_utils.py         # AgX + Adaptive Fast Storyboard (270x480 4s) + Cycles multi-GPU
│   ├── post.py                   # Camera finishing pass (soft lens, glow, vignette, film grain)
│   └── audio_utils.py            # faster-whisper (1/VO_SPEED + anti-hallucination), 15ms fade, room_tone
├── scripts/                      # LAPISAN 2 — GENERIC RUNNERS & UTILITIES
│   ├── build_and_render.py       # Generic runner: load `04_episodes/<ep>/scene_builder.py`
│   ├── build_storyboard_sheet.py # Adaptive Multi-Keyframe sheet builder (maks. 8–9 panel/sheet + sub overlay)
│   ├── generate_tts.py           # Gemini 3.8 Flash TTS (Audio-First + cache Drive)
│   ├── compose_final.py          # faster-whisper ASS + 15ms micro-fade + room_tone + -14 LUFS
│   ├── fetch_assets.py           # Poly Haven CC0 fetcher + Mas Dimas / MPFB2 Drive cache sync
│   └── procedural_props.py       # Reusable procedural prop builders (ruangan, pintu, rak sandal, sandal, rig)
└── MICRO_POV_STUDIO_SKILL.md     # Kitab teknis ini

04_episodes/
└── epXXX_<slug>/                 # LAPISAN 3 — ISOLATED EPISODE BUILDER
    ├── epXXX_spec.json           # Naskah, render_pipeline, spatial_plan, prop_state_chain, room_tone
    ├── epXXX_metadata.md         # Judul, deskripsi, tag YouTube/TikTok/Reels
    └── scene_builder.py          # Builder staging khusus episode ini (tidak menyentuh episode lain!)
```

---

## 2. Unified Look-Dev (*Stylized Semi-Matte*) & Karakter Maskot Permanen **Mas Dimas**
- **1 Bahasa Visual Tunggal Lintas Episode:**
  - **Mas Dimas (`02_assets/models_3d/mas_dimas_ready.blend`):** Kulit hangat Asia Tenggara & pakaian menggunakan material ***soft-matte* (`roughness 0.55–0.65`)** bersih tanpa pori-pori tajam menyeramkan, kaus Crimson `#A62C2B` bertuliskan **`JADI APA`** + garis kuning di tengah dada, **tanpa kacamata**, rambut hitam pendek bervolume (*textured crop*), celana pendek rumahan gelap (`bmesh` crop + `ShortsHemSolidify` + `Displace 0.006`), dan **100% nyeker** (*barefoot*) di dalam rumah/kosan.
  - **Episode Non-Manusia (EP002 Sel Darah Putih, EP003 Kabel Charger, dst.):** WAJIB memakai bahasa visual *stylized semi-matte* (`roughness 0.55–0.65`) bertekstur mikro halus (BUKAN bola/balok polos mentah) + grading identik **`AgX Medium High Contrast` + `Macro DOF` + `post.py`**.
  - **Anchor Opening / Closing:** Episode dalam tubuh atau benda mati WAJIB membuka 2 detik pertama (atau menutup ending) dengan **Mas Dimas** sebagai jangkar semesta sebelum/sesudah kamera masuk ke dunia mikro.
- **Hukum "Anti-Senam Tulang":**
  - **DILARANG** membuat koreografi tubuh rumit melepas alas kaki/pakaian dari rig tubuh yang sedang bergerak.
  - Untuk pengambilan properti (sandal, HP, alat dapur), selalu gunakan **titik ambil statis** (rak sandal rendah, meja, nakas) atau pose *upper-body* + ekspresi wajah ARKit (`BOOST 1.6`).
  - Saat menggenggam sandal (`snap_sandal_to_right_hand()`), pegang di pangkal tumit dengan pronasi pergelangan tangan (`twist=-38°`) agar permukaan sol rata hijau menghadap **depan-bawah ke arah target** (BUKAN berdiri tegak seperti bet pingpong) dan **0% jari menembus sol**.

---

## 3. Hybrid Production Pipeline (`render_pipeline`) & 5 Arketipe Kamera POV
| Jalur (`render_pipeline`) | Kapan Dipakai |
|---|---|
| `blender_3d` *(Default)* | Adegan POV bergerak di ruang 3D nyata (`insect_ground`, `aerial_erratic`, `fluid_float`, `human_first_person`, *whip-pan* 180°, perubahan FOV, *floor clamp*). |
| `parallax_25d` | Khusus adegan `static_object_pov` tenang tanpa perpindahan posisi kamera (gambar statis digerakkan kode 2.5D agar hemat token & waktu). |
| `ai_i2v` | Khusus episode **Semesta Sejarah / Alam Ekstrem** berskala masif (Krakatau 1883, tsunami, kerumunan besar) via Google Flow / Veo. |

> **ATURAN OVERRIDE ZACK-BLENDER-PACK:** Channel **Jadi Apa** memakai 5 arketipe kamera POV organik (`core/camera_presets.py`) + *floor clamp* + `use_motion_blur = True` (`shutter = 0.40`) pada render `final`, dan `use_motion_blur = False` pada Fast Storyboard.

| Arketipe (`camera_archetype`) | Tinggi Default | Floor Clamp | Karakter Gerak & Kegunaan |
|---|---|---|---|
| `insect_ground` | `0.015 m` | `z >= 0.012 m` | Skitter shake cepat, macro DOF (`f/2.8–4.0`), kecoak, semut, serangga lantai |
| `aerial_erratic` | `0.45 m` | `z >= 0.025 m` | Terbang oleng, dynamic banking roll/yaw, rapid wing flutter (kecoak terbang, nyamuk) |
| `fluid_float` | `0.50 m` | bebas | Zero-G drift organik & buoyancy roll (sel darah, lambung, tetesan air) |
| `static_object_pov` | `0.10 m` | `z >= 0.008 m` | Terkunci di objek diam, bergetar/miring saat disentuh tangan (HP, uang, charger) |
| `human_first_person` | `1.60 m` | `z >= 0.25 m` | Tinggi mata manusia, walk bob & chest breathing sway (sejarah, aksi POV manusia) |

**Beat Modifiers (`motion_modifiers`):** `snap_jerk`, `bullet_time`, `whip_pan`, `impact_bump` (4–6 frame), `fov_rush`, `handheld_breath`, `erratic_wobble`, `rapid_wing_flutter`.

---

## 4. Adaptive Multi-Keyframe Fast Storyboard Gate (Pengganti Video `motion_check`)
1. **HARD GATE — ADAPTIVE MULTI-KEYFRAME FAST STORYBOARD (`--mode storyboard`):**
   - Resolusi **`270×480`** per panel, **`4 samples + OIDN`**, `use_persistent_data=True`, `use_motion_blur=False` → selesai **~1–2 menit**.
   - **Jumlah panel & sheet adaptif (tidak dibatasi kaku):** Render sebanyak keyframe yang dibutuhkan, dibagi rapi maksimal **8–9 panel per sheet** (`storyboard_sheet_1.png`, `storyboard_sheet_2.png`, dst.) agar **seluruh transisi penting** (masuk ruangan, tekan saklar, tangan meraih properti dari rak/meja, *bullet-time*, langkah kaki, *whip-pan* kiri/kanan/atas, terbang, hingga **simulasi kotak subtitle ending**) bisa diaudit sebelum render final.
   - Agen **WAJIB Self-QC Vision** terhadap seluruh panel sebelum menampilkan ke user, lalu **STOP TOTAL** menunggu balasan **`ACC STORYBOARD`**.
2. **FINAL RENDER (`--mode final` — Hanya Setelah `ACC STORYBOARD`):**
   - Barulah siapkan bundle Kaggle / Colab dan jalankan render **`final`** (`1080×1920`, `24 fps`, `24 samples + OIDN`, `use_motion_blur=True`, `post.py`) + `compose_final.py` (`-14 LUFS`, `faster-whisper` `1 / VO_SPEED`).

---

## 5. Golden Hero Zone 9:16, 4-Layer Audio Mix & Anti-Bug MPFB2
- **Golden Hero Zone (`1080×1920`):** Wajah ekspresif & aksi utama WAJIB di **`x: 100–900px, y: 260–1250px`** (aman 100% dari bar atas, UI kanan, dan subtitle `MarginV=380`).
- **4-Layer Audio Mix (`-14 LUFS`):** `VO -6 dB` (`faster-whisper` `1 / VO_SPEED` + filter anti-hallucination + `15 ms` micro-fade), `SFX -10 dB` (`skitter_fast` diturunkan `-7 dB` di bawah VO), `BGM -22 dB` (auto-ducking), `Room Tone -32 dB` (`night_fridge_hum`). **Anti-Spoiler Badge:** Jangan tampilkan badge punchline ending di awal scene terakhir; tunda hingga momen punchline (mis. `00:45.5`) atau kosongkan.
- **Checklist Anti-Bug MPFB2 (`TROUBLESHOOTING.md`):**
  - [ ] Jangan pernah zero `$md-*` body shape keys (hanya `!ex-*` + `BOOST=1.6` + tulang `jaw`).
  - [ ] `shoulder01.L/R` WAJIB masuk `POSE_BONES` agar selalu di-reset & di-keyframe setiap frame.
  - [ ] Pertahankan `Hide helpers` MASK di `Kid_body`; hapus hanya `Delete.*` agar kaki nyeker utuh.
  - [ ] Selalu `Displace 0.006`, `fix_teeth.py`, `pack_all()`, `MISSING=[]`, `shoes=0`, `camera_clear=ALL`, dan denoiser `OPENIMAGEDENOISE`.
