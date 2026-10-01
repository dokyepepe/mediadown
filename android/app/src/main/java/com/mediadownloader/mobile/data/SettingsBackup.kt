package com.mediadownloader.mobile.data

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/**
 * Backup/restore of the app settings and cookie profiles as a single JSON file.
 *
 * The Spotify session is intentionally left out (it stays encrypted in its own
 * preference file). Cookie profile records and their cookies.txt content are
 * both covered, so a restore really works after a wipe or on a new device.
 */
object SettingsBackup {

    const val FORMAT_VERSION = 1
    const val EXPORT_FILE_NAME = "media_downloader_settings_backup.json"

    private const val KEY_FORMAT = "format"
    private const val KEY_MOBILE_SETTINGS = "mobile_settings"
    private const val KEY_COOKIE_PROFILES = "cookie_profiles"
    private const val KEY_COOKIE_FILES = "cookie_files"

    fun export(context: Context, mobilePrefs: SharedPreferences): String {
        val cookieStore = CookieProfilesStore(context)
        val cookieFiles = JSONObject()
        cookieStore.list().forEach { profile ->
            cookieStore.contentFor(profile.id)?.let { cookieFiles.put(profile.id, it) }
        }
        val root = JSONObject().apply {
            put(KEY_FORMAT, FORMAT_VERSION)
            put(KEY_MOBILE_SETTINGS, prefsToJson(mobilePrefs))
            put(KEY_COOKIE_PROFILES, prefsToJson(mobileCookiesPrefs(context)))
            put(KEY_COOKIE_FILES, cookieFiles)
        }
        return root.toString(2)
    }

    fun import(context: Context, mobilePrefs: SharedPreferences, json: String) {
        val root = JSONObject(json)
        if (root.optInt(KEY_FORMAT, -1) != FORMAT_VERSION) {
            throw IllegalArgumentException()
        }
        applyJsonToPrefs(mobilePrefs, root.optJSONObject(KEY_MOBILE_SETTINGS))
        applyJsonToPrefs(mobileCookiesPrefs(context), root.optJSONObject(KEY_COOKIE_PROFILES))
        val cookieFiles = root.optJSONObject(KEY_COOKIE_FILES)
        if (cookieFiles != null) {
            val dir = File(context.filesDir, "cookies")
            dir.mkdirs()
            cookieFiles.keys().forEach { id ->
                val content = cookieFiles.optString(id)
                File(dir, "${id.trim()}.txt")
                    .takeIf { id.isNotBlank() }
                    ?.writeText(content)
            }
        }
    }

    private fun mobileCookiesPrefs(context: Context): SharedPreferences =
        context.getSharedPreferences("cookie_profiles", Context.MODE_PRIVATE)

    private fun prefsToJson(prefs: SharedPreferences): JSONObject {
        val out = JSONObject()
        prefs.all.forEach { (key, value) ->
            when (value) {
                is String -> out.put(key, value)
                is Int -> out.put(key, value)
                is Long -> out.put(key, value)
                is Boolean -> out.put(key, value)
                is Float -> out.put(key, value)
                is Set<*> -> {
                    val array = JSONArray()
                    @Suppress("UNCHECKED_CAST")
                    (value as? Set<String>)?.forEach { string -> array.put(string) }
                    out.put(key, array)
                }
            }
        }
        return out
    }

    private fun applyJsonToPrefs(prefs: SharedPreferences, json: JSONObject?) {
        if (json == null) return
        prefs.edit {
            clear()
            json.keys().forEach { key ->
                when (val value = json.opt(key)) {
                    is Boolean -> putBoolean(key, value)
                    is Int -> putInt(key, value)
                    is Long -> putLong(key, value)
                    is Double -> putFloat(key, value.toFloat())
                    is JSONArray -> {
                        val set = LinkedHashSet<String>()
                        for (i in 0 until value.length()) set.add(value.optString(i))
                        putStringSet(key, set)
                    }

                    else -> putString(key, value?.toString())
                }
            }
        }
    }
}