# Ringkasan Eksekutif — Sprint 2 & Sprint 3

**Untuk:** Manajemen dan Direksi · **Per:** 21 September 2026
**Sumber:** NEXONE (data langsung, dibaca 21 Sep) + Slack `#daily-updates` & `#developments`

---

## Satu halaman untuk dibaca lebih dulu

**Sprint 2 ditutup dengan 80% pekerjaan selesai. Sprint 3 berjalan di 70% dengan empat hari tersisa.** Di antara keduanya terjadi perubahan arah yang paling penting untuk diketahui direksi: tim berhenti sekadar memperbaiki OneAlpha versi lama dan mulai membangun **OneAlpha v2** sebagai superapp.

| | Sprint 2 | Sprint 3 |
|---|---|---|
| Periode | 31 Ags – 11 Sep (selesai) | 15 – 25 Sep (berjalan) |
| Tugas selesai | **28 dari 35** | **12 dari 17** |
| Poin selesai | **101 dari 123** | **33 dari 64** |
| Progres | **80%** | **70%** |
| Produk tersentuh | 4 | **8** |
| Tugas lewat tenggat | 5 | 2 |

Angka di atas diambil langsung dari NEXONE, bukan dari laporan manual.

---

## Sprint 2 — konsolidasi: menstabilkan yang sudah berjalan

Sprint 2 adalah sprint perapihan, dan sebagian besar bebannya ada di **Audit Platform**. Dari 35 tugas, 21 di antaranya menyangkut platform audit — terutama sertifikat, penjadwalan audit, dan filter data.

**Yang selesai dan bisa dirasakan pengguna:**

- **Sertifikat audit diperbaiki menyeluruh** — nomor sertifikat, alamat klien yang tidak muncul, sertifikat ISCC, dan paragraf sertifikat. Sembilan tugas terpisah, semuanya lolos UAT.
- **Proses audit menjadi lebih aman** — validasi kasus Stage 2 yang tidak bisa dijadwalkan saat Stage 1 belum tuntas, perbaikan penyimpanan tanggal audit, dan surat konfirmasi audit (FSCP-03) masuk ke penjadwalan.
- **Dashboard monitoring audit klien** tersedia untuk memantau posisi setiap klien.
- **CRM distabilkan** — dua perbaikan besar: penggantian komponen pemilihan data di seluruh CRM dan perbaikan bug pembuatan data di detail perusahaan.
- **Fondasi kerja tim dibangun** — lingkungan pengembangan NexFinance dan NexOne disiapkan, story point diaktifkan di NEXONE, dan **integrasi dua arah Slack–NEXONE–Support** berjalan sehingga tiket dan tugas tidak lagi dicatat dua kali.

**Yang tidak selesai — dan ini polanya penting:** tujuh tugas tersisa, dan **ketujuhnya ada di Audit Platform**, mayoritas di seputar sertifikat (paragraf sertifikat single/multi site, tautan sertifikat, tampilan sertifikat) ditambah satu pekerjaan besar sinkronisasi migrasi data dari Audit-Q v2 (13 poin). Tidak ada sisa pekerjaan di CRM, NexOne, maupun NexFinance.

> **Implikasi manajerial:** sisa Sprint 2 bukan tersebar — ia terkonsentrasi pada satu fungsi bisnis, yaitu penerbitan sertifikat. Itu kabar baik untuk pengelolaan risiko: satu area, satu fokus penyelesaian.

---

## Sprint 3 — pergeseran arah: dari memperbaiki menjadi membangun

Sprint 3 memiliki wajah yang sangat berbeda. Jumlah tugasnya separuh Sprint 2, tetapi menyentuh **delapan produk** dan hampir seluruhnya bersifat fondasi, bukan perbaikan.

Tiga sasaran sprint ini:

1. **Riset EverGauzy** sebagai rujukan arsitektur untuk membangun ulang OneAlpha (CRM, Project Management, HCM/HRIS, modul enterprise).
2. **Menyiapkan repositori OneAlpha-v2** untuk delapan modul: KMS, HCM, Project Management, Academy, Accreditation, OneGRC, Asset Management, dan Service Desk.
3. **Menyiapkan kebutuhan DevOps** — repositori, environment, CI/CD, baseline arsitektur, dan standar penulisan kode.

**Yang sudah tercapai:** repositori dan prototipe untuk Academy, Accreditation, Service Desk, KMS, HCM, dan Superapp sudah berdiri dan ter-deploy. Integrasi Slack–NEXONE–Support dituntaskan. Lima tiket dukungan pelanggan dari Audit Q v2 diselesaikan di sela pekerjaan fondasi — empat di antaranya berprioritas mendesak.

**Yang masih terbuka (5 tugas, 31 poin):**

| Pekerjaan | Produk | Status | Penanggung jawab |
|---|---|---|---|
| Development mengikuti prototipe (13 poin) | KMS | sedang dikerjakan | Diky |
| Setup CI/CD | KMS | belum mulai | Diky, Rafly |
| Setup CI/CD | Superapp | menuju produksi | Rafif, Rafly |
| Setup kebutuhan DevOps OneAlpha-v2 | Superapp | sedang dikerjakan | Rafly |
| Riset & setup EverGauzy | Superapp | menunggu review | Imam, Rafly |

> **Perhatian:** 31 dari 64 poin — hampir separuh beban sprint — masih terbuka dengan **empat hari tersisa**, dan sebagian besarnya adalah pekerjaan DevOps yang saling bergantung. Ini risiko jadwal yang nyata, bukan sekadar pekerjaan yang belum sempat disentuh.

---

## Tim dan distribusi beban

Lima orang tercatat mengerjakan sprint ini:

| Nama | Peran | Beban |
|---|---|---|
| M Imam Nurokhi | Tech Lead | Integrasi, arsitektur, fondasi repositori |
| Muhammad Rafif Fadhil Naufal | Fullstack Developer | Audit Platform (UAT), CRM, dukungan pelanggan |
| Diky Wahyudi | IT Magang | Modul Audit, KMS, automation testing |
| Mochammad Rafly Putra Aprijanto | IT Support | DevOps, CI/CD, environment |
| Harmanto | Bisnis/QA | Pelaporan isu dari sisi pengguna |

**Konsentrasi beban** ada pada Rafif dan Imam di Sprint 2, lalu bergeser ke Rafly dan Diky di Sprint 3 seiring perpindahan fokus ke DevOps. Seorang magang memegang pekerjaan 13 poin di jalur kritis KMS — layak menjadi perhatian pendampingan.

---

## Temuan tata kelola yang perlu keputusan

**Kanal `#daily-updates` di Slack berhenti sejak 20 Agustus 2026.** Selama Sprint 2 dan Sprint 3 berjalan, tidak ada satu pun laporan harian manusia di kanal itu. Yang masih aktif hanyalah `#developments`, dan isinya otomatis dari bot GitHub serta bot NEXONE.

Artinya pelaporan harian yang disepakati pada 11 Agustus — stand-up pembuka 09.00 dan penutup 16.45 — tidak lagi meninggalkan jejak tertulis. Pekerjaannya tetap berjalan (terbukti dari NEXONE dan GitHub), tetapi **jejak naratifnya hilang**: manajemen kehilangan konteks "mengapa", dan hanya melihat "apa".

Dua pilihan yang bisa diputuskan direksi:

1. **Hidupkan kembali laporan harian tertulis** di Slack, dengan pengingat otomatis yang sudah tersedia.
2. **Akui NEXONE sebagai satu-satunya sumber kebenaran** dan hentikan ekspektasi laporan harian di Slack, sehingga tidak ada dua sistem yang setengah terisi.

Yang tidak disarankan adalah membiarkan keadaan sekarang, karena ia menciptakan ilusi bahwa pelaporan sedang berjalan.

---

## Rekomendasi

1. **Tutup sisa Sprint 2 sebagai satu paket "Sertifikat".** Ketujuh tugas ada di satu area; menyelesaikannya sekaligus lebih murah daripada menyeretnya sprint demi sprint.
2. **Tinjau ulang cakupan Sprint 3 sekarang, bukan tanggal 25.** Dengan 48% poin masih terbuka dan pekerjaan DevOps yang saling bergantung, memilih dua hal yang wajib tuntas lebih baik daripada mengejar lima hal sekaligus.
3. **Putuskan status pelaporan harian** (lihat temuan tata kelola).
4. **Dampingi jalur kritis KMS**, yang saat ini bertumpu pada satu magang untuk pekerjaan 13 poin.

---

## Catatan metode

Seluruh angka dalam dokumen ini dibaca langsung dari NEXONE pada 21 September 2026 melalui antarmuka aplikasi, bukan dari rekap manual. Data Slack diambil dari kanal `#daily-updates` dan `#developments`. Tidak ada angka yang diperkirakan; bila sebuah data tidak tersedia, dokumen ini menyebutkannya.
