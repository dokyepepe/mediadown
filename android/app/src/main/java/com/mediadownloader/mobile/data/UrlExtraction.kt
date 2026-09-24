package com.mediadownloader.mobile.data

/**
 * Pure URL helpers shared by the ViewModel, the clipboards keeps the extraction
 * and validation rules unit-testable on the JVM.
 */
object UrlExtraction {

    /** Matches http(s) links inside arbitrary text (share intents, clipboard). */
    private val URL_REGEX = Regex(
        """https?://[A-Za-z0-9\-._~%!$&'()*+,;=:@]+(?:/[A-Za-z0-9\-._~%!$&'()*+,;=:@/?&=]*)?"""
    )

    /** True when the value looks like a usable http(s) URL with a host. */
    fun isValidHttpUrl(value: String): Boolean {
        val trimmed = value.trim()
        if (!trimmed.startsWith("http://", ignoreCase = true) &&
            !trimmed.startsWith("https://", ignoreCase = true)
        ) {
            return false
        }
        val afterScheme = trimmed.substring(trimmed.indexOf("://") + 3)
        val host = afterScheme.takeWhile { it != '/' && it != '?' && it != '#' }
        return host.isNotBlank()
    }

    /**
     * Returns every http(s) URL found in [text], de-duplicated and in first
     * occurrence order. Useful for bulk downloads from share intents and for
     * pasting text that contains several links.
     */
    fun extractHttpUrls(text: String): List<String> = URL_REGEX
        .findAll(text)
        .map { it.value.trim().trimEnd('.') }
        .distinct()
        .toList()

    /** Convenience alias used by the single-URL paste/analyze flow. */
    fun extractHttpUrl(text: String): String? = extractHttpUrls(text).firstOrNull()
}