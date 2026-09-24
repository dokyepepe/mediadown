package com.mediadownloader.mobile.data

import java.util.Locale
import kotlin.math.pow

/**
 * Immutable snapshot of the audio adjustments offered before a preview and on
 * downloads. Besides speed / pitch / volume it carries four native FFmpeg
 * toggles (bass boost, echo, tremolo and loudness normalization) that mirror
 * the desktop edition's chain builder.
 */
data class AudioEffects(
    val speed: Float = 1f,
    val semitones: Float = 0f,
    val volumePercent: Int = 100,
    val bass: Boolean = false,
    val echo: Boolean = false,
    val tremolo: Boolean = false,
    val normalize: Boolean = false,
) {
    val pitchRatio: Float
        get() = semitonesToRatio(semitones)

    val volumeFactor: Float
        get() = volumePercent / 100f

    val isIdentity: Boolean
        get() = speed == 1f && semitones == 0f && volumePercent == 100 &&
            !(bass || echo || tremolo || normalize)

    fun sanitized(): AudioEffects = AudioEffects(
        speed = speed.coerceIn(MIN_SPEED, MAX_SPEED),
        semitones = semitones.coerceIn(MIN_SEMITONES, MAX_SEMITONES),
        volumePercent = volumePercent.coerceIn(MIN_VOLUME_PERCENT, MAX_VOLUME_PERCENT),
        bass = bass,
        echo = echo,
        tremolo = tremolo,
        normalize = normalize,
    )

    /**
     * Mirror of the desktop editor's chain (build_audio_filters): pitch shifts
     * with asetrate + aresample + atempo=1/pitch, speed with atempo, the native
     * filters (bass, echo, tremolo), volume, and loudness normalization last.
     * Returns `null` when nothing is altered.
     */
    fun filterChain(): String? = AudioFilterChain.build(
        speed = speed,
        pitchRatio = pitchRatio,
        volumeFactor = volumeFactor,
        bass = bass,
        echo = echo,
        tremolo = tremolo,
        normalize = normalize,
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
 * Builds the FFmpeg `-af` filter graph for speed / pitch / volume / toggles
 * using the same stages as the desktop application. Pure and unit-testable.
 */
object AudioFilterChain {
    fun build(
        speed: Float,
        pitchRatio: Float,
        volumeFactor: Float,
        bass: Boolean = false,
        echo: Boolean = false,
        tremolo: Boolean = false,
        normalize: Boolean = false,
    ): String? {
        if (speed == 1f && pitchRatio == 1f && volumeFactor == 1f &&
            !(bass || echo || tremolo || normalize)
        ) {
            return null
        }
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
        if (bass) {
            filters += "bass=g=6:f=100"
        }
        if (echo) {
            filters += "aecho=0.7:0.7:300:0.3"
        }
        if (tremolo) {
            filters += "tremolo=f=5:d=0.25"
        }
        if (volumeFactor != 1f) {
            filters += "volume=${formatNumber(volumeFactor)}"
        }
        if (normalize) {
            filters += "loudnorm=I=-16:TP=-1.5:LRA=11"
        }
        return filters.joinToString(",")
    }

    /** Shortest decimal form accepted by FFmpeg (mirrors Python's `:g`). */
    private fun formatNumber(value: Float): String {
        val text = String.format(Locale.US, "%.6g", value.toDouble())
        return if ('e' in text || 'E' in text) text else text.trimEnd('0').trimEnd('.')
    }
}

/**
 * Mirror of the desktop editor's trim + fade graph (`trim_fade_filter` and the
 * fade handling in `edit_filter_chain`). Fades are clamped to the segment and
 * scaled down together when their sum would exceed the clip duration, so the
 * fade-out never starts before zero. Pure and unit-testable.
 */
object TrimFadeChain {
    /**
     * Builds the `afade` graph for a segment of `durationSeconds`, or `null`
     * when there is nothing to attenuate.
     *
     * When the segment duration is unknown (`null`) a fade-in is always safe
     * (it only ever softens the very start) but a fade-out needs a placement,
     * so without a known duration it is postponed rather than dropped onto the
     * stream start: fade out is omitted, keeping the fade-in.
     */
    fun fadeGraph(
        durationSeconds: Float?,
        fadeInSeconds: Float,
        fadeOutSeconds: Float,
    ): String? {
        val fadeIn = fadeInSeconds.coerceAtLeast(0f)
        val fadeOut = fadeOutSeconds.coerceAtLeast(0f)
        if (fadeIn <= 0f && fadeOut <= 0f) return null

        val duration = durationSeconds?.takeIf { it > 0f }
        if (duration == null) {
            return if (fadeIn > 0f) "afade=t=in:d=${formatSeconds(fadeIn)}" else null
        }

        var inFade = fadeIn
        var outFade = fadeOut
        val total = inFade + outFade
        if (total > duration && inFade > 0f && outFade > 0f) {
            val ratio = duration / total
            inFade *= ratio
            outFade *= ratio
        } else {
            inFade = minOf(inFade, duration)
            outFade = minOf(outFade, duration)
        }
        val parts = mutableListOf<String>()
        if (inFade > 0f) {
            parts += "afade=t=in:d=${formatSeconds(inFade)}"
        }
        if (outFade > 0f) {
            parts += "afade=t=out:st=${formatSeconds(duration - outFade)}:d=${formatSeconds(outFade)}"
        }
        return parts.joinToString(",") { it }.takeUnless(String::isBlank)
    }

    /**
     * Mirrors the desktop `edit_filter_chain`: the effect chain (speed / pitch /
     * volume / toggles) runs first so the fade envelope is applied to the final
     * waveform and is never re-normalized away by loudnorm.
     */
    fun combinedChain(effectsChain: String?, fadeGraph: String?): String? = when {
        effectsChain == null -> fadeGraph
        fadeGraph == null -> effectsChain
        else -> "$effectsChain,$fadeGraph"
    }

    private fun formatSeconds(value: Float): String {
        val text = String.format(Locale.US, "%.6g", value.toDouble())
        return if ('e' in text || 'E' in text) text else text.trimEnd('0').trimEnd('.')
    }
}