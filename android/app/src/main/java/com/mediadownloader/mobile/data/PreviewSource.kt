package com.mediadownloader.mobile.data

/**
 * A directly playable stream, mirroring the desktop `PreviewSource` model.
 *
 * The desktop resolves it live with yt-dlp selectors (`best[acodec!=none][vcodec!=none]`,
 * `best[acodec!=none]`, `best[vcodec!=none]`, `best`). Here the same priority is applied
 * to the formats already collected during analysis, so no second network round-trip is
 * needed.
 */
data class PreviewSource(
    val url: String,
    val extension: String? = null,
    val hasVideo: Boolean = true,
    val hasAudio: Boolean = true,
)

/**
 * Selects the best usable preview stream from the formats of a media analysis.
 * Pure and unit-testable.
 */
object PreviewSourceResolver {

    /**
     * Returns the highest-priority stream with a direct URL, or `null` when no
     * format can be played directly (callers then fall back to the media URL).
     */
    fun resolve(formats: List<MediaFormat>): PreviewSource? {
        val usable = formats.filter(MediaFormat::hasStreamUrl)
        if (usable.isEmpty()) return null

        val muxed = usable.filter { it.hasVideo && it.hasAudio }
        val audioOnly = usable.filter { it.hasAudio && !it.hasVideo }
        val videoOnly = usable.filter { it.hasVideo && !it.hasAudio }

        val candidate = when {
            muxed.isNotEmpty() -> muxed.bestVideoLike()
            audioOnly.isNotEmpty() -> audioOnly.bestAudioLike()
            videoOnly.isNotEmpty() -> videoOnly.bestVideoLike()
            else -> usable.bestVideoLike()
        } ?: return null

        return PreviewSource(
            url = candidate.streamUrl.orEmpty(),
            extension = candidate.extension,
            hasVideo = candidate.hasVideo,
            hasAudio = candidate.hasAudio,
        )
    }

    /** Prefers higher resolution, then higher bitrate, then file size. */
    private fun List<MediaFormat>.bestVideoLike(): MediaFormat? =
        maxWithOrNull(
            compareBy<MediaFormat> { it.height ?: 0 }
                .thenBy { it.totalBitrate ?: 0L }
                .thenBy { it.approximateSizeBytes ?: 0L },
        )

    /** Prefers higher bitrate, then file size (audio has no resolution). */
    private fun List<MediaFormat>.bestAudioLike(): MediaFormat? =
        maxWithOrNull(
            compareBy<MediaFormat> { it.totalBitrate ?: 0L }
                .thenBy { it.approximateSizeBytes ?: 0L },
        )
}