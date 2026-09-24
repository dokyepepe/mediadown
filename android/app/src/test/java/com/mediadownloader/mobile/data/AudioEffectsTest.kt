package com.mediadownloader.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AudioEffectsTest {
    @Test
    fun identityEffectsProduceNoFilterChain() {
        assertTrue(AudioEffects().isIdentity)
        assertNull(AudioEffects().filterChain())
    }

    @Test
    fun speedOnlyBuildsAtempo() {
        val chain = AudioEffects(speed = 1.5f).filterChain()
        assertEquals("atempo=1.5", chain)
    }

    @Test
    fun volumeOnlyBuildsVolumeFilter() {
        val chain = AudioEffects(volumePercent = 80).filterChain()
        assertEquals("volume=0.8", chain)
    }

    @Test
    fun speedAndVolumeCombineInOrder() {
        val chain = AudioEffects(speed = 1.5f, volumePercent = 80).filterChain()
        assertEquals("atempo=1.5,volume=0.8", chain)
    }

    @Test
    fun pitchStagesUseAsetrateAndPitchRecoveryAtempo() {
        val chain = AudioEffects(semitones = 12f).filterChain()
        assertNotNull(chain)
        assertTrue(chain!!.startsWith("aresample=44100,"))
        assertTrue(chain.contains("asetrate=88200"))
        assertTrue(chain.contains("aresample=44100"))
        assertTrue(chain.contains("atempo=0.5"))
    }

    @Test
    fun semitonesConvertToExpectedRatio() {
        assertEquals(2f, semitonesToRatio(12f), 0.001f)
        assertEquals(0.5f, semitonesToRatio(-12f), 0.001f)
        assertEquals(1f, semitonesToRatio(0f), 0.001f)
        assertEquals(1.059f, semitonesToRatio(1f), 0.001f)
    }

    @Test
    fun sanitizedClampsValuesToSupportedRanges() {
        val sanitized = AudioEffects(
            speed = 3f,
            semitones = 20f,
            volumePercent = 300,
        ).sanitized()
        assertEquals(AudioEffects.MAX_SPEED, sanitized.speed, 0.001f)
        assertEquals(AudioEffects.MAX_SEMITONES, sanitized.semitones, 0.001f)
        assertEquals(AudioEffects.MAX_VOLUME_PERCENT, sanitized.volumePercent)

        val lower = AudioEffects(
            speed = 0.1f,
            semitones = -20f,
            volumePercent = 1,
        ).sanitized()
        assertEquals(AudioEffects.MIN_SPEED, lower.speed, 0.001f)
        assertEquals(AudioEffects.MIN_SEMITONES, lower.semitones, 0.001f)
        assertEquals(AudioEffects.MIN_VOLUME_PERCENT, lower.volumePercent)
    }

    @Test
    fun sanitizedKeepsInRangeValuesUntouched() {
        val original = AudioEffects(speed = 1.25f, semitones = 2f, volumePercent = 120)
        assertEquals(original, original.sanitized())
        assertFalse(original.isIdentity)
    }

    @Test
    fun togglesAloneBuildChainInStableOrder() {
        val chain = AudioEffects(bass = true, echo = true, tremolo = true, normalize = true).filterChain()
        assertNotNull(chain)
        assertEquals(
            "bass=g=6:f=100,aecho=0.7:0.7:300:0.3,tremolo=f=5:d=0.25,loudnorm=I=-16:TP=-1.5:LRA=11",
            chain,
        )
    }

    @Test
    fun singleToggleIsEnoughToMakeChain() {
        assertNull(AudioEffects().filterChain())
        assertNotNull(AudioEffects(bass = true).filterChain())
        assertFalse(AudioEffects(bass = true).isIdentity)
        assertFalse(AudioEffects(normalize = true).isIdentity)
    }

    @Test
    fun togglesCombineWithSpeedVolumeInExpectedOrder() {
        val chain = AudioEffects(
            speed = 1.5f,
            volumePercent = 80,
            echo = true,
            normalize = true,
        ).filterChain()
        assertNotNull(chain)
        assertEquals("atempo=1.5,aecho=0.7:0.7:300:0.3,volume=0.8,loudnorm=I=-16:TP=-1.5:LRA=11", chain)
    }

    @Test
    fun pitchStagesPrecedeToggleFiltersAndNormalization() {
        val chain = AudioEffects(semitones = 12f, bass = true, normalize = true).filterChain()
        assertNotNull(chain)
        assertTrue(chain!!.startsWith("aresample=44100,"))
        assertTrue(chain.contains("atempo=0.5,bass=g=6:f=100,loudnorm=I=-16:TP=-1.5:LRA=11"))
    }

    @Test
    fun sanitizedPreservesToggles() {
        val sanitized = AudioEffects(
            speed = 3f,
            bass = true,
            tremolo = true,
        ).sanitized()
        assertEquals(AudioEffects.MAX_SPEED, sanitized.speed, 0.001f)
        assertTrue(sanitized.bass)
        assertTrue(sanitized.tremolo)
        assertFalse(sanitized.echo)
    }
}

class TrimFadeChainTest {
    @Test
    fun noFadesProduceNoGraph() {
        assertNull(TrimFadeChain.fadeGraph(10f, 0f, 0f))
        assertNull(TrimFadeChain.fadeGraph(null, 0f, 0f))
        assertNotNull(TrimFadeChain.fadeGraph(10f, 2f, 2f))
    }

    @Test
    fun fadeInOnlyPlacesAtStreamStart() {
        assertEquals("afade=t=in:d=2", TrimFadeChain.fadeGraph(10f, 2f, 0f))
    }

    @Test
    fun fadeOutOnlyPlacesBeforeSegmentEnd() {
        assertEquals("afade=t=out:st=8:d=2", TrimFadeChain.fadeGraph(10f, 0f, 2f))
    }

    @Test
    fun bothFadesCombineInOrder() {
        assertEquals(
            "afade=t=in:d=2,afade=t=out:st=8:d=2",
            TrimFadeChain.fadeGraph(10f, 2f, 2f),
        )
    }

    @Test
    fun fadesAreScaledDownWhenTheirSumExceedsSegment() {
        assertEquals(
            "afade=t=in:d=5,afade=t=out:st=5:d=5",
            TrimFadeChain.fadeGraph(10f, 20f, 20f),
        )
    }

    @Test
    fun singleFadeIsClampedToSegment() {
        assertEquals("afade=t=in:d=10", TrimFadeChain.fadeGraph(10f, 20f, 0f))
        assertEquals("afade=t=out:st=0:d=10", TrimFadeChain.fadeGraph(10f, 0f, 20f))
    }

    @Test
    fun unknownDurationKeepsOnlyTheFadeIn() {
        assertNull(TrimFadeChain.fadeGraph(null, 0f, 2f))
        assertEquals("afade=t=in:d=3", TrimFadeChain.fadeGraph(null, 3f, 0f))
        assertEquals("afade=t=in:d=3", TrimFadeChain.fadeGraph(null, 3f, 2f))
    }

    @Test
    fun fractionalFadesKeepShortestDecimalForm() {
        assertEquals("afade=t=in:d=0.5", TrimFadeChain.fadeGraph(10f, 0.5f, 0f))
        assertEquals("afade=t=out:st=9.25:d=0.75", TrimFadeChain.fadeGraph(10f, 0f, 0.75f))
    }

    @Test
    fun combinedChainOrdersEffectsBeforeFades() {
        assertEquals(
            "atempo=1.5,afade=t=in:d=2",
            TrimFadeChain.combinedChain("atempo=1.5", "afade=t=in:d=2"),
        )
        assertNull(TrimFadeChain.combinedChain(null, null))
        assertEquals("atempo=1.5", TrimFadeChain.combinedChain("atempo=1.5", null))
        assertEquals("afade=t=in:d=2", TrimFadeChain.combinedChain(null, "afade=t=in:d=2"))
    }
}