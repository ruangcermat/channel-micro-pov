# SERIES UNIVERSE — PETA DUNIA & KONTINUITAS JADI APA (v3.0)

Dokumen ini menjaga agar channel **Jadi Apa** (**@jadiapa3d**) memiliki semesta yang saling terhubung dengan 1 bahasa visual tunggal (*Unified Stylized Semi-Matte*) dan karakter maskot permanen **Mas Dimas**.

---

## 0. Profil Maskot Permanen & Unified Look-Dev Lintas Semesta — **Mas Dimas**
- **Master Rig:** `02_assets/models_3d/mas_dimas_ready.blend` (MPFB2 + 100% tekstur ter-pack).
- **Ciri Visual Permanen (*Unified Stylized Semi-Matte*):**
  - **Wajah & Rambut:** Pria muda Indonesia **tanpa kacamata** (mata & alis 100% terbuka), **rambut hitam pendek bervolume** (*textured crop*), **kulit hangat Asia Tenggara** *soft-matte* (**`roughness 0.55–0.65`**, bersih tanpa pori-pori tajam menyeramkan).
  - **Atasan Ikonik:** Kaus oblong **Merah Bata / Crimson (`#A62C2B`, `roughness 0.62`)** bertuliskan kapital tebal putih **`JADI APA`** + **garis aksen kuning** tepat di tengah dada.
- **Konsistensi Visual Episode Non-Manusia & Jangkar Semesta (*Anchor Opening/Closing*):**
  - Episode objek/organ non-manusia (mis. Sel Darah Putih di EP002, Kabel Charger di EP003) WAJIB memakai permukaan *stylized semi-matte* (`roughness 0.55–0.65`) bertekstur halus + **`AgX Medium High Contrast` + `Macro DOF` + `post.py`** agar seragam 100% dengan dunia Mas Dimas (bukan bola/balok polos mentah).
  - Episode dalam tubuh atau benda mati WAJIB dibuka **2 detik pertama** (atau ditutup di ending) dengan **Mas Dimas** sebagai jangkar semesta sebelum/sesudah kamera masuk ke dunia mikro.
- **Aturan Adaptasi Pakaian & Hukum Anti-Senam Tulang:**
  - **Semesta Kosan & Rumah:** Kaus `JADI APA` + **celana pendek rumahan gelap** + **100% nyeker (*barefoot*)** di dalam ruangan. Sandal jepit Swallow hijau diletakkan di **rak sandal rendah statis** di bawah jam dinding `02:00` (BUKAN dilepas dari kaki rig yang bergerak — *Hukum Anti-Senam Tulang*!).
  - **Semesta Jalanan & Keseharian:** Kaus `JADI APA` + celana panjang santai gelap + sepatu kasual sesuai konteks lokasi.
  - **Semesta Dalam Tubuh:** Mas Dimas tampil 2 detik pembuka/penutup sebagai tuan rumah sebelum kamera masuk ke organ tubuh (`fluid_float`).
  - **Semesta Sejarah & Alam Ekstrem:** Menggunakan jalur `render_pipeline: "ai_i2v"` (Google Flow / Veo) untuk skala masif (letusan gunung, tsunami, kerumunan).

---

## 1. Semesta Kosan & Rumah (`render_pipeline: "blender_3d"` / `"parallax_25d"`)
Latar: Kamar kosan & dapur kontrakan **Mas Dimas** khas Indonesia (pintu kamar kayu kanan yang menutup rapat, rak sandal kayu rendah di bawah jam `02:00`, kulkas, saklar Broco kanan kulkas, rak dapur kiri padat, lantai keramik nat).
- **Penghuni / Objek Utama:**
  - **Mas Dimas** (Debut: `EP001`) — Anak kosan yang suka masak mi jam dua pagi, musuh bebuyutan kecoak dapur.
  - **Si Kecoak Dapur** (Debut: `EP001`, `blender_3d`) — Pejuang remah-remah jam dua pagi, musuh abadi sandal jepit Swallow hijau milik Mas Dimas.
  - **Si Cicak Plafon** (`blender_3d`) — Pengamat dari atas yang sering jatuh pas lagi galau tepat di depan Mas Dimas.
  - **Kabel Charger Sekarat** (`EP003`, `parallax_25d` + Anchor Mas Dimas) — Cuma mau ngecas HP Mas Dimas kalau ditekuk miring empat puluh lima derajat.
  - **Kulkas Kosan** (`parallax_25d` / `blender_3d`) — Trauma dimasuki panci kuah panas dan isinya cuma air dingin + sambal saset.
  - **Nasi Sisa Kemarin di Rice Cooker** (`parallax_25d`) — Menuju fase kering keras jadi kerupuk.

## 2. Semesta Dalam Tubuh (`render_pipeline: "blender_3d"` + Anchor Mas Dimas)
Latar: Organ dalam tubuh **Mas Dimas** (kamera `fluid_float`, tekstur *stylized semi-matte* `0.55–0.65`, selalu dibuka 2 detik Mas Dimas sebagai jangkar!).
- **Ide Episode:**
  - **Sel Darah Putih** (`EP002`) saat Mas Dimas nekat begadang + minum es tiap malam.
  - **Lambung** saat dikasih seblak level lima padahal belum sarapan.
  - **Otak** yang bikin lupa tujuan begitu masuk kamar (*Doorway Effect*).
  - **Saraf Kaget** yang nyetrum badan biar bangun pas baru mau tidur (*Hypnic Jerk*).

## 3. Semesta Jalanan & Keseharian Indonesia (`blender_3d` / `parallax_25d`)
Latar: Jalan raya, minimarket, gudang ekspedisi, warung (Mas Dimas memakai pakaian kasual jalanan).
- **Ide Episode:** Uang Dua Ribu Lusuh, Paket COD, Nyamuk Kamar (`aerial_erratic`), Baterai HP Satu Persen (`static_object_pov` / `parallax_25d`).

## 4. Semesta Sejarah & Alam Ekstrem (`render_pipeline: "ai_i2v"` via Google Flow / Veo)
Latar: Peristiwa sejarah Nusantara/dunia atau fenomena alam berskala masif.
- **Ide Episode:** Warga Pesisir Selat Sunda Agustus 1883 saat Gunung Krakatau meletus (`ai_i2v`), Tetesan Air Hujan (`blender_3d`), Semut Pekerja (`blender_3d`).

---

## Aturan Rotasi Kategori (Biar Feed Segar & Anti-Bosan)
1. Semesta Kosan/Benda (Komedi & *Relatable*)
2. Semesta Dalam Tubuh (Sains Ringan + Anchor Mas Dimas)
3. Semesta Jalanan/Keseharian (Observasi Lokal)
4. Semesta Sejarah/Alam (`ai_i2v` Skala Epik / Ketegangan)
*Sesuaikan porsi kategori berdasarkan pemenang data di `PERFORMANCE_LOG.csv` setelah 5–10 episode.*
