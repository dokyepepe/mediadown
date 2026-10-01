package com.mediadownloader.mobile.update

import android.content.Context
import com.yausername.youtubedl_android.YoutubeDL
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.util.zip.ZipFile

/**
 * Seeds the active yt-dlp runtime from the APK assets so a fresh install already
 * runs the modern yt-dlp shipped with this APK, instead of the 0.18.1-era bundle
 * that youtubedl-android carries inside its own `res/raw/ytdlp`.
 *
 * Callers must hold [YtDlpRuntimeGate]'s write lock (the engine's
 * `ensureInitialized()` and the update manager's `ensureInitializedLocked()` both
 * run under it). It never downgrades: the active binary is replaced only when it
 * is missing or older than the asset, so manual/automatic updates are never lost.
 */
internal object YtDlpBundledSeeder {

    private const val ASSET_BINARY = "ytdlp"
    private const val ASSET_VERSION = "ytdlp.version"
    private const val MARKER_FILE_NAME = ".bundled-version"

    private val versionPattern = Regex("""__version__\s*=\s*['"]([0-9.]+)['"]""")

    /** Best-effort bootstrap; a failure must never block the runtime startup. */
    fun stageIfNewer(context: Context) {
        runCatching { stageIfNewerOrThrow(context) }
    }

    private fun stageIfNewerOrThrow(context: Context) {
        val binary = activeBinary(context) ?: return
        val bundledVersion = context.assets.open(ASSET_VERSION).use { input ->
            input.readBytes().toString(Charsets.UTF_8).trim()
        }
        if (bundledVersion.isBlank()) return

        val marker = File(binary.parentFile, MARKER_FILE_NAME)
        if (marker.readTextOrNull() == bundledVersion && binary.isFile && binary.length() > 0L) {
            return
        }

        val installedVersion = installedVersionOf(binary)
        val shouldReplace = !binary.isFile || binary.length() <= 0L ||
            installedVersion == null ||
            YtDlpUpdatePolicy.compareVersions(installedVersion, bundledVersion)?.let { it < 0 } == true

        if (!shouldReplace) {
            marker.writeTextSilent(bundledVersion)
            return
        }

        binary.parentFile?.let { parent ->
            if (!parent.exists() && !parent.mkdirs()) return
        }
        val temporary = File(binary.parentFile, "yt-dlp.bundled.pending")
        context.assets.open(ASSET_BINARY).use { input ->
            FileOutputStream(temporary).use { output ->
                input.copyTo(output)
                output.fd.sync()
            }
        }
        try {
            YtDlpArtifactIntegrity.copyVerified(temporary, binary)
        } finally {
            temporary.delete()
        }
        marker.writeTextSilent(bundledVersion)
    }

    private fun installedVersionOf(binary: File): String? {
        if (!binary.isFile || binary.length() <= 0L) return null
        return try {
            ZipFile(binary).use { zip ->
                val entry = zip.getEntry("yt_dlp/version.py") ?: return null
                val text = zip.getInputStream(entry).readBytes().toString(Charsets.UTF_8)
                versionPattern.find(text)?.groupValues?.get(1)
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun activeBinary(context: Context): File? {
        val runtimeRoot = File(context.noBackupFilesDir, YoutubeDL.baseName)
        return File(File(runtimeRoot, YoutubeDL.ytdlpDirName), YoutubeDL.ytdlpBin)
    }

    private fun File.readTextOrNull(): String? = runCatching { readText() }.getOrNull()

    private fun File.writeTextSilent(text: String) {
        runCatching { writeText(text) }
    }
}