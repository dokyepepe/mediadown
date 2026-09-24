package com.mediadownloader.mobile.data

import android.content.Context
import android.content.SharedPreferences

/**
 * Persisted network/file defaults used by the download engine. It shares the
 * `mobile_settings` preference file with the ViewModel so the foreground
 * service and the UI always agree on the same values.
 */
class MobileSettingsStore(private val preferences: SharedPreferences) {

    var proxy: String
        get() = preferences.getString(KEY_PROXY, "").orEmpty()
        set(value) = preferences.edit().putString(KEY_PROXY, value.trim()).apply()

    /** Download speed cap in KiB/s; 0 means unlimited. */
    var rateLimitKbps: Int
        get() = preferences.getInt(KEY_RATE_LIMIT_KBPS, 0)
        set(value) = preferences.edit().putInt(KEY_RATE_LIMIT_KBPS, value.coerceAtLeast(0)).apply()

    var fileNameTemplate: String
        get() = preferences.getString(KEY_FILE_NAME_TEMPLATE, "").orEmpty()
        set(value) = preferences.edit().putString(KEY_FILE_NAME_TEMPLATE, value).apply()

    var defaultVideoQuality: String
        get() = preferences.getString(KEY_DEFAULT_VIDEO_QUALITY, "best").orEmpty()
        set(value) = preferences.edit().putString(KEY_DEFAULT_VIDEO_QUALITY, value).apply()

    var defaultAudioBitrate: Int
        get() = preferences.getInt(KEY_DEFAULT_AUDIO_BITRATE, 192)
        set(value) = preferences.edit().putInt(KEY_DEFAULT_AUDIO_BITRATE, value).apply()

    var defaultVideoFormat: String
        get() = preferences.getString(KEY_DEFAULT_VIDEO_FORMAT, "mp4").orEmpty()
        set(value) = preferences.edit().putString(KEY_DEFAULT_VIDEO_FORMAT, value).apply()

    var defaultAudioFormat: String
        get() = preferences.getString(KEY_DEFAULT_AUDIO_FORMAT, "mp3").orEmpty()
        set(value) = preferences.edit().putString(KEY_DEFAULT_AUDIO_FORMAT, value).apply()

    companion object {
        const val PREFERENCES_NAME = "mobile_settings"

        private const val KEY_PROXY = "proxy_url"
        private const val KEY_RATE_LIMIT_KBPS = "rate_limit_kbps"
        private const val KEY_FILE_NAME_TEMPLATE = "file_name_template"
        private const val KEY_DEFAULT_VIDEO_QUALITY = "default_video_quality"
        private const val KEY_DEFAULT_AUDIO_BITRATE = "default_audio_bitrate"
        private const val KEY_DEFAULT_VIDEO_FORMAT = "default_video_format"
        private const val KEY_DEFAULT_AUDIO_FORMAT = "default_audio_format"

        fun open(context: Context): MobileSettingsStore =
            MobileSettingsStore(
                context.applicationContext.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)
            )
    }
}