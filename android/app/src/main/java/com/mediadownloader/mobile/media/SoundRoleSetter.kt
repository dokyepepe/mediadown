package com.mediadownloader.mobile.media

import android.content.ContentValues
import android.content.Context
import android.media.MediaScannerConnection
import android.media.RingtoneManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.webkit.MimeTypeMap
import androidx.annotation.RequiresApi
import androidx.core.net.toUri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference

/** Where a finished audio file is offered to the system sound picker. */
enum class SoundRole(val labelRes: Int) {
    RINGTONE(com.mediadownloader.mobile.R.string.sound_role_ringtone),
    NOTIFICATION(com.mediadownloader.mobile.R.string.sound_role_notification),
    ALARM(com.mediadownloader.mobile.R.string.sound_role_alarm),
}

/**
 * Makes a finished download available as ringtone, notification or alarm sound.
 *
 * A copy is always required: MediaStore rows cannot change collection and the system
 * picker only lists rows that live inside the audio collection, while downloads are
 * published into Downloads or into a user-picked SAF folder.
 */
class SoundRoleSetter(private val context: Context) {

    suspend fun apply(sourceUri: String, displayName: String, role: SoundRole): Uri =
        withContext(Dispatchers.IO) {
            val source = sourceUri.toUri()
            val name = safeDisplayName(displayName)
            val audioUri = findAudioRow(name) ?: importIntoAudioCollection(source, name)
            flagRow(audioUri, role)
            val ringtoneType = when (role) {
                SoundRole.RINGTONE -> RingtoneManager.TYPE_RINGTONE
                SoundRole.NOTIFICATION -> RingtoneManager.TYPE_NOTIFICATION
                SoundRole.ALARM -> RingtoneManager.TYPE_ALARM
            }
            applyAsDefault(audioUri, ringtoneType)
            if (RingtoneManager.getActualDefaultRingtoneUri(context, ringtoneType) != audioUri) {
                throw IOException("O Android recusou a troca do som do sistema")
            }
            audioUri
        }

    /**
     * API 29 renamed the call to (Context, int type, Uri) and dropped the old
     * (Context, Uri, int) overload from the SDK, so API 26-28 is reached reflectively.
     */
    private fun applyAsDefault(audioUri: Uri, type: Int) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            RingtoneManager.setActualDefaultRingtoneUri(context, type, audioUri)
            return
        }
        RingtoneManager::class.java
            .getMethod(
                "setActualDefaultRingtoneUri",
                Context::class.java,
                Uri::class.java,
                Int::class.javaPrimitiveType,
            )
            .invoke(null, context, audioUri, type)
    }

    private fun flagRow(audioUri: Uri, role: SoundRole) {
        val values = ContentValues().apply {
            put(MediaStore.Audio.Media.IS_RINGTONE, if (role == SoundRole.RINGTONE) 1 else 0)
            put(MediaStore.Audio.Media.IS_NOTIFICATION, if (role == SoundRole.NOTIFICATION) 1 else 0)
            put(MediaStore.Audio.Media.IS_ALARM, if (role == SoundRole.ALARM) 1 else 0)
        }
        context.contentResolver.update(audioUri, values, null, null)
    }

    private fun findAudioRow(displayName: String): Uri? {
        val collection = audioCollection()
        val (selection, args) = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            "${MediaStore.Audio.Media.DISPLAY_NAME} = ? AND " +
                "${MediaStore.Audio.Media.RELATIVE_PATH} = ?" to
                arrayOf(displayName, "$MUSIC_DIRECTORY/")
        } else {
            @Suppress("DEPRECATION")
            "${MediaStore.Audio.Media.DATA} LIKE ?" to arrayOf("$legacyDirectory$FILE_NAME_PATTERN")
        }
        return context.contentResolver.query(
            collection,
            arrayOf(MediaStore.Audio.Media._ID),
            selection,
            args,
            null,
        )?.use { cursor ->
            if (!cursor.moveToFirst()) return null
            android.content.ContentUris.withAppendedId(collection, cursor.getLong(0))
        }
    }

    private fun importIntoAudioCollection(source: Uri, displayName: String): Uri =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            importScoped(source, displayName)
        } else {
            importLegacy(source, displayName)
        }

    @RequiresApi(Build.VERSION_CODES.Q)
    private fun importScoped(source: Uri, displayName: String): Uri {
        val values = ContentValues().apply {
            put(MediaStore.Audio.Media.DISPLAY_NAME, displayName)
            put(MediaStore.Audio.Media.MIME_TYPE, audioMimeType(displayName))
            put(MediaStore.Audio.Media.RELATIVE_PATH, "$MUSIC_DIRECTORY/")
            put(MediaStore.Audio.Media.IS_MUSIC, 0)
            put(MediaStore.Audio.Media.IS_PENDING, 1)
        }
        val uri = context.contentResolver.insert(audioCollection(), values)
            ?: throw IOException("O Android não criou o arquivo em Música")
        try {
            copyTo(source, uri)
            val ready = ContentValues().apply { put(MediaStore.Audio.Media.IS_PENDING, 0) }
            context.contentResolver.update(uri, ready, null, null)
            return uri
        } catch (error: Throwable) {
            runCatching { context.contentResolver.delete(uri, null, null) }
            throw error
        }
    }

    @Suppress("DEPRECATION")
    private fun importLegacy(source: Uri, displayName: String): Uri {
        val directory = File(
            Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MUSIC),
            LEGACY_DIRECTORY,
        )
        if (!directory.exists() && !directory.mkdirs()) {
            throw IOException("Não foi possível criar ${directory.absolutePath}")
        }
        val target = uniqueFile(directory, displayName)
        try {
            context.contentResolver.openInputStream(source)?.use { input ->
                target.outputStream().use { output -> input.copyTo(output) }
            } ?: throw IOException("Não foi possível ler o arquivo de origem")
        } catch (error: Throwable) {
            target.delete()
            throw error
        }
        val scanned = AtomicReference<Uri?>()
        val latch = CountDownLatch(1)
        @Suppress("DEPRECATION")
        MediaScannerConnection.scanFile(context, arrayOf(target.absolutePath), null) { _, uri ->
            scanned.set(uri)
            latch.countDown()
        }
        latch.await(SCAN_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        return scanned.get() ?: Uri.fromFile(target)
    }

    private fun copyTo(source: Uri, target: Uri) {
        context.contentResolver.openInputStream(source)?.use { input ->
            context.contentResolver.openOutputStream(target, "w")?.use { output ->
                input.copyTo(output)
            } ?: throw IOException("Não foi possível gravar o arquivo em Música")
        } ?: throw IOException("Não foi possível ler o arquivo de origem")
    }

    private fun audioCollection(): Uri =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            MediaStore.Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
        } else {
            @Suppress("DEPRECATION")
            MediaStore.Audio.Media.EXTERNAL_CONTENT_URI
        }

    private fun uniqueFile(directory: File, original: String): File {
        val name = original.substringBeforeLast('.', original)
        val extension = original.substringAfterLast('.', "").let { if (it.isEmpty()) "" else ".$it" }
        var candidate = File(directory, original)
        var suffix = 1
        while (candidate.exists()) {
            candidate = File(directory, "$name ($suffix)$extension")
            suffix += 1
        }
        return candidate
    }

    private fun safeDisplayName(raw: String): String {
        val cleaned = raw.replace(Regex("[\\u0000-\\u001F\\u007F/\\\\]"), "_").trim().trim('.')
        return cleaned.ifBlank { "som-${System.currentTimeMillis()}" }.take(MAX_FILE_NAME_LENGTH)
    }

    private fun audioMimeType(fileName: String): String {
        val extension = fileName.substringAfterLast('.', "").lowercase()
        return MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension)
            ?.takeIf { it.startsWith("audio/") }
            ?: "audio/mpeg"
    }

    private companion object {
        const val MUSIC_DIRECTORY = "Music/MediaDownloader"
        const val LEGACY_DIRECTORY = "MediaDownloader"
        const val FILE_NAME_PATTERN = "%"
        const val MAX_FILE_NAME_LENGTH = 220
        const val SCAN_TIMEOUT_SECONDS = 8L

        @Suppress("DEPRECATION")
        val legacyDirectory: String =
            "${Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MUSIC).absolutePath}/$LEGACY_DIRECTORY/"
    }
}
