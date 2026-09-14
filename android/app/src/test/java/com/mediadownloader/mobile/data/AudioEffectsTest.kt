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
}