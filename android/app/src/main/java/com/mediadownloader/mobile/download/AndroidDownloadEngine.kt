package com.mediadownloader.mobile.download

import android.content.Context
import android.os.Environment
import android.webkit.URLUtil
import com.mediadownloader.mobile.data.AudioFormat
import com.mediadownloader.mobile.data.DownloadItem
import com.mediadownloader.mobile.data.DownloadOptions
import com.mediadownloader.mobile.data.DownloadResult
import com.mediadownloader.mobile.data.MediaAnalysis
import com.mediadownloader.mobile.data.MediaFormat
import com.mediadownloader.mobile.data.MediaType
import com.mediadownloader.mobile.data.VideoContainer
import com.yausername.ffmpeg.FFmpeg
import com.yausername.youtubedl_android.YoutubeDL
import com.yausername.youtubedl_android.YoutubeDLRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

class DownloadCancelledException : IOException("Download cancelado")

data class EngineProgress(
    val percent: Int,
    val etaSeconds: Long?,
    val outputLine: String?,
    val processing: Boolean,
)

/** Android adapter around youtubedl-android 0.18.1 and its bundled FFmpeg runtime. */
class AndroidDownloadEngine(context: Context) {
    private val appContext = context.applicationContext
    private val publisher = MediaStorePublisher(appContext)
    private val initializationMutex = Mutex()
    private val cancelledProcesses = ConcurrentHashMap.newKeySet<String>()

    @Volatile
    private var initialized = false

    suspend fun analyze(url: String): MediaAnalysis = withContext(Dispatchers.IO) {
        validateUrl(url)
        ensureInitialized()
        val processId = "analysis-${UUID.randomUUID()}"
        val request = YoutubeDLRequest(url.trim()).apply {
            addOption("--dump-single-json")
            addOption("--skip-download")
            addOption("--no-warnings")
            addOption("--flat-playlist")
        }
        val response = YoutubeDL.getInstance().execute(request, processId, null)
        parseAnalysis(url.trim(), response.out)
    }

    suspend fun download(
        item: DownloadItem,
        onProgress: (EngineProgress) -> Unit,
    ): DownloadResult = withContext(Dispatchers.IO) {
        validateUrl(item.sourceUrl)
        ensureInitialized()
        checkCancelled(item.id)

        val stagingDirectory = stagingDirectoryFor(item.id)
        resetStagingDirectory(stagingDirectory)
        val request = buildDownloadRequest(item, stagingDirectory)

        try {
            val response = try {
                YoutubeDL.getInstance().execute(
                    request,
                    item.id,
                    false,
                    callback = { progress, etaSeconds, line ->
                        val processing = line.contains("[ffmpeg]", ignoreCase = true) ||
                            line.contains("[Merger]", ignoreCase = true) ||
                            line.contains("[ExtractAudio]", ignoreCase = true) ||
                            line.startsWith("size=")
                        onProgress(
                            EngineProgress(
                                percent = when {
                                    processing -> 99
                                    progress.isNaN() || progress < 0 -> 0
                                    else -> progress.toInt().coerceIn(0, 99)
                                },
                                etaSeconds = etaSeconds.takeIf { it >= 0 },
                                outputLine = line.trim().takeIf(String::isNotBlank),
                                processing = processing,
                            ),
                        )
                    },
                )
            } catch (error: YoutubeDL.CanceledException) {
                throw DownloadCancelledException()
            } catch (error: InterruptedException) {
                Thread.currentThread().interrupt()
                throw DownloadCancelledException()
            }

            checkCancelled(item.id)
            val stagedFiles = completedStagingFiles(stagingDirectory)
            if (stagedFiles.isEmpty()) {
                throw IOException("O yt-dlp terminou sem produzir um arquivo")
            }

            val published = mutableListOf<com.mediadownloader.mobile.data.PublishedFile>()
            stagedFiles.forEach { file ->
                checkCancelled(item.id)
                published += publisher.publish(file) { cancelledProcesses.contains(item.id) }
            }
            DownloadResult(files = published, commandOutput = response.out)
        } finally {
            stagingDirectory.deleteRecursively()
            cancelledProcesses.remove(item.id)
        }
    }

    fun cancel(processId: String): Boolean {
        cancelledProcesses += processId
        return YoutubeDL.getInstance().destroyProcessById(processId)
    }

    fun prepare(processId: String) {
        cancelledProcesses.remove(processId)
    }

    suspend fun initialize() = withContext(Dispatchers.IO) {
        ensureInitialized()
    }

    private suspend fun ensureInitialized() {
        if (initialized) return
        initializationMutex.withLock {
            if (initialized) return
            YoutubeDL.getInstance().init(appContext)
            FFmpeg.getInstance().init(appContext)
            initialized = true
        }
    }

    private fun buildDownloadRequest(item: DownloadItem, stagingDirectory: File): YoutubeDLRequest {
        val outputTemplate = File(
            stagingDirectory,
            "%(title).180B [%(id)s].%(ext)s",
        ).absolutePath
        return YoutubeDLRequest(item.sourceUrl).apply {
            addOption("--newline")
            addOption("--no-mtime")
            addOption("--trim-filenames", 180)
            addOption("--output", outputTemplate)
            addOption(if (item.options.downloadPlaylist) "--yes-playlist" else "--no-playlist")
            addMediaOptions(item.options)
            if (item.options.includeSubtitles) {
                addOption("--write-subs")
                addOption("--write-auto-subs")
                addOption("--sub-langs", item.options.subtitleLanguages.joinToString(","))
                addOption("--convert-subs", "srt")
            }
        }
    }

    private fun YoutubeDLRequest.addMediaOptions(options: DownloadOptions) {
        when (options.mediaType) {
            MediaType.AUDIO -> {
                addOption("--format", options.formatId ?: "bestaudio/best")
                addOption("--extract-audio")
                addOption("--audio-format", options.audioFormat.extension)
                addOption("--audio-quality", "${options.audioBitrateKbps}K")
                addOption("--embed-thumbnail")
                addOption("--add-metadata")
            }

            MediaType.VIDEO -> {
                addOption("--format", videoSelector(options))
                addOption("--merge-output-format", options.videoContainer.extension)
                addOption("--remux-video", options.videoContainer.extension)
                addOption("--add-metadata")
            }
        }
    }

    private fun videoSelector(options: DownloadOptions): String {
        options.formatId?.takeIf(String::isNotBlank)?.let { selected ->
            return "$selected+bestaudio/$selected/best"
        }
        val height = options.maxVideoHeight?.let { "[height<=$it]" }.orEmpty()
        return when (options.videoContainer) {
            VideoContainer.MP4 ->
                "bestvideo$height[ext=mp4]+bestaudio[ext=m4a]/" +
                    "best$height[ext=mp4]/bestvideo$height+bestaudio/best$height/best"

            VideoContainer.WEBM ->
                "bestvideo$height[ext=webm]+bestaudio[ext=webm]/" +
                    "best$height[ext=webm]/bestvideo$height+bestaudio/best$height/best"

            VideoContainer.MKV ->
                "bestvideo$height+bestaudio/best$height/best"
        }
    }

    private fun parseAnalysis(sourceUrl: String, output: String): MediaAnalysis {
        val json = extractJsonObject(output)
        val entries = json.optJSONArray("entries")
        val formatsJson = json.optJSONArray("formats")
        val formats = buildList {
            if (formatsJson != null) {
                for (index in 0 until formatsJson.length()) {
                    val item = formatsJson.optJSONObject(index) ?: continue
                    val id = item.optNullableString("format_id") ?: continue
                    add(
                        MediaFormat(
                            id = id,
                            extension = item.optNullableString("ext"),
                            formatNote = item.optNullableString("format_note"),
                            width = item.optPositiveInt("width"),
                            height = item.optPositiveInt("height"),
                            fps = item.optPositiveInt("fps"),
                            videoCodec = item.optNullableString("vcodec"),
                            audioCodec = item.optNullableString("acodec"),
                            approximateSizeBytes = item.optPositiveLong("filesize")
                                ?: item.optPositiveLong("filesize_approx"),
                        ),
                    )
                }
            }
        }
        val isPlaylist = entries != null || json.optNullableString("_type") == "playlist"
        val itemCount = json.optPositiveInt("playlist_count")
            ?: entries?.length()?.takeIf { it > 0 }
        return MediaAnalysis(
            sourceUrl = sourceUrl,
            title = json.optNullableString("title") ?: sourceUrl,
            uploader = json.optNullableString("uploader")
                ?: json.optNullableString("channel"),
            sourceName = json.optNullableString("extractor_key")
                ?: json.optNullableString("extractor"),
            thumbnailUrl = json.optNullableString("thumbnail"),
            durationSeconds = json.optPositiveLong("duration"),
            isPlaylist = isPlaylist,
            playlistItemCount = itemCount,
            formats = formats,
        )
    }

    private fun extractJsonObject(output: String): JSONObject {
        val trimmed = output.trim()
        try {
            return JSONObject(trimmed)
        } catch (_: Exception) {
            val start = trimmed.indexOf('{')
            val end = trimmed.lastIndexOf('}')
            if (start >= 0 && end > start) {
                try {
                    return JSONObject(trimmed.substring(start, end + 1))
                } catch (_: Exception) {
                    // Fall through to the domain-specific error below.
                }
            }
        }
        throw IOException("Não foi possível interpretar os metadados retornados pelo yt-dlp")
    }

    private fun completedStagingFiles(directory: File): List<File> {
        val ignoredSuffixes = setOf("part", "ytdl", "temp", "tmp")
        return directory.walkTopDown()
            .filter(File::isFile)
            .filter { it.extension.lowercase() !in ignoredSuffixes }
            .sortedWith(
                compareByDescending<File> { isPrimaryMedia(it) }
                    .thenByDescending(File::length),
            )
            .toList()
    }

    private fun isPrimaryMedia(file: File): Boolean = file.extension.lowercase() in setOf(
        "mp4", "mkv", "webm", "mov", "avi", "mp3", "m4a", "opus", "ogg", "flac", "wav",
    )

    private fun stagingDirectoryFor(id: String): File {
        val externalBase = appContext.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)
            ?: appContext.filesDir
        val safeId = id.replace(Regex("[^A-Za-z0-9._-]"), "_")
        return File(File(externalBase, "staging"), safeId)
    }

    private fun resetStagingDirectory(directory: File) {
        if (directory.exists() && !directory.deleteRecursively()) {
            throw IOException("Não foi possível limpar a área temporária")
        }
        if (!directory.mkdirs() && !directory.isDirectory) {
            throw IOException("Não foi possível criar a área temporária")
        }
    }

    private fun checkCancelled(processId: String) {
        if (cancelledProcesses.contains(processId)) throw DownloadCancelledException()
    }

    private fun validateUrl(url: String) {
        val normalized = url.trim()
        require(URLUtil.isHttpUrl(normalized) || URLUtil.isHttpsUrl(normalized)) {
            "Informe uma URL HTTP ou HTTPS válida"
        }
    }

    private fun JSONObject.optNullableString(name: String): String? =
        if (!has(name) || isNull(name)) null else optString(name).takeIf(String::isNotBlank)

    private fun JSONObject.optPositiveInt(name: String): Int? =
        if (!has(name) || isNull(name)) null else optInt(name).takeIf { it > 0 }

    private fun JSONObject.optPositiveLong(name: String): Long? =
        if (!has(name) || isNull(name)) null else optLong(name).takeIf { it > 0 }
}
