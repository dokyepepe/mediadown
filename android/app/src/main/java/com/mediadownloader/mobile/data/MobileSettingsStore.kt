package com.mediadownloader.mobile.data

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit

/**
 * Persisted network/file defaults used by the download engine. It shares the
 * `mobile_settings` preference file with the ViewModel so the foreground
 * service and the UI always agree on the same values.
 */
class MobileSettingsStore(private val preferences: SharedPreferences) {

    var proxy: String
        get() = preferences.getString(KEY_PROXY, "").orEmpty()
        set(value) = preferences.edit { putString(KEY_PROXY, value.trim()) }

    /** Download speed cap in KiB/s; 0 means unlimited. */
    var rateLimitKbps: Int
        get() = preferences.getInt(KEY_RATE_LIMIT_KBPS, 0)
        set(value) = preferences.edit { putInt(KEY_RATE_LIMIT_KBPS, value.coerceAtLeast(0)) }

    var fileNameTemplate: String
        get() = preferences.getString(KEY_FILE_NAME_TEMPLATE, "").orEmpty()
        set(value) = preferences.edit { putString(KEY_FILE_NAME_TEMPLATE, value) }

    var defaultVideoQuality: String
        get() = preferences.getString(KEY_DEFAULT_VIDEO_QUALITY, "best").orEmpty()
        set(value) = preferences.edit { putString(KEY_DEFAULT_VIDEO_QUALITY, value) }

    var defaultAudioBitrate: Int
        get() = preferences.getInt(KEY_DEFAULT_AUDIO_BITRATE, 192)
        set(value) = preferences.edit { putInt(KEY_DEFAULT_AUDIO_BITRATE, value) }

    var defaultVideoFormat: String
        get() = preferences.getString(KEY_DEFAULT_VIDEO_FORMAT, "mp4").orEmpty()
        set(value) = preferences.edit { putString(KEY_DEFAULT_VIDEO_FORMAT, value) }

    var defaultAudioFormat: String
        get() = preferences.getString(KEY_DEFAULT_AUDIO_FORMAT, "mp3").orEmpty()
        set(value) = preferences.edit { putString(KEY_DEFAULT_AUDIO_FORMAT, value) }

    /** Concurrent downloads the queue may run; clamped to 1..3 at read time. */
    var parallelDownloads: Int
        get() = preferences.getInt(KEY_PARALLEL_DOWNLOADS, 1).coerceIn(1, 3)
        set(value) = preferences.edit { putInt(KEY_PARALLEL_DOWNLOADS, value.coerceIn(1, 3)) }

    /** Pause the queue when the device is not on Wi-Fi. */
    var wifiOnly: Boolean
        get() = preferences.getBoolean(KEY_WIFI_ONLY, false)
        set(value) = preferences.edit { putBoolean(KEY_WIFI_ONLY, value) }

    /** Daily window (minutes since midnight) in which downloads may run. */
    var downloadWindowEnabled: Boolean
        get() = preferences.getBoolean(KEY_DOWNLOAD_WINDOW_ENABLED, false)
        set(value) = preferences.edit { putBoolean(KEY_DOWNLOAD_WINDOW_ENABLED, value) }

    var downloadWindowStartMin: Int
        get() = preferences.getInt(KEY_DOWNLOAD_WINDOW_START, 0).coerceIn(0, 1439)
        set(value) = preferences.edit { putInt(KEY_DOWNLOAD_WINDOW_START, value.coerceIn(0, 1439)) }

    var downloadWindowEndMin: Int
        get() = preferences.getInt(KEY_DOWNLOAD_WINDOW_END, 6 * 60).coerceIn(0, 1439)
        set(value) = preferences.edit { putInt(KEY_DOWNLOAD_WINDOW_END, value.coerceIn(0, 1439)) }

    /** Success notification extras. */
    var completionSound: Boolean
        get() = preferences.getBoolean(KEY_COMPLETION_SOUND, true)
        set(value) = preferences.edit { putBoolean(KEY_COMPLETION_SOUND, value) }

    var completionVibrate: Boolean
        get() = preferences.getBoolean(KEY_COMPLETION_VIBRATE, false)
        set(value) = preferences.edit { putBoolean(KEY_COMPLETION_VIBRATE, value) }

    /** Keep the process awake while any download runs (partial wake lock). */
    var keepAwakeDuringDownloads: Boolean
        get() = preferences.getBoolean(KEY_KEEP_AWAKE, false)
        set(value) = preferences.edit { putBoolean(KEY_KEEP_AWAKE, value) }

    /** Preferred media type the widget uses when "Colar e baixar" is tapped. */
    var widgetDownloadKindName: String
        get() = preferences.getString(KEY_WIDGET_KIND, MediaType.VIDEO.name) ?: MediaType.VIDEO.name
        set(value) = preferences.edit { putString(KEY_WIDGET_KIND, value) }

    companion object {
        const val PREFERENCES_NAME = "mobile_settings"

        private const val KEY_PROXY = "proxy_url"
        private const val KEY_RATE_LIMIT_KBPS = "rate_limit_kbps"
        private const val KEY_FILE_NAME_TEMPLATE = "file_name_template"
        private const val KEY_DEFAULT_VIDEO_QUALITY = "default_video_quality"
        private const val KEY_DEFAULT_AUDIO_BITRATE = "default_audio_bitrate"
        private const val KEY_DEFAULT_VIDEO_FORMAT = "default_video_format"
        private const val KEY_DEFAULT_AUDIO_FORMAT = "default_audio_format"
        private const val KEY_PARALLEL_DOWNLOADS = "parallel_downloads"
        private const val KEY_WIFI_ONLY = "wifi_only"
        private const val KEY_DOWNLOAD_WINDOW_ENABLED = "download_window_enabled"
        private const val KEY_DOWNLOAD_WINDOW_START = "download_window_start"
        private const val KEY_DOWNLOAD_WINDOW_END = "download_window_end"
        private const val KEY_COMPLETION_SOUND = "completion_sound"
        private const val KEY_COMPLETION_VIBRATE = "completion_vibrate"
        private const val KEY_KEEP_AWAKE = "keep_awake_during_downloads"
        private const val KEY_WIDGET_KIND = "widget_download_kind"

        fun open(context: Context): MobileSettingsStore =
            MobileSettingsStore(
                context.applicationContext.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)
            )
    }
}