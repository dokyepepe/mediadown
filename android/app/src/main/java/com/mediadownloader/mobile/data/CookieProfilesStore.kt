package com.mediadownloader.mobile.data

import android.content.Context
import androidx.core.content.edit
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** A persisted cookies.txt profile. [hosts] empty means "all sites" (global). */
data class CookieProfile(
    val id: String,
    val label: String,
    val hosts: List<String> = emptyList(),
    /** Optional yt-dlp `--impersonate` target (e.g. "chrome", "safari", "edge"). */
    val impersonate: String? = null,
)

/**
 * Multi-file cookie store. Each profile is materialized as a private cookies.txt
 * inside `filesDir/cookies/<id>.txt`, while the record (id + label + host list)
 * lives in preferences. The single-file cookie settings of older builds are
 * migrated to the global profile automatically.
 */
class CookieProfilesStore(context: Context) {
    private val appContext = context.applicationContext
    private val preferences = appContext.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)
    private val cookiesDir = File(appContext.filesDir, DIR_COOKIES)

    init {
        migrateLegacyGlobalCookie()
    }

    val globalProfile: CookieProfile?
        get() = list().firstOrNull { it.hosts.isEmpty() }

    val subProfiles: List<CookieProfile>
        get() = list().filter { it.hosts.isNotEmpty() }

    fun list(): List<CookieProfile> {
        val raw = preferences.getString(KEY_PROFILES_JSON, null) ?: return emptyList()
        return try {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val obj = array.getJSONObject(i)
                    val hosts = obj.optJSONArray("hosts")?.let { hostsArray ->
                        buildList { for (j in 0 until hostsArray.length()) add(hostsArray.getString(j)) }
                    }.orEmpty()
                    add(
                        CookieProfile(
                            id = obj.getString("id"),
                            label = obj.getString("label"),
                            hosts = hosts,
                            impersonate = obj.optString("impersonate").nullIfBlank(),
                        ),
                    )
                }
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    fun labelFor(id: String): String = list().firstOrNull { it.id == id }?.label.orEmpty()

    /** Materialized content file for a profile, when record + file exist. */
    fun fileFor(id: String): File? =
        if (list().any { it.id == id }) File(cookiesDir, "$id.txt").takeIf { it.isFile } else null

    /** Global cookies.txt used by older code paths, or `null` when absent. */
    val globalFile: File?
        get() = globalProfile?.let { File(cookiesDir, "${it.id}.txt").takeIf { f -> f.isFile } }

    /** Content of a profile file as text: null when absent/read-error. */
    fun contentFor(id: String): String? = fileFor(id)?.takeIf { it.isFile }?.readText()

    fun upsert(profile: CookieProfile, content: String? = null) {
        var records = list().filterNot { it.id == profile.id }.toMutableList()
        records.add(profile)
        writeRecords(records)
        if (content != null) {
            val target = File(cookiesDir, "${profile.id}.txt")
            target.parentFile?.mkdirs()
            target.writeText(content)
        }
    }

    fun updateHosts(id: String, hosts: List<String>) {
        val current = list().firstOrNull { it.id == id } ?: return
        upsert(current.copy(hosts = hosts.distinct().map(String::trim).filter(String::isNotBlank)))
    }

    fun updateImpersonate(id: String, impersonate: String?) {
        val current = list().firstOrNull { it.id == id } ?: return
        upsert(current.copy(impersonate = impersonate?.trim().nullIfBlank()))
    }

    fun remove(id: String) {
        File(cookiesDir, "$id.txt").delete()
        writeRecords(list().filterNot { it.id == id })
    }

    fun clearAll() {
        cookiesDir.listFiles()?.forEach { it.delete() }
        preferences.edit { remove(KEY_PROFILES_JSON) }
    }

    /** Picks the profile that applies to [url] via [CookieProfileMatcher]. */
    fun resolveForUrl(url: String): CookieProfile? {
        val id = CookieProfileMatcher.matchingRuleId(
            rules = list().map { CookieProfileRule(it.id, it.hosts) },
            url = url,
        ) ?: return null
        return list().firstOrNull { it.id == id }
    }

    private fun writeRecords(records: List<CookieProfile>) {
        val array = JSONArray()
        for (record in records) {
            val hosts = JSONArray()
            record.hosts.forEach { hosts.put(it) }
            val json = JSONObject()
                .put("id", record.id)
                .put("label", record.label)
                .put("hosts", hosts)
            if (record.impersonate != null) {
                json.put("impersonate", record.impersonate)
            }
            array.put(json)
        }
        preferences.edit { putString(KEY_PROFILES_JSON, array.toString()) }
    }

    private fun String?.nullIfBlank(): String? = this?.takeIf(String::isNotBlank)

    private fun migrateLegacyGlobalCookie() {
        val legacy = appContext.getSharedPreferences(LEGACY_PREFS_NAME, Context.MODE_PRIVATE)
        val legacyEnabled = legacy.getBoolean(LEGACY_KEY_ENABLED, false)
        val legacyFile = File(appContext.filesDir, LEGACY_COOKIE_FILE)
        if (!legacyEnabled || !legacyFile.isFile) return
        if (list().any { it.id == DEFAULT_ID }) return
        val content = legacyFile.readText()
        File(cookiesDir, "$DEFAULT_ID.txt").let { target ->
            target.parentFile?.mkdirs()
            target.writeText(content)
        }
        writeRecords(listOf(CookieProfile(DEFAULT_ID, legacy.getString(LEGACY_KEY_LABEL, null).orEmpty())))
        legacyFile.delete()
        legacy.edit { remove(LEGACY_KEY_ENABLED); remove(LEGACY_KEY_LABEL) }
    }

    companion object {
        const val DEFAULT_PROFILE_ID = "default"
        private const val DEFAULT_ID = DEFAULT_PROFILE_ID

        private const val PREFERENCES_NAME = "cookie_profiles"
        private const val KEY_PROFILES_JSON = "profiles_json"
        private const val DIR_COOKIES = "cookies"
        private const val LEGACY_PREFS_NAME = "cookie_store"
        private const val LEGACY_KEY_ENABLED = "cookie_file_enabled"
        private const val LEGACY_KEY_LABEL = "cookie_file_label"
        private const val LEGACY_COOKIE_FILE = "cookies.txt"
    }
}