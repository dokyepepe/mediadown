package com.mediadownloader.mobile.data

import java.util.UUID

enum class MediaType {
    VIDEO,
    AUDIO,
}

enum class VideoContainer(val extension: String, val mimeType: String) {
    MP4("mp4", "video/mp4"),
    MKV("mkv", "video/x-matroska"),
    WEBM("webm", "video/webm"),
}

enum class AudioFormat(val extension: String, val mimeType: String) {
    MP3("mp3", "audio/mpeg"),
    M4A("m4a", "audio/mp4"),
    OPUS("opus", "audio/opus"),
    FLAC("flac", "audio/flac"),
    WAV("wav", "audio/wav"),
}

/** Options persisted with every queue item so a process restart can resume the queue. */
data class DownloadOptions(
    val mediaType: MediaType = MediaType.VIDEO,
    val maxVideoHeight: Int? = 1080,
    val videoContainer: VideoContainer = VideoContainer.MP4,
    val audioFormat: AudioFormat = AudioFormat.MP3,
    val audioBitrateKbps: Int = 192,
    val formatId: String? = null,
    val downloadPlaylist: Boolean = false,
    val includeSubtitles: Boolean = false,
    val subtitleLanguages: List<String> = listOf("pt", "pt-BR", "en"),
) {
    init {
        require(maxVideoHeight == null || maxVideoHeight > 0) {
            "maxVideoHeight must be positive"
        }
        require(audioBitrateKbps in 32..320) {
            "audioBitrateKbps must be between 32 and 320"
        }
    }
}

enum class DownloadState {
    QUEUED,
    INITIALIZING,
    DOWNLOADING,
    PROCESSING,
    COMPLETED,
    FAILED,
    CANCELLED,
}

data class DownloadItem(
    val id: String,
    val sourceUrl: String,
    val title: String,
    val sourceName: String? = null,
    val thumbnailUrl: String? = null,
    val options: DownloadOptions = DownloadOptions(),
    val state: DownloadState = DownloadState.QUEUED,
    val progress: Int = 0,
    val etaSeconds: Long? = null,
    val statusLine: String? = null,
    val errorMessage: String? = null,
    val outputUri: String? = null,
    val outputFileName: String? = null,
    val outputMimeType: String? = null,
    val outputSizeBytes: Long? = null,
    val retryCount: Int = 0,
    val createdAtEpochMs: Long,
    val updatedAtEpochMs: Long,
    val completedAtEpochMs: Long? = null,
) {
    companion object {
        fun create(
            sourceUrl: String,
            title: String = sourceUrl,
            sourceName: String? = null,
            thumbnailUrl: String? = null,
            options: DownloadOptions = DownloadOptions(),
            nowEpochMs: Long = System.currentTimeMillis(),
        ): DownloadItem {
            val normalizedUrl = sourceUrl.trim()
            return DownloadItem(
                id = UUID.randomUUID().toString(),
                sourceUrl = normalizedUrl,
                title = title.trim().ifBlank { normalizedUrl },
                sourceName = sourceName,
                thumbnailUrl = thumbnailUrl,
                options = options,
                createdAtEpochMs = nowEpochMs,
                updatedAtEpochMs = nowEpochMs,
            )
        }
    }
}

data class HistoryItem(
    val id: String,
    val downloadId: String,
    val sourceUrl: String,
    val title: String,
    val fileUri: String,
    val fileName: String,
    val mimeType: String,
    val sizeBytes: Long,
    val thumbnailUrl: String? = null,
    val completedAtEpochMs: Long = System.currentTimeMillis(),
) {
    companion object {
        fun create(
            download: DownloadItem,
            fileUri: String,
            fileName: String,
            mimeType: String,
            sizeBytes: Long,
            completedAtEpochMs: Long = System.currentTimeMillis(),
        ): HistoryItem = HistoryItem(
            id = UUID.randomUUID().toString(),
            downloadId = download.id,
            sourceUrl = download.sourceUrl,
            title = if (fileName.isBlank()) download.title else fileName.substringBeforeLast('.'),
            fileUri = fileUri,
            fileName = fileName,
            mimeType = mimeType,
            sizeBytes = sizeBytes,
            thumbnailUrl = download.thumbnailUrl,
            completedAtEpochMs = completedAtEpochMs,
        )
    }
}

data class MediaFormat(
    val id: String,
    val extension: String?,
    val formatNote: String?,
    val width: Int?,
    val height: Int?,
    val fps: Int?,
    val videoCodec: String?,
    val audioCodec: String?,
    val approximateSizeBytes: Long?,
) {
    val hasVideo: Boolean get() = !videoCodec.isNullOrBlank() && videoCodec != "none"
    val hasAudio: Boolean get() = !audioCodec.isNullOrBlank() && audioCodec != "none"
}

data class MediaAnalysis(
    val sourceUrl: String,
    val title: String,
    val uploader: String?,
    val sourceName: String?,
    val thumbnailUrl: String?,
    val durationSeconds: Long?,
    val isPlaylist: Boolean,
    val playlistItemCount: Int?,
    val formats: List<MediaFormat>,
)

data class PublishedFile(
    val uri: String,
    val displayName: String,
    val mimeType: String,
    val sizeBytes: Long,
)

data class DownloadResult(
    val files: List<PublishedFile>,
    val commandOutput: String,
) {
    val primaryFile: PublishedFile
        get() = files.first()
}
