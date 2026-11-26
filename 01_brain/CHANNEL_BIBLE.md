# CHANNEL BIBLE — JADI APA (3D MICRO-POV INDONESIA, v2.0)

## 1. Identitas & Konsep Inti (RESMI DIKUNCI)
- **Nama Channel:** **Jadi Apa** (handle cadangan: **Jadi Apa 3D**)
- **Karakter Maskot Utama (Permanen):** **Mas Dimas** (`mas_dimas_ready.blend`)
  - Pria muda anak kosan Indonesia yang ekspresif, selalu mengenakan **kaus oblong Merah Bata / Crimson (`#A62C2B`) bertuliskan kapital tebal putih `JADI APA`** di tengah dada, **kacamata kotak bingkai hitam matte** (tanpa silau lensa agar ekspresi mata tetap 100% terbaca di layar HP), rambut pendek hitam natural, celana pendek rumahan gelap, dan kaki **nyeker** (atau sandal jepit Swallow hijau sesuai kontinuitas adegan).
  - Muncul berulang lintas episode Semesta Kosan, Jalanan, maupun cameo visual agar penonton langsung mengenali brand **Jadi Apa** dalam < 1 detik!
- **Format:** Faceless 3D Animated Edutainment — *Micro-POV* (Sudut Pandang Orang Pertama / Kedua: "Bayangin kamu jadi...").
- **Premis Utama:** Memasukkan penonton langsung ke dalam tubuh, objek, hewan, atau situasi tertentu selama 35–50 detik. Penonton tidak sedang menonton video pelajaran, melainkan sedang "menjadi" tokoh utama di dalam sebuah mini-film yang lucu, tegang, sekaligus membuka wawasan.
- **Target Audiens:** Audiens Indonesia lintas usia (remaja hingga dewasa muda, 15–35 tahun) di YouTube Shorts, TikTok, dan Instagram Reels.
- **Posisi Unik (Pembeda dari Zack D. Films & Odd Tilt):**
  - Bukan anatomi klinis/ngilu ala Zack D. Films.
  - Bukan komedi sejarah penemuan benda ala Odd Tilt.
  - Fokus pada **pengalaman imersif (Micro-POV)**, observasi khas keseharian Indonesia bersama **Mas Dimas**, plus selipan fakta sains/realita yang terasa alami (bukan ceramah).

---

## 2. Gaya Bahasa & Aturan Naskah (ANTI-MENGGURUI)
- **Persona Narator:** Teman nongkrong yang cerdas, ekspresif, agak nyeleneh, dan jago mendramatisasi hal sepele.
- **Sudut Pandang:** Wajib gunakan kata **"kamu"** secara langsung sejak detik pertama agar penonton langsung masuk ke peran.
- **Aturan Anti-Kaku:**
  - ❌ DILARANG buka video dengan: *"Halo guys"*, *"Tahukah kamu"*, *"Pernahkah kalian berpikir"*, atau *"Secara ilmiah..."*.
  - ❌ DILARANG menggunakan bahasa terjemahan kaku (*"Anda kemudian mengalami..."*).
  - ✅ GUNAKAN bahasa Indonesia lisan yang luwes, kalimat pendek (maksimal 10–14 kata per kalimat), dan ritme bicara cepat dengan *comedic timing*.
  - ✅ Sisipkan fakta sains/logika sebagai **alasan kejadian di dalam cerita**, bukan materi pelajaran.
    - *Salah:* "Kecoak memiliki organ bernama cerci yang mendeteksi hembusan angin."
    - *Benar:* "Dua antena di pantatmu langsung nangkep angin dari ayunan tangannya."

---

## 3. Rumus Retensi 35–50 Detik
1. **Detik 0–3 (Hook Instan + Konflik):** Langsung lempar penonton ke peran DAN masalah genting di kalimat pertama.
2. **Detik 4–30 (Eskalasi + Fakta Tersembunyi):** Setiap 5–7 detik wajib ada perubahan situasi, rintangan baru, atau fakta menarik yang memicu reaksi "oh pantesan!" atau "anjir bener juga!".
3. **Detik 31–42 (Klimaks & Twist/Payoff):** Puncak ketegangan atau aksi paling absurd/relatable.
4. **Detik 43–48 (Ending Tajam / Loop):** Selesai langsung potong di punchline terkuat, atau sambungkan kalimat terakhir ke kalimat pertama (*perfect loop*). Tanpa penutup basa-basi (*"Jangan lupa like dan subscribe"*).

---

## 4. Standar Visual, Kamera POV, & Audio
- **Visual & Look-Dev:** 3D Blender 5.2.2 LTS + **MPFB2 (Mas Dimas)** + properti nyata Poly Haven CC0 + **AgX Medium High Contrast** + **Macro DOF** + kamera finish `post.py`.
- **5 Arketipe Kamera POV (`camera_presets.py`):** Berbeda dari film orang ketiga yang statis, kamera **Jadi Apa** adalah POV imersif yang bergerak sesuai subjek (`insect_ground`, `aerial_erratic`, `fluid_float`, `static_object_pov`, `human_first_person`) dengan *motion blur* (`shutter=0.40`).
- **Safe-Zone 9:16 (`1080×1920`):** Wajah & aksi utama di **upper-third / center-upper**, subtitle 2–3 kata di **MarginV=380**, aman dari UI TikTok/Shorts/Reels.
- **Audio & Subtitle Presisi:**
  - Voiceover Gemini 3.8 Flash TTS (`Puck`, `VO_SPEED=1.08`) dengan *micro-fade* `15 ms` + *word-level timestamps* (`faster-whisper`) + *room tone* dinamis (`-32 dB`) + BGM auto-ducking (`-22 dB`) + master `-14 LUFS`.

---

## 5. Protokol Produksi & 2 Hard Gate
Setiap episode baru (`EP002–EP100+`) WAJIB melewati 3 Pass Penulisan (`epXXX_spec.json`) + **2 Hard Gate Visual** sebelum render final 1080×1920:
- **Gate 1 (Storyboard):** Render & tampilkan `storyboard_sheet.png` (9 panel + kartu Aksi/Kamera/VO/SFX). DILARANG render penuh sebelum user membalas **`ACC STORYBOARD`**.
- **Gate 2 (Motion Check):** Render cepat `motion_check` (`360×640`, 8 samples, lengkap VO+SFX+subtitle) untuk cek rasa gerak & safe-zone sebelum render **`final`** `1080×1920`.
