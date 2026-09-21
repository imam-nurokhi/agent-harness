# Platform AI Nexora — Ringkasan Eksekutif

**20 September 2026**

Dokumen ini merangkum apa yang sudah berjalan, apa manfaatnya, dan apa yang masih
menunggu keputusan. Ditulis untuk dibaca tanpa latar belakang teknis.

---

## Apa yang sudah berjalan

Ada satu asisten AI yang kini menemani dua aplikasi Nexora: **NexAccred** untuk
akreditasi dan **DeAcademy** untuk pembelajaran. Ia muncul sebagai tombol kecil di
pojok layar, siap menjawab pertanyaan tentang aplikasi yang sedang dibuka.

Selain itu, tim kini punya **dua asisten di Telegram** dengan peran yang sengaja
dipisah: satu untuk bertanya, satu untuk bekerja.

| Yang tersedia | Untuk siapa | Bisa melakukan apa |
|---|---|---|
| Asisten di dalam aplikasi | manajemen, asesor, peserta | menjawab pertanyaan tentang aplikasi |
| Asisten di Telegram | tim non-teknis | menjawab pertanyaan tentang kedua produk |
| Asisten pengembangan di Telegram | pemilik sistem | mengerjakan perbaikan dan pengembangan |

---

## Mengapa asisten ini tidak mengarang

Ini pembeda yang paling penting, dan ia hasil pilihan desain, bukan kebetulan.

Asisten di dalam aplikasi **tidak menebak**. Ia hanya menjawab dari dokumentasi
produk yang sudah disetujui. Bila sebuah pertanyaan belum tercakup, ia mengatakan
terus terang bahwa ia belum tahu — lalu mencatat pertanyaan itu.

Catatan itulah yang membuat sistem ini membaik sendiri. Setiap pertanyaan yang
gagal dijawab menjadi daftar pekerjaan yang konkret, bukan keluhan yang menguap.
Hasilnya sudah terlihat: setelah satu putaran perbaikan berdasarkan pertanyaan
nyata pengguna, kemampuan menjawab **DeAcademy naik dari 63% ke 100%** dan
**NexAccred dari 92% ke 100%** pada rangkaian pertanyaan uji yang realistis.

Ringkasan pertanyaan yang belum terjawab dikirim otomatis ke Telegram setiap
Jumat pagi, jadi tidak ada yang perlu mengingat untuk memeriksanya.

---

## Apa yang bisa dilakukan asisten NexAccred

Untuk akreditasi, asisten melangkah lebih jauh daripada sekadar menjawab:

- **Menyesuaikan diri dengan layar yang sedang dibuka** — saran pertanyaannya
  berubah mengikuti konteks pengguna.
- **Memandu per area penilaian** — sembilan area penilaian masing-masing punya
  penuntun yang mengantar pengguna ke layar yang tepat.
- **Menahan persetujuan yang belum layak** — bila prasyarat belum lengkap, ia
  menolak meneruskan dan menunjukkan apa yang masih kurang.

---

## Keamanan: apa yang tidak bisa dilakukan asisten

Sama pentingnya dengan apa yang bisa ia lakukan.

- Asisten **tidak bisa mengubah data apa pun**. Ia hanya membaca.
- Asisten di Telegram untuk tim non-teknis **tidak bisa menjalankan perintah,
  membuka internet, atau menyentuh Slack, Notion, dan GitHub**. Semua itu ditutup
  di tingkat sistem, bukan sekadar diinstruksikan.
- Pengguna non-teknis **tidak akan pernah disodori tombol izin teknis** yang tidak
  bisa mereka nilai.
- Seluruh alamat web berada di balik autentikasi. Tidak ada yang terbuka ke publik.
- Kata sandi dan token tidak pernah melewati percakapan; semuanya disimpan di
  server dengan izin akses paling ketat.

Klaim "hanya membaca" di atas tidak diasumsikan. Sistem diuji dengan meminta
asisten menjalankan perintah dan membuat berkas; ia tidak bisa, dan berkasnya
memang tidak pernah ada.

---

## Cara pengembangan dikerjakan sekarang

Pekerjaan perbaikan dan pengembangan bisa diminta lewat Telegram dengan bahasa
biasa. Yang terjadi setelah itu berlapis, dan lapisan terakhirnya adalah Anda:

1. Asisten pengembangan mengerjakan permintaan di ruang kerja terpisah.
2. Hasilnya bisa ditinjau sebelum ke mana-mana.
3. Perubahan didorong ke **cabang baru**, tidak pernah langsung ke cabang utama.
4. Sebuah permintaan penggabungan dibuat, dan **hanya bisa menuju cabang `dev`**.
5. Penggabungan **hanya terjadi setelah Anda menekan tombol Setujui di Telegram**.

Aturan itu bukan kesepakatan lisan — sistem menolak sendiri bila dilanggar.
Percobaan menggabungkan tanpa persetujuan ditolak sebelum permintaan apa pun
dikirim ke GitHub, dan persetujuan terikat pada versi persis yang Anda lihat:
bila isinya berubah setelah disetujui, persetujuan harus diulang.

Seluruh rangkaian ini sudah **dijalankan sungguhan** pada 19 September 2026, dari
permintaan sampai penggabungan yang Anda setujui sendiri lewat Telegram.

---

## Yang selesai belakangan ini

**Seluruh kode asisten kini tersimpan di repositori.** Sebelumnya pekerjaan itu
hanya ada sebagai berkas di satu server: bila server disiapkan ulang, ia hilang,
dan tidak ada cara memastikan yang tayang sama dengan yang pernah diuji. Dua
permintaan penggabungan — masing-masing untuk aplikasi akreditasi dan academy —
disetujui dan digabungkan pada 19 September 2026, setelah seluruh pengujian
dijalankan lebih dulu dan isinya dibuktikan identik dengan yang diuji.

Dampaknya sederhana tapi besar: yang tayang sekarang bisa dibangun ulang kapan
saja, dan prosedur pembaruan rutin aman dijalankan kembali.

---

## Yang masih menunggu keputusan

| Hal | Kenapa penting |
|---|---|
| Penggantian tiga kata sandi lama | pernah melewati percakapan, sebaiknya diganti |
| Cadangan otomasi yang terenkripsi dan teruji | saat ini tersimpan tanpa enkripsi di server yang sama |
| Alur otomasi pertama | perangkatnya siap, menunggu prioritas |
| Model bahasa penuh di dalam aplikasi | sengaja ditunda; jalurnya sudah dirancang bila disetujui |

---

## Kesimpulan

Yang dibangun bukan chatbot yang pandai bicara, melainkan asisten yang **jujur
soal batas pengetahuannya**, memperbaiki diri dari pertanyaan nyata pengguna, dan
tidak diberi kemampuan untuk merusak apa pun. Kendali atas perubahan tetap berada
di tangan manusia, dan sistemlah yang memastikan hal itu — bukan sebaliknya.
