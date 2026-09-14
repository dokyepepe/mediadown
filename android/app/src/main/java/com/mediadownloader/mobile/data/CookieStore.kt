package com.mediadownloader.mobile.data

import android.content.Context
import java.io.File

/**
 * Stores the user-provided cookies.txt as an app-private file so both the
 * foreground download service and the ViewModel can pass `--cookiefile` to
 * yt-dlp without depending on a persisted content Uri.
 */
class CookieStore(context: Context) {
    private val appContext = context.applicationContext
    private val preferences = appContext.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)

    /** The materialized cookies.txt when one is configured, or `null`. */
    val cookieFile: File?
        get() = if (preferences.getBoolean(KEY_ENABLED, false)) {
            File(appContext.filesDir, COOKIE_FILE_NAME).takeIf { it.isFile }
        } else {
            null
        }

    val label: String
        get() = preferences.getString(KEY_LABEL, null).orEmpty()

    fun set(source: File, label: String) {
        require(source.isFile) { "source must be a file" }
        setContent(source.readText(), label)
    }

    fun setContent(content: String, label: String) {
        val target = File(appContext.filesDir, COOKIE_FILE_NAME)
        target.parentFile?.mkdirs()
        target.writeText(content)
        preferences.edit()
            .putBoolean(KEY_ENABLED, true)
            .putString(KEY_LABEL, label)
            .apply()
    }

    fun clear() {
        File(appContext.filesDir, COOKIE_FILE_NAME).delete()
        preferences.edit().remove(KEY_ENABLED).remove(KEY_LABEL).apply()
    }

    private companion object {
        const val PREFERENCES_NAME = "cookie_store"
        const val KEY_ENABLED = "cookie_file_enabled"
        const val KEY_LABEL = "cookie_file_label"
        const val COOKIE_FILE_NAME = "cookies.txt"
    }
}