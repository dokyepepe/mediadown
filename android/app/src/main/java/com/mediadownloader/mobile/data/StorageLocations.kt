package com.mediadownloader.mobile.data

import android.content.Context
import java.net.URLDecoder
import java.nio.charset.StandardCharsets

enum class StorageCategory(val preferenceKey: String, val label: String) {
    VIDEO("storage_video_tree_uri", "Vídeos"),
    AUDIO("storage_audio_tree_uri", "Áudios"),
    SITE_FILES("storage_site_files_tree_uri", "PDFs e imagens"),
}

class StorageLocationStore(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences(
        PREFERENCES_NAME,
        Context.MODE_PRIVATE,
    )

    fun uri(category: StorageCategory): String? = preferences
        .getString(category.preferenceKey, null)
        ?.takeIf(String::isNotBlank)

    fun set(category: StorageCategory, uri: String) {
        preferences.edit().putString(category.preferenceKey, uri).apply()
    }

    fun reset(category: StorageCategory) {
        preferences.edit().remove(category.preferenceKey).apply()
    }

    fun label(category: StorageCategory): String = uri(category)?.let(::treeLocationLabel)
        ?: DEFAULT_LOCATION_LABEL

    companion object {
        const val PREFERENCES_NAME = "mobile_settings"
        const val DEFAULT_LOCATION_LABEL = "Downloads/MediaDownloader"

        fun treeLocationLabel(rawUri: String): String {
            val encodedDocumentId = rawUri.substringAfter("/tree/", "")
                .substringBefore('/')
            val documentId = runCatching {
                URLDecoder.decode(encodedDocumentId, StandardCharsets.UTF_8.name())
            }.getOrDefault(encodedDocumentId)
            val relativePath = documentId.substringAfter(':', documentId).trim('/')
            return relativePath.takeIf(String::isNotBlank) ?: "Pasta selecionada"
        }
    }
}
