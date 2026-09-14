package com.mediadownloader.mobile.data

import java.util.Locale
import kotlin.math.pow

/** Immutable snapshot of the three audio adjustments offered before a preview. */
data class AudioEffects(
    val speed: Float = 1f,
    val semitones: Float = 0f,
    val volumePercent: Int = 100,
) {
    val pitchRatio: Float
        get() = semitonesToRatio(semitones)

    val volumeFactor: Float
        get() = volumePercent / 100f

    val isIdentity: Boolean
        get() = speed == 1f && semitones == 0f && volumePercent == 100

    fun sanitized(): AudioEffects = AudioEffects(
        speed = speed.coerceIn(MIN_SPEED, MAX_SPEED),
        semitones = semitones.coerceIn(MIN_SEMITONES, MAX_SEMITONES),
        volumePercent = volumePercent.coerceIn(MIN_VOLUME_PERCENT, MAX_VOLUME_PERCENT),
    )

    /**
     * Mirror of the desktop editor's chain (build_audio_filters): pitch shifts
     * with asetrate + aresample + atempo=1/pitch, speed with atempo, and volume
     * last. Returns `null` when nothing is altered.
     */
    fun filterChain(): String? = AudioFilterChain.build(
        speed = speed,
        pitchRatio = pitchRatio,
        volumeFactor = volumeFactor,
    )

    companion object {
        const val MIN_SPEED = 0.5f
        const val MAX_SPEED = 2.0f
        const val MIN_SEMITONES = -12f
        const val MAX_SEMITONES = 12f
        const val MIN_VOLUME_PERCENT = 5
        const val MAX_VOLUME_PERCENT = 200
        const val DEFAULT_SEMITONES = 0f
    }
}

fun semitonesToRatio(semitones: Float): Float = 2f.pow(semitones / 12f)

/**
 * Builds the FFmpeg `-af` filter graph for speed / pitch / volume using the
 * same stages as the desktop application. Pure and unit-testable.
 */
object AudioFilterChain {
    fun build(speed: Float, pitchRatio: Float, volumeFactor: Float): String? {
        if (speed == 1f && pitchRatio == 1f && volumeFactor == 1f) return null
        val filters = mutableListOf<String>()
        if (pitchRatio != 1f) {
            filters += listOf(
                "aresample=44100",
                "asetrate=${formatNumber(44100f * pitchRatio)}",
                "aresample=44100",
                "atempo=${formatNumber(1f / pitchRatio)}",
            )
        }
        if (speed != 1f) {
            filters += "atempo=${formatNumber(speed)}"
        }
        if (volumeFactor != 1f) {
            filters += "volume=${formatNumber(volumeFactor)}"
        }
        return filters.joinToString(",")
    }

    /** Shortest decimal form accepted by FFmpeg (mirrors Python's `:g`). */
    private fun formatNumber(value: Float): String {
        val text = String.format(Locale.US, "%.6g", value.toDouble())
        return if ('e' in text || 'E' in text) text else text.trimEnd('0').trimEnd('.')
    }
}