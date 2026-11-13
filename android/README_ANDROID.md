# Panduan Kompilasi APK Android (Standalone / Tanpa Server)

Proyek ini telah dikonfigurasi dengan arsitektur **Chaquopy + Android WebView**.
Aplikasi ini berjalan **100% mandiri di dalam ponsel Android** tanpa membutuhkan server VPS, cloud, ataupun laptop.

---

## 🛠️ Persyaratan

1. **Android Studio** (Koala, Hedgehog, Iguana, atau versi terbaru).
2. **JDK 17** (Bawaan Android Studio).
3. **Android SDK** API 24 (Android 7.0) hingga API 34 (Android 14).

---

## 🚀 Langkah Build Menjadi APK

### Langkah 1: Buka Proyek di Android Studio
1. Buka aplikasi **Android Studio**.
2. Pilih menu **File** > **Open...**
3. Arahkan ke folder:
   ```
   f:\ytdownloader\android
   ```
   *(Pilih folder `android`, bukan root repository).*
4. Tunggu Gradle melakukan sync dependencies pertama kali (Chaquopy akan mengunduh runtime CPython dan library Python yang didefinisikan di `app/build.gradle`).

---

### Langkah 2: Build APK Debug (Untuk Dicoba Langsung di HP)
1. Sambungkan HP Android dengan kabel USB (aktifkan *USB Debugging*), **atau** cukup buat file APK-nya saja:
2. Di Android Studio, klik menu:
   ```
   Build > Build Bundle(s) / APK(s) > Build APK(s)
   ```
3. Tunggu hingga proses build selesai.
4. Klik tautan **locate** pada notifikasi yang muncul di kanan bawah. File APK Anda akan berada di:
   ```
   android/app/build/outputs/apk/debug/app-debug.apk
   ```
5. Kirim file `app-debug.apk` tersebut ke HP Anda lewat WhatsApp, Telegram, atau kabel data, lalu install.

---

### Langkah 3: Build APK Release (Siap Distribusi)
1. Di Android Studio, klik menu **Build** > **Generate Signed Bundle / APK...**
2. Pilih **APK** > Next.
3. Buat KeyStore baru (jika belum punya) atau gunakan key yang ada.
4. Pilih varian `release` dan centang signature V1/V2.
5. Klik **Finish**. File APK final siap disebarkan.

---

## 🌟 Fitur Khusus di Versi Android

1. **Mendukung Tombol "Share / Bagikan" YouTube**:
   - Saat Anda menonton video di aplikasi YouTube resmi di HP, klik tombol **Bagikan (Share)** > pilih **YTDownloader**.
   - URL video akan otomatis terisi dan tombol analisis otomatis diklik.
2. **Tersimpan ke Folder Publik HP**:
   - Hasil unduhan langsung tersimpan di `/storage/emulated/0/Download/YTDownloader/` dan otomatis terdeteksi oleh pemutar video/musik bawaan HP.
3. **Download Manager Native**:
   - Status unduhan browser terintegrasi dengan bar notifikasi Android.
