package com.mediadownloader.mobile.ui

import android.content.Context
import android.graphics.Bitmap
import androidx.core.content.FileProvider
import com.mediadownloader.mobile.BuildConfig
import com.mediadownloader.mobile.data.PublishedFile
import com.mediadownloader.mobile.data.StorageCategory
import com.mediadownloader.mobile.download.MediaStorePublisher
import java.io.File
import java.io.IOException

internal class QrCodeFileService(private val context: Context) {
    private val publisher = MediaStorePublisher(context)

    fun createShareable(value: String): QrCodeFile {
        val file = File(context.cacheDir, "$SHARE_DIRECTORY/$FILE_NAME")
        writeQrCode(value, file)
        val uri = FileProvider.getUriForFile(
            context,
            "${BuildConfig.APPLICATION_ID}.files",
            file,
        )
        return QrCodeFile(uri = uri.toString(), displayName = file.name)
    }

    fun save(value: String): PublishedFile {
        val stagingFile = File(context.cacheDir, "$STAGING_DIRECTORY/$FILE_NAME")
        writeQrCode(value, stagingFile)
        return publisher.publish(
            source = stagingFile,
            category = StorageCategory.SITE_FILES,
            isCancelled = { false },
        )
    }

    @Synchronized
    private fun writeQrCode(value: String, destination: File) {
        val parent = destination.parentFile
            ?: throw IOException("Destino inválido para o QR Code")
        if (!parent.exists() && !parent.mkdirs()) {
            throw IOException("Não foi possível preparar o arquivo do QR Code")
        }
        val temporary = File(parent, "${destination.name}.tmp")
        try {
            temporary.outputStream().buffered().use { output ->
                if (!createQrCodeBitmap(value).compress(Bitmap.CompressFormat.PNG, 100, output)) {
                    throw IOException("Não foi possível codificar o QR Code como PNG")
                }
            }
            if (destination.exists() && !destination.delete()) {
                throw IOException("Não foi possível substituir o QR Code anterior")
            }
            if (!temporary.renameTo(destination)) {
                temporary.copyTo(destination, overwrite = true)
                temporary.delete()
            }
        } catch (error: Throwable) {
            temporary.delete()
            throw error
        }
    }

    companion object {
        private const val SHARE_DIRECTORY = "shared"
        private const val STAGING_DIRECTORY = "qr-code-staging"
        private const val FILE_NAME = "MediaDownloader-QRCode.png"
    }
}

internal data class QrCodeFile(
    val uri: String,
    val displayName: String,
)
