package com.mediadownloader.mobile.site

import android.content.Context
import com.mediadownloader.mobile.BuildConfig
import com.mediadownloader.mobile.data.PublishedFile
import com.mediadownloader.mobile.data.StorageCategory
import com.mediadownloader.mobile.download.DownloadCancelledException
import com.mediadownloader.mobile.download.MediaStorePublisher
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.net.URLDecoder
import java.nio.charset.Charset
import java.util.UUID

/** Network/storage adapter for site files; it never calls yt-dlp or FFmpeg. */
class AndroidSiteFileService(context: Context) {
    private val appContext = context.applicationContext
    private val publisher = MediaStorePublisher(appContext)

    suspend fun discover(
        url: String,
        includePdfs: Boolean,
        includeImages: Boolean,
    ): SiteScanResult = withContext(Dispatchers.IO) {
        validateWebUrl(url)
        if (!includePdfs && !includeImages) {
            throw IOException("Selecione PDFs, imagens ou ambos antes de analisar.")
        }
        val connection = open(url, "text/html,application/pdf,image/*;q=0.9,*/*;q=0.2")
        try {
            val finalUrl = connection.url.toString()
            val contentType = contentType(connection)
            val directKind = kindFromResponse(finalUrl, contentType)
            if (directKind != null) {
                val allowed = directKind == SiteFileKind.PDF && includePdfs ||
                    directKind == SiteFileKind.IMAGE && includeImages
                val files = if (allowed) listOf(
                    SiteFile(
                        url = finalUrl,
                        name = SiteFileDiscovery.nameFor(finalUrl, directKind),
                        kind = directKind,
                        mimeType = contentType,
                        referer = url,
                    ),
                ) else emptyList()
                return@withContext SiteScanResult(url, finalUrl, hostTitle(finalUrl), files)
            }
            if (contentType.isNotBlank() && "html" !in contentType && !contentType.startsWith("text/")) {
                throw IOException("A URL não aponta para uma página, imagem ou PDF compatível.")
            }
            val declaredSize = connection.contentLengthLong.takeIf { it >= 0 }
            if (declaredSize != null && declaredSize > MAX_PAGE_BYTES) {
                throw IOException("A página é grande demais para ser analisada com segurança.")
            }
            val bytes = connection.inputStream.use { input ->
                val output = ByteArrayOutputStream()
                val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                var total = 0
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    total += count
                    if (total > MAX_PAGE_BYTES) {
                        throw IOException("A página é grande demais para ser analisada com segurança.")
                    }
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
            SiteFileDiscovery.parse(
                sourceUrl = url,
                finalUrl = finalUrl,
                html = bytes.toString(charset(connection.contentType)),
                includePdfs = includePdfs,
                includeImages = includeImages,
            )
        } finally {
            connection.disconnect()
        }
    }

    suspend fun download(
        asset: SiteFile,
        onProgress: (downloaded: Long, total: Long?) -> Unit,
    ): PublishedFile = withContext(Dispatchers.IO) {
        validateWebUrl(asset.url)
        val coroutineJob = currentCoroutineContext()[Job]
        val isCancelled = { coroutineJob?.isActive == false }
        val connection = open(
            asset.url,
            "application/pdf,image/*,*/*;q=0.2",
            referer = asset.referer,
        )
        val stagingDirectory = File(appContext.cacheDir, "site-files/${UUID.randomUUID()}")
        try {
            if (isCancelled()) throw CancellationException("Download cancelado")
            val finalUrl = connection.url.toString()
            val contentType = contentType(connection)
            if ("html" in contentType) {
                throw IOException("O servidor devolveu uma página em vez do arquivo solicitado.")
            }
            val detectedKind = kindFromResponse(finalUrl, contentType)
            if (detectedKind != null && detectedKind != asset.kind) {
                throw IOException("O tipo recebido não corresponde ao arquivo selecionado.")
            }
            val total = connection.contentLengthLong.takeIf { it >= 0 }
            if (total != null && total > MAX_FILE_BYTES) {
                throw IOException("O arquivo excede o limite de 512 MB.")
            }
            if (!stagingDirectory.mkdirs() && !stagingDirectory.isDirectory) {
                throw IOException("Não foi possível preparar o armazenamento temporário.")
            }
            val suggested = contentDispositionName(connection)
                .ifBlank { SiteFileDiscovery.nameFor(finalUrl, asset.kind, asset.name) }
            val fileName = fileNameWithExtension(suggested, contentType, asset.kind)
            val stagedFile = File(stagingDirectory, fileName)
            var downloaded = 0L
            connection.inputStream.use { input ->
                stagedFile.outputStream().use { output ->
                    val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                    while (true) {
                        if (isCancelled()) throw CancellationException("Download cancelado")
                        val count = input.read(buffer)
                        if (count < 0) break
                        downloaded += count
                        if (downloaded > MAX_FILE_BYTES) {
                            throw IOException("O arquivo excede o limite de 512 MB.")
                        }
                        output.write(buffer, 0, count)
                        onProgress(downloaded, total)
                    }
                }
            }
            if (stagedFile.length() == 0L) throw IOException("O servidor devolveu um arquivo vazio.")
            try {
                publisher.publish(stagedFile, StorageCategory.SITE_FILES, isCancelled)
            } catch (_: DownloadCancelledException) {
                throw CancellationException("Download cancelado")
            }
        } finally {
            connection.disconnect()
            stagingDirectory.deleteRecursively()
        }
    }

    private fun open(rawUrl: String, accept: String, referer: String? = null): HttpURLConnection {
        val connection = URL(rawUrl).openConnection() as? HttpURLConnection
            ?: throw IOException("Protocolo de rede não suportado.")
        connection.instanceFollowRedirects = true
        connection.connectTimeout = CONNECT_TIMEOUT_MS
        connection.readTimeout = READ_TIMEOUT_MS
        connection.setRequestProperty("User-Agent", USER_AGENT)
        connection.setRequestProperty("Accept", accept)
        connection.setRequestProperty("Accept-Encoding", "identity")
        if (!referer.isNullOrBlank()) connection.setRequestProperty("Referer", referer)
        connection.connect()
        if (connection.responseCode !in 200..299) {
            val status = connection.responseCode
            connection.disconnect()
            throw IOException("O site respondeu com HTTP $status.")
        }
        validateWebUrl(connection.url.toString())
        return connection
    }

    private fun kindFromResponse(url: String, contentType: String): SiteFileKind? = when {
        contentType == "application/pdf" -> SiteFileKind.PDF
        contentType.startsWith("image/") -> SiteFileKind.IMAGE
        else -> SiteFileDiscovery.kindFromUrl(url)
    }

    private fun contentType(connection: HttpURLConnection): String =
        connection.contentType.orEmpty().substringBefore(';').trim().lowercase()

    private fun charset(rawContentType: String?): Charset {
        val raw = Regex("charset=([^;\\s]+)", RegexOption.IGNORE_CASE)
            .find(rawContentType.orEmpty())
            ?.groupValues
            ?.get(1)
            ?.trim('"', '\'')
        return runCatching { Charset.forName(raw ?: "UTF-8") }.getOrDefault(Charsets.UTF_8)
    }

    private fun contentDispositionName(connection: HttpURLConnection): String {
        val raw = connection.getHeaderField("Content-Disposition").orEmpty()
        val extended = Regex("filename\\*\\s*=\\s*(?:UTF-8'')?([^;]+)", RegexOption.IGNORE_CASE)
            .find(raw)?.groupValues?.get(1)
        val regular = Regex(
            """filename\s*=\s*(?:"([^"]+)"|'([^']+)'|([^;]+))""",
            RegexOption.IGNORE_CASE,
        ).find(raw)?.groupValues?.drop(1)?.firstOrNull(String::isNotBlank)
        val value = (extended ?: regular).orEmpty().trim().trim('"', '\'')
        return runCatching { URLDecoder.decode(value, Charsets.UTF_8.name()) }.getOrDefault(value)
    }

    private fun fileNameWithExtension(
        suggested: String,
        contentType: String,
        kind: SiteFileKind,
    ): String {
        var name = SiteFileDiscovery.nameFor("https://local.invalid/$suggested", kind, suggested)
        if (kind == SiteFileKind.PDF) return name
        val extension = name.substringAfterLast('.', "").lowercase()
        if (extension in IMAGE_EXTENSIONS) return name
        name += IMAGE_MIME_EXTENSIONS[contentType] ?: ".img"
        return name
    }

    private fun validateWebUrl(raw: String) {
        val valid = runCatching {
            val uri = URI(raw.trim())
            (uri.scheme.equals("http", true) || uri.scheme.equals("https", true)) &&
                !uri.host.isNullOrBlank() && uri.userInfo.isNullOrBlank()
        }.getOrDefault(false)
        if (!valid) throw IOException("Informe uma URL HTTP ou HTTPS válida.")
    }

    private fun hostTitle(url: String): String = runCatching {
        URI(url).host.orEmpty().removePrefix("www.").ifBlank { "Site" }
    }.getOrDefault("Site")

    companion object {
        private const val MAX_PAGE_BYTES = 5 * 1024 * 1024
        private const val MAX_FILE_BYTES = 512L * 1024 * 1024
        private const val CONNECT_TIMEOUT_MS = 20_000
        private const val READ_TIMEOUT_MS = 30_000
        private val USER_AGENT =
            "MediaDownloader/${BuildConfig.VERSION_NAME} (Android; site-file-extractor)"
        private val IMAGE_EXTENSIONS = setOf(
            "avif", "bmp", "gif", "heic", "heif", "ico", "jpeg", "jpg", "png", "svg",
            "tif", "tiff", "webp",
        )
        private val IMAGE_MIME_EXTENSIONS = mapOf(
            "image/avif" to ".avif",
            "image/bmp" to ".bmp",
            "image/gif" to ".gif",
            "image/heic" to ".heic",
            "image/heif" to ".heif",
            "image/jpeg" to ".jpg",
            "image/png" to ".png",
            "image/svg+xml" to ".svg",
            "image/tiff" to ".tiff",
            "image/webp" to ".webp",
            "image/x-icon" to ".ico",
        )
    }
}
