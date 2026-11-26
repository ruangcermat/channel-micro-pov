# CHANNEL BIBLE — 3D MICRO-POV INDONESIA (v1.0)

## 1. Identitas & Konsep Inti
- **Format:** Faceless 3D Animated Edutainment — *Micro-POV* (Sudut Pandang Orang Pertama / Kedua: "Bayangin kamu jadi...").
- **Premis Utama:** Memasukkan penonton langsung ke dalam tubuh, objek, hewan, atau situasi tertentu selama 35–50 detik. Penonton tidak sedang menonton video pelajaran, melainkan sedang "menjadi" tokoh utama di dalam sebuah mini-film yang lucu, tegang, sekaligus membuka wawasan.
- **Target Audiens:** Audiens Indonesia lintas usia (remaja hingga dewasa muda, 15–35 tahun) di YouTube Shorts, TikTok, dan Instagram Reels.
- **Posisi Unik (Pembeda dari Zack D. Films & Odd Tilt):**
  - Bukan anatomi klinis/ngilu ala Zack D. Films.
  - Bukan komedi sejarah penemuan benda ala Odd Tilt.
  - Fokus pada **pengalaman imersif (POV)**, observasi khas keseharian Indonesia, plus selipan fakta sains/realita yang terasa alami (bukan ceramah).

---

## 2. Gaya Bahasa & Aturan Naskah (ANTI-MENGGURUI)
- **Persona Narator:** Teman nongkrong yang cerdas, ekspresif, agak nyeleneh, dan jago mendramatisasi hal sepele.
- **Sudut Pandang:** Wajib gunakan kata **"kamu"** secara langsung sejak detik pertama agar penonton langsung masuk ke peran.
- **Aturan Anti-Kaku:**
  - ❌ DILARANG buka video dengan: *"Halo guys"*, *"Tahukah kamu"*, *"Pernahkah kalian berpikir"*, atau *"Secara ilmiah..."*.
  - ❌ DILARANG menggunakan bahasa terjemahan kaku (*"Anda kemudian mengalami..."*).
  - ✅ GUNAKAN bahasa Indonesia lisan yang luwes, kalimat pendek (maksimal 10–14 kata per kalimat), dan ritme bicara yang cepat tapi punya jeda komedi (*comedic timing*).
  - ✅ Sisipkan fakta sains/logika sebagai **alasan kejadian di dalam cerita**, bukan sebagai materi pelajaran.
    - *Salah:* "Kecoak memiliki organ bernama cerci yang mendeteksi hembusan angin."
    - *Benar:* "Dua antena kecil di pantatmu langsung nangkep hembusan angin dari telapak kakinya—bahkan sebelum otaknya sadar dia mau nginjek kamu."

---

## 3. Rumus Retensi 35–50 Detik
1. **Detik 0–3 (Hook Instan + Konflik):** Langsung lempar penonton ke peran DAN masalah genting di kalimat pertama.
   - Contoh: *"Jam 2 pagi. Lampu dapur tiba-tiba nyala—dan kamu adalah seekor kecoak yang lagi asyik jilatin sisa kuah indomie."*
2. **Detik 4–30 (Eskalasi + Fakta Tersembunyi):** Setiap 5–7 detik wajib ada perubahan situasi, rintangan baru, atau fakta menarik yang memicu reaksi "oh pantesan!" atau "anjir bener juga!".
3. **Detik 31–42 (Klimaks & Twist/Payoff):** Puncak ketegangan atau aksi paling absurd/relatable.
4. **Detik 43–45 (Ending Tajam / Loop):** Selesai langsung potong di punchline terkuat, atau sambungkan kalimat terakhir ke kalimat pertama agar terjadi *perfect loop*. Tanpa penutup basa-basi (*"Jangan lupa like dan subscribe"*).

---

## 4. Standar Visual & Audio
- **Visual:** 3D Low-Poly / Stylized bersih dengan pencahayaan kontras tinggi (gaya ramah render cepat via Blender EEVEE / Three.js).
- **Kejelasan Visual (*Readability*):** Resolusi vertikal `1080x1920` (9:16). Setiap 2–3 detik wajib ada pergerakan kamera POV (goyangan lari, *whip pan*, *zoom* panik) atau perubahan aksi objek.
- **Audio (Kunci Rasa "Mahal"):**
  - Voiceover ekspresif dengan perubahan tempo (tenang -> panik -> dramatis).
  - SFX wajib rapat: *whoosh*, *heartbeat*, *thud*, *pop*, suara lingkungan (saklar lampu, decit sandal, suara kompor).
  - BGM mengikuti dinamika emosi (tenang/misterius di awal -> tegang/aksi di tengah -> *record scratch* / berhenti mendadak saat *punchline*).
- **Subtitle:** Font tebal, kontras tinggi (putih/kuning dengan *outline* hitam), 2–4 kata per muncul di area aman tengah-bawah (tidak tertutup UI TikTok/Shorts).

---

## 5. Protokol Penulisan Multi-Pass (Writer's Room)
Setiap naskah baru WAJIB melewati 3 tahap sebelum keluar menjadi `epXX_spec.json`:
1. **Pass 1 (Riset & Struktur):** Tentukan premis POV, 2–3 fakta nyata/observasi tajam, dan alur konflik 40–45 detik.
2. **Pass 2 (Roast / Kritik Pedas):** Evaluasi draf dari sudut pandang penonton TikTok/Shorts Indonesia yang gampang bosan. Coret kalimat bertele-tele, buang nada menggurui, dan tajamkan hook 3 detik pertama.
3. **Pass 3 (Poles Lisan & Produksi):** Ubah ke bahasa lisan super luwes, pecah per adegan 2–4 detik, lalu susun output final menjadi `epXX_spec.json` + `epXX_metadata.md`.
