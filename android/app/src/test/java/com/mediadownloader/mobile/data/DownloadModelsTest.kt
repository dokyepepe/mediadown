package com.mediadownloader.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test

class DownloadModelsTest {
    @Test
    fun createNormalizesUrlAndUsesItForBlankTitle() {
        val item = DownloadItem.create(
            sourceUrl = "  https://example.com/video  ",
            title = "   ",
            nowEpochMs = 1234L,
        )

        assertEquals("https://example.com/video", item.sourceUrl)
        assertEquals("https://example.com/video", item.title)
        assertEquals(DownloadState.QUEUED, item.state)
        assertEquals(1234L, item.createdAtEpochMs)
        assertNull(item.outputUri)
    }

    @Test
    fun optionsRejectInvalidVideoHeight() {
        assertThrows(IllegalArgumentException::class.java) {
            DownloadOptions(maxVideoHeight = 0)
        }
    }

    @Test
    fun optionsRejectInvalidAudioBitrate() {
        assertThrows(IllegalArgumentException::class.java) {
            DownloadOptions(audioBitrateKbps = 321)
        }
    }

    @Test
    fun resultExposesFirstPublishedFile() {
        val first = PublishedFile("content://first", "first.mp4", "video/mp4", 50L)
        val second = PublishedFile("content://second", "second.srt", "application/x-subrip", 10L)

        assertEquals(first, DownloadResult(listOf(first, second), "ok").primaryFile)
    }
}
