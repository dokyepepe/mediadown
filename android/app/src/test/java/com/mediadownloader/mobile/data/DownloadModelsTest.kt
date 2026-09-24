package com.mediadownloader.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
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
    fun optionsRejectOutOfRangeAudioEffects() {
        assertThrows(IllegalArgumentException::class.java) {
            DownloadOptions(audioSpeed = 3f)
        }
        assertThrows(IllegalArgumentException::class.java) {
            DownloadOptions(audioPitchSemitones = 13f)
        }
        assertThrows(IllegalArgumentException::class.java) {
            DownloadOptions(audioVolumePercent = 500)
        }
    }

    @Test
    fun optionsExposeEffectsOnlyWhenAdjusted() {
        assertEquals(null, DownloadOptions().audioEffects())
        assertEquals(null, DownloadOptions(audioSpeed = 1f, audioPitchSemitones = 0f).audioEffects())

        val speedUp = DownloadOptions(audioSpeed = 1.25f).audioEffects()
        assertEquals(1.25f, speedUp!!.speed, 0.0f)
        val shifted = DownloadOptions(audioPitchSemitones = 2f).audioEffects()
        assertEquals(2f, shifted!!.semitones, 0.0f)
        val boosted = DownloadOptions(audioVolumePercent = 150).audioEffects()
        assertEquals(150, boosted!!.volumePercent)
    }

    @Test
    fun optionsCarryNativeToggleEffects() {
        assertEquals(
            null,
            DownloadOptions(audioBass = false, audioEcho = false).audioEffects(),
        )

        val effects = DownloadOptions(
            audioBass = true,
            audioEcho = true,
            audioTremolo = true,
            audioNormalize = true,
        ).audioEffects()
        assertEquals(true, effects!!.bass)
        assertEquals(true, effects.echo)
        assertEquals(true, effects.tremolo)
        assertEquals(true, effects.normalize)
    }

    @Test
    fun optionsConsiderTrimsAndFadesAsAudioProcessing() {
        assertFalse(DownloadOptions().hasAudioProcessing)
        assertTrue(DownloadOptions(trimStartSeconds = 5f).hasAudioProcessing)
        assertTrue(DownloadOptions(trimDurationSeconds = 10f).hasAudioProcessing)
        assertTrue(DownloadOptions(fadeInSeconds = 2f).hasAudioProcessing)
        assertTrue(DownloadOptions(fadeOutSeconds = 2f).hasAudioProcessing)
        assertTrue(
            DownloadOptions(audioSpeed = 1.5f).hasAudioProcessing,
        )
        // A trim/fade pass is independent from the effect chain.
        assertEquals(null, DownloadOptions(trimStartSeconds = 5f).audioEffects())
    }

    @Test
    fun optionsRejectInvalidTrimAndFades() {
        assertThrows(IllegalArgumentException::class.java) {
            DownloadOptions(trimStartSeconds = -1f)
        }
        assertThrows(IllegalArgumentException::class.java) {
            DownloadOptions(trimDurationSeconds = 0f)
        }
        assertThrows(IllegalArgumentException::class.java) {
            DownloadOptions(fadeInSeconds = -1f)
        }
        assertThrows(IllegalArgumentException::class.java) {
            DownloadOptions(fadeOutSeconds = -1f)
        }
    }

    @Test
    fun optionsFilterChainMatchesAudioFilterChain() {
        val options = DownloadOptions(
            audioSpeed = 1.25f,
            audioPitchSemitones = -3f,
            audioVolumePercent = 80,
            audioEcho = true,
            audioNormalize = true,
        ).audioEffects()!!
        assertEquals(
            AudioFilterChain.build(
                speed = options.speed,
                pitchRatio = AudioEffects(1f, options.semitones, 100).pitchRatio,
                volumeFactor = options.volumeFactor,
                bass = options.bass,
                echo = options.echo,
                tremolo = options.tremolo,
                normalize = options.normalize,
            ),
            options.filterChain(),
        )
    }

    @Test
    fun resultExposesFirstPublishedFile() {
        val first = PublishedFile("content://first", "first.mp4", "video/mp4", 50L)
        val second = PublishedFile("content://second", "second.srt", "application/x-subrip", 10L)

        assertEquals(first, DownloadResult(listOf(first, second), "ok").primaryFile)
    }
}
