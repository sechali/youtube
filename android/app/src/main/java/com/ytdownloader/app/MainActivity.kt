package com.ytdownloader.app

import android.annotation.SuppressLint
import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.Settings
import android.util.Log
import android.view.View
import android.webkit.*
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.ytdownloader.app.databinding.ActivityMainBinding
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val localServerUrl = "http://127.0.0.1:8000"
    private var sharedYoutubeUrl: String? = null
    private var ffmpegExecutablePath: String? = null

    private val storagePermissionLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) {
        // Refresh check after returning from settings
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // 0. Minta Izin Penyimpanan Lengkap agar bisa menulis langsung ke folder publik Download HP
        requestStoragePermissionIfNeeded()

        // 1. Ekstrak binary FFmpeg dari assets ke private internal filesDir agar bisa dieksekusi (chmod +x)
        prepareFfmpegBinary()

        // 2. Tangkap URL jika aplikasi dibuka via tombol "Share / Bagikan" dari YouTube
        handleIncomingShareIntent(intent)

        setupWebView()
        startPythonServerAsync()
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIncomingShareIntent(intent)
        sharedYoutubeUrl?.let { url ->
            injectSharedUrlIntoWeb(url)
        }
    }

    private fun requestStoragePermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            if (!Environment.isExternalStorageManager()) {
                try {
                    val intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION).apply {
                        data = Uri.parse("package:$packageName")
                    }
                    storagePermissionLauncher.launch(intent)
                } catch (_: Exception) {
                    val intent = Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION)
                    storagePermissionLauncher.launch(intent)
                }
            }
        } else {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(
                    android.Manifest.permission.READ_EXTERNAL_STORAGE,
                    android.Manifest.permission.WRITE_EXTERNAL_STORAGE
                ),
                1001
            )
        }
    }

    private fun prepareFfmpegBinary() {
        try {
            // 1. Cek apakah ada di nativeLibraryDir (diextract otomatis oleh Android dari jniLibs)
            val nativeLibDir = applicationInfo.nativeLibraryDir
            val nativeFfmpeg = File(nativeLibDir, "libffmpeg.so")
            if (nativeFfmpeg.exists() && nativeFfmpeg.canExecute()) {
                ffmpegExecutablePath = nativeFfmpeg.absolutePath
                Log.i("YTDownloader", "FFmpeg dari nativeLibraryDir siap: $ffmpegExecutablePath")
                return
            }

            // 2. Fallback: Ekstrak dari assets ke internal filesDir/bin/ffmpeg
            val binDir = File(filesDir, "bin")
            if (!binDir.exists()) binDir.mkdirs()

            val ffmpegFile = File(binDir, "ffmpeg")

            if (!ffmpegFile.exists() || ffmpegFile.length() < 1000000L) {
                assets.open("ffmpeg-arm64").use { input ->
                    FileOutputStream(ffmpegFile).use { output ->
                        input.copyTo(output)
                    }
                }
            }

            ffmpegFile.setReadable(true, false)
            ffmpegFile.setExecutable(true, false)

            ffmpegExecutablePath = ffmpegFile.absolutePath
            Log.i("YTDownloader", "FFmpeg Android siap di: $ffmpegExecutablePath (executable: ${ffmpegFile.canExecute()})")
        } catch (e: Exception) {
            Log.e("YTDownloader", "Gagal menyiapkan FFmpeg binary: ${e.message}", e)
        }
    }

    private fun handleIncomingShareIntent(intent: Intent?) {
        if (intent?.action == Intent.ACTION_SEND && intent.type == "text/plain") {
            val text = intent.getStringExtra(Intent.EXTRA_TEXT)
            if (!text.isNullOrBlank()) {
                sharedYoutubeUrl = extractUrl(text)
            }
        }
    }

    private fun extractUrl(text: String): String {
        val parts = text.split("\\s+".toRegex())
        for (part in parts) {
            if (part.startsWith("http://") || part.startsWith("https://")) {
                return part
            }
        }
        return text.trim()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        val webView = binding.webView
        val settings = webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.databaseEnabled = true
        settings.allowFileAccess = true
        settings.useWideViewPort = true
        settings.loadWithOverviewMode = true

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                binding.loadingLayout.visibility = View.GONE
                binding.webView.visibility = View.VISIBLE

                sharedYoutubeUrl?.let { ytUrl ->
                    injectSharedUrlIntoWeb(ytUrl)
                }
            }

            override fun onReceivedError(
                view: WebView?,
                errorCode: Int,
                description: String?,
                failingUrl: String?
            ) {
                // Abaikan error saat polling server lokal yang masih boot
            }
        }

        // Listener jika user mengunduh file hasil konversi dari browser webview
        webView.setDownloadListener { url, userAgent, contentDisposition, mimetype, _ ->
            try {
                val request = DownloadManager.Request(Uri.parse(url))
                val filename = URLUtil.guessFileName(url, contentDisposition, mimetype)
                request.setMimeType(mimetype)
                request.addRequestHeader("User-Agent", userAgent)
                request.setDescription("Mengunduh $filename...")
                request.setTitle(filename)
                request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, filename)

                val dm = getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
                dm.enqueue(request)
                Toast.makeText(this, "Mengunduh ke folder Download...", Toast.LENGTH_SHORT).show()
            } catch (e: Exception) {
                Toast.makeText(this, "Gagal mengunduh: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun injectSharedUrlIntoWeb(url: String) {
        val js = """
            (function() {
                var input = document.getElementById('urlInput');
                if (input) {
                    input.value = '$url';
                    var inspectBtn = document.getElementById('inspectBtn');
                    if (inspectBtn) inspectBtn.click();
                }
            })();
        """.trimIndent()
        binding.webView.evaluateJavascript(js, null)
    }

    private fun startPythonServerAsync() {
        binding.loadingLayout.visibility = View.VISIBLE
        binding.webView.visibility = View.GONE

        thread(name = "PythonFastAPIServerThread") {
            try {
                // 1. Inisialisasi runtime Chaquopy Python
                if (!Python.isStarted()) {
                    Python.start(AndroidPlatform(applicationContext))
                }
                val py = Python.getInstance()

                // 2. Tentukan direktori penyimpanan:
                // Gunakan folder publik Download HP (/storage/emulated/0/Download/YTDownloader)
                val publicDownloadDir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "YTDownloader").apply {
                    mkdirs()
                }.absolutePath
                val internalFilesDir = applicationContext.filesDir.absolutePath
                val ffmpegPath = ffmpegExecutablePath ?: ""

                val launcherModule = py.getModule("android_launcher")
                launcherModule.callAttr("start_server", internalFilesDir, publicDownloadDir, ffmpegPath)

            } catch (e: Exception) {
                e.printStackTrace()
            }
        }

        // Polling thread untuk memeriksa server lokal
        thread(name = "ServerHealthCheckThread") {
            var ready = false
            var attempts = 0
            while (!ready && attempts < 40) {
                Thread.sleep(500)
                attempts++
                try {
                    val connection = URL(localServerUrl).openConnection() as HttpURLConnection
                    connection.connectTimeout = 400
                    connection.readTimeout = 400
                    connection.requestMethod = "GET"
                    val code = connection.responseCode
                    if (code in 200..399) {
                        ready = true
                    }
                    connection.disconnect()
                } catch (_: Exception) {}
            }

            runOnUiThread {
                if (ready) {
                    binding.webView.loadUrl(localServerUrl)
                } else {
                    binding.loadingText.text = "Gagal menyalakan mesin lokal. Coba restart aplikasi."
                }
            }
        }
    }

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (binding.webView.canGoBack()) {
            binding.webView.goBack()
        } else {
            super.onBackPressed()
        }
    }
}
