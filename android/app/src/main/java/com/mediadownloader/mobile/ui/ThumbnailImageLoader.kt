package com.mediadownloader.mobile.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.LruCache
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

internal object ThumbnailImageLoader {
    private const val CONNECT_TIMEOUT_MS = 12_000
    private const val READ_TIMEOUT_MS = 18_000
    private const val MAX_REDIRECTS = 5
    private const val MAX_DOWNLOAD_BYTES = 12 * 1024 * 1024
    private const val MAX_BITMAP_EDGE = 1_920
    private const val CACHE_BYTES = 16 * 1024 * 1024
    private const val USER_AGENT =
        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 " +
            "(KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36"

    private val cache = object : LruCache<String, Bitmap>(CACHE_BYTES) {
        override fun sizeOf(key: String, value: Bitmap): Int = value.allocationByteCount
    }

    suspend fun load(rawUrl: String?, referer: String?): ImageBitmap? = withContext(Dispatchers.IO) {
        val url = rawUrl?.trim()?.takeIf(String::isNotBlank) ?: return@withContext null
        val cacheKey = "$url\n${referer.orEmpty()}"
        cache.get(cacheKey)?.let { return@withContext it.asImageBitmap() }

        val refererAttempts = if (isHttpUrl(referer)) {
            listOf<String?>(referer, null)
        } else {
            listOf<String?>(null)
        }
        val bitmap = refererAttempts.firstNotNullOfOrNull { requestReferer ->
            runCatching { download(url, requestReferer) }.getOrNull()
        } ?: return@withContext null
        cache.put(cacheKey, bitmap)
        bitmap.asImageBitmap()
    }

    internal fun requestHeaders(referer: String?): Map<String, String> = buildMap {
        put("User-Agent", USER_AGENT)
        put("Accept", "image/avif,image/webp,image/apng,image/*,*/*;q=0.8")
        put("Accept-Language", "pt-BR,pt;q=0.9,en;q=0.7")
        if (isHttpUrl(referer)) put("Referer", referer!!.trim())
    }

    private fun download(rawUrl: String, referer: String?): Bitmap {
        var currentUrl = URL(rawUrl)
        require(currentUrl.protocol.equals("https", true) || currentUrl.protocol.equals("http", true))
        repeat(MAX_REDIRECTS + 1) { redirectCount ->
            val connection = (currentUrl.openConnection() as HttpURLConnection).apply {
                instanceFollowRedirects = false
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                useCaches = true
                requestHeaders(referer).forEach(::setRequestProperty)
            }
            try {
                val status = connection.responseCode
                if (status in 300..399) {
                    if (redirectCount == MAX_REDIRECTS) throw IOException("Redirecionamentos demais")
                    val location = connection.getHeaderField("Location")
                        ?: throw IOException("Redirecionamento sem destino")
                    currentUrl = URL(currentUrl, location).also {
                        require(it.protocol.equals("https", true) || it.protocol.equals("http", true))
                    }
                    return@repeat
                }
                if (status !in 200..299) {
                    connection.errorStream?.close()
                    throw IOException("HTTP $status")
                }
                val declaredSize = connection.contentLengthLong
                if (declaredSize > MAX_DOWNLOAD_BYTES) throw IOException("Imagem muito grande")
                val bytes = connection.inputStream.use(::readLimited)
                return decode(bytes) ?: throw IOException("Formato de imagem incompatível")
            } finally {
                connection.disconnect()
            }
        }
        throw IOException("Não foi possível abrir a imagem")
    }

    private fun readLimited(input: java.io.InputStream): ByteArray {
        val output = ByteArrayOutputStream()
        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
        var total = 0
        while (true) {
            val count = input.read(buffer)
            if (count < 0) break
            total += count
            if (total > MAX_DOWNLOAD_BYTES) throw IOException("Imagem muito grande")
            output.write(buffer, 0, count)
        }
        return output.toByteArray()
    }

    private fun decode(bytes: ByteArray): Bitmap? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null
        var sampleSize = 1
        while (bounds.outWidth / sampleSize > MAX_BITMAP_EDGE ||
            bounds.outHeight / sampleSize > MAX_BITMAP_EDGE
        ) {
            sampleSize *= 2
        }
        return BitmapFactory.decodeByteArray(
            bytes,
            0,
            bytes.size,
            BitmapFactory.Options().apply { inSampleSize = sampleSize },
        )
    }

    private fun isHttpUrl(value: String?): Boolean = runCatching {
        val protocol = URL(value?.trim()).protocol
        protocol.equals("https", true) || protocol.equals("http", true)
    }.getOrDefault(false)
}
