package com.mediadownloader.mobile.download

import android.content.ContentUris
import android.content.ContentValues
import android.content.Context
import android.media.MediaScannerConnection
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.webkit.MimeTypeMap
import androidx.annotation.RequiresApi
import com.mediadownloader.mobile.data.PublishedFile
import java.io.File
import java.io.FileInputStream
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/** Publishes private staging files without requesting broad storage access on Android 10+. */
internal class MediaStorePublisher(private val context: Context) {
    private val resolver = context.contentResolver

    fun publish(source: File, isCancelled: () -> Boolean): PublishedFile {
        require(source.isFile) { "Arquivo temporário inexistente: ${source.name}" }
        if (isCancelled()) throw DownloadCancelledException()
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            publishScoped(source, isCancelled)
        } else {
            publishLegacy(source, isCancelled)
        }
    }

    @RequiresApi(Build.VERSION_CODES.Q)
    private fun publishScoped(source: File, isCancelled: () -> Boolean): PublishedFile {
        val relativePath = "${Environment.DIRECTORY_DOWNLOADS}/$DOWNLOAD_DIRECTORY"
        val displayName = uniqueScopedName(safeDisplayName(source.name), relativePath)
        val mimeType = mimeTypeFor(displayName)
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, displayName)
            put(MediaStore.Downloads.MIME_TYPE, mimeType)
            put(MediaStore.Downloads.RELATIVE_PATH, relativePath)
            put(MediaStore.Downloads.IS_PENDING, 1)
        }
        val collection = MediaStore.Downloads.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        val uri = resolver.insert(collection, values)
            ?: throw IOException("O Android não criou o arquivo em Downloads")
        try {
            resolver.openOutputStream(uri, "w")?.use { output ->
                FileInputStream(source).use { input ->
                    copyCheckingCancellation(input, output, isCancelled)
                }
            } ?: throw IOException("Não foi possível abrir o destino em Downloads")
            val ready = ContentValues().apply { put(MediaStore.Downloads.IS_PENDING, 0) }
            resolver.update(uri, ready, null, null)
            return PublishedFile(uri.toString(), displayName, mimeType, source.length())
        } catch (error: Throwable) {
            resolver.delete(uri, null, null)
            throw error
        }
    }

    @Suppress("DEPRECATION")
    private fun publishLegacy(source: File, isCancelled: () -> Boolean): PublishedFile {
        val downloads = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
        val destinationDirectory = File(downloads, DOWNLOAD_DIRECTORY)
        if (!destinationDirectory.exists() && !destinationDirectory.mkdirs()) {
            throw IOException("Não foi possível criar ${destinationDirectory.absolutePath}")
        }
        val destination = uniqueLegacyFile(destinationDirectory, safeDisplayName(source.name))
        try {
            FileInputStream(source).use { input ->
                destination.outputStream().use { output ->
                    copyCheckingCancellation(input, output, isCancelled)
                }
            }
        } catch (error: Throwable) {
            destination.delete()
            throw error
        }

        val mimeType = mimeTypeFor(destination.name)
        val scannedUri = scanLegacyFile(destination, mimeType) ?: findLegacyMediaUri(destination)
        return PublishedFile(
            uri = (scannedUri ?: Uri.fromFile(destination)).toString(),
            displayName = destination.name,
            mimeType = mimeType,
            sizeBytes = destination.length(),
        )
    }

    private fun copyCheckingCancellation(
        input: java.io.InputStream,
        output: java.io.OutputStream,
        isCancelled: () -> Boolean,
    ) {
        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
        while (true) {
            if (isCancelled()) throw DownloadCancelledException()
            val count = input.read(buffer)
            if (count < 0) break
            output.write(buffer, 0, count)
        }
        output.flush()
    }

    @RequiresApi(Build.VERSION_CODES.Q)
    private fun uniqueScopedName(original: String, relativePath: String): String {
        val name = original.substringBeforeLast('.', original)
        val extension = original.substringAfterLast('.', "").let { if (it.isBlank()) "" else ".$it" }
        var candidate = original
        var suffix = 1
        while (scopedNameExists(candidate, relativePath)) {
            candidate = "$name ($suffix)$extension"
            suffix += 1
        }
        return candidate
    }

    @RequiresApi(Build.VERSION_CODES.Q)
    private fun scopedNameExists(name: String, relativePath: String): Boolean {
        val collection = MediaStore.Downloads.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        return resolver.query(
            collection,
            arrayOf(MediaStore.Downloads._ID),
            "${MediaStore.Downloads.DISPLAY_NAME} = ? AND ${MediaStore.Downloads.RELATIVE_PATH} = ?",
            arrayOf(name, relativePath),
            null,
        )?.use { it.moveToFirst() } == true
    }

    private fun uniqueLegacyFile(directory: File, original: String): File {
        var candidate = File(directory, original)
        val name = original.substringBeforeLast('.', original)
        val extension = original.substringAfterLast('.', "").let { if (it.isBlank()) "" else ".$it" }
        var suffix = 1
        while (candidate.exists()) {
            candidate = File(directory, "$name ($suffix)$extension")
            suffix += 1
        }
        return candidate
    }

    private fun scanLegacyFile(file: File, mimeType: String): Uri? {
        val result = AtomicReference<Uri?>()
        val latch = CountDownLatch(1)
        MediaScannerConnection.scanFile(
            context,
            arrayOf(file.absolutePath),
            arrayOf(mimeType),
        ) { _, uri ->
            result.set(uri)
            latch.countDown()
        }
        latch.await(SCAN_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        return result.get()
    }

    @Suppress("DEPRECATION")
    private fun findLegacyMediaUri(file: File): Uri? {
        val collection = MediaStore.Files.getContentUri("external")
        return resolver.query(
            collection,
            arrayOf(MediaStore.Files.FileColumns._ID),
            "${MediaStore.Files.FileColumns.DATA} = ?",
            arrayOf(file.absolutePath),
            null,
        )?.use { cursor ->
            if (!cursor.moveToFirst()) null
            else ContentUris.withAppendedId(collection, cursor.getLong(0))
        }
    }

    private fun safeDisplayName(raw: String): String {
        val cleaned = raw
            .replace(Regex("[\\u0000-\\u001F\\u007F/\\\\]"), "_")
            .trim()
            .trim('.')
        return cleaned.ifBlank { "download-${System.currentTimeMillis()}" }.take(MAX_FILE_NAME_LENGTH)
    }

    private fun mimeTypeFor(fileName: String): String {
        val extension = fileName.substringAfterLast('.', "").lowercase()
        return when (extension) {
            "mkv" -> "video/x-matroska"
            "m4a" -> "audio/mp4"
            "opus" -> "audio/opus"
            "flac" -> "audio/flac"
            "wav" -> "audio/wav"
            "srt" -> "application/x-subrip"
            "vtt" -> "text/vtt"
            else -> MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension)
                ?: "application/octet-stream"
        }
    }

    companion object {
        private const val DOWNLOAD_DIRECTORY = "MediaDownloader"
        private const val MAX_FILE_NAME_LENGTH = 220
        private const val SCAN_TIMEOUT_SECONDS = 8L
    }
}
