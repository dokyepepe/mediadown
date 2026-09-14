package com.mediadownloader.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PreviewSourceResolverTest {

    private fun format(
        id: String,
        height: Int? = null,
        videoCodec: String? = null,
        audioCodec: String? = null,
        bitrate: Long? = null,
        size: Long? = null,
        url: String? = null,
    ) = MediaFormat(
        id = id,
        extension = "mp4",
        formatNote = null,
        width = height,
        height = height,
        fps = null,
        videoCodec = videoCodec,
        audioCodec = audioCodec,
        approximateSizeBytes = size,
        streamUrl = url,
        totalBitrate = bitrate,
    )

    @Test
    fun emptyFormatsResolveToNull() {
        assertNull(PreviewSourceResolver.resolve(emptyList()))
    }

    @Test
    fun formatsWithoutStreamUrlResolveToNull() {
        val formats = listOf(format("a", height = 1080, videoCodec = "avc1", audioCodec = "mp4a", url = null))
        assertNull(PreviewSourceResolver.resolve(formats))
    }

    @Test
    fun prefersMuxedOverAudioOnly() {
        val formats = listOf(
            format("audio", audioCodec = "mp4a", bitrate = 320, url = "https://audio.example"),
            format("muxed", height = 720, videoCodec = "avc1", audioCodec = "mp4a", bitrate = 1500, url = "https://muxed.example"),
        )
        val source = PreviewSourceResolver.resolve(formats)!!
        assertEquals("https://muxed.example", source.url)
        assertTrue(source.hasVideo)
        assertTrue(source.hasAudio)
    }

    @Test
    fun prefersHigherResolutionMuxed() {
        val formats = listOf(
            format("low", height = 360, videoCodec = "avc1", audioCodec = "mp4a", url = "https://low.example"),
            format("high", height = 2160, videoCodec = "avc1", audioCodec = "mp4a", url = "https://high.example"),
        )
        val source = PreviewSourceResolver.resolve(formats)!!
        assertEquals("https://high.example", source.url)
    }

    @Test
    fun breaksResolutionTieByBitrateAndSize() {
        val formats = listOf(
            format("bitrateLow", height = 1080, videoCodec = "avc1", audioCodec = "mp4a", bitrate = 1000, url = "https://bitrateLow.example"),
            format("bitrateHigh", height = 1080, videoCodec = "avc1", audioCodec = "mp4a", bitrate = 4000, url = "https://bitrateHigh.example"),
            format("sizeHigh", height = 1080, videoCodec = "avc1", audioCodec = "mp4a", bitrate = 4000, size = 999, url = "https://sizeHigh.example"),
        )
        val source = PreviewSourceResolver.resolve(formats)!!
        assertEquals("https://sizeHigh.example", source.url)
    }

    @Test
    fun fallsBackToAudioOnlyWhenNoMuxed() {
        val formats = listOf(
            format("video", height = 2160, videoCodec = "vp9", url = "https://video.example"),
            format("audio", audioCodec = "opus", bitrate = 160, url = "https://audio.example"),
        )
        val source = PreviewSourceResolver.resolve(formats)!!
        assertEquals("https://audio.example", source.url)
        assertFalse(source.hasVideo)
        assertTrue(source.hasAudio)
    }

    @Test
    fun bestAudioWinsOnBitrateThenSize() {
        val formats = listOf(
            format("a128", audioCodec = "mp4a", bitrate = 128, size = 90, url = "https://a128.example"),
            format("a320", audioCodec = "mp4a", bitrate = 320, url = "https://a320.example"),
        )
        val source = PreviewSourceResolver.resolve(formats)!!
        assertEquals("https://a320.example", source.url)
    }

    @Test
    fun fallsBackToVideoOnlyWhenNoAudioAtAll() {
        val formats = listOf(
            format("videoOnly", height = 480, videoCodec = "avc1", url = "https://videoOnly.example"),
            format("streamWithNoCodecs", url = "https://unknown.example"),
        )
        val source = PreviewSourceResolver.resolve(formats)!!
        assertEquals("https://videoOnly.example", source.url)
    }

    @Test
    fun presentationalFormatWithCodecNoneIgnoredAsFallback() {
        val formats = listOf(
            format("audio", audioCodec = "mp4a", url = "https://audio.example"),
        )
        val source = PreviewSourceResolver.resolve(formats)!!
        assertTrue(source.hasAudio)
        assertFalse(source.hasVideo)
    }
}