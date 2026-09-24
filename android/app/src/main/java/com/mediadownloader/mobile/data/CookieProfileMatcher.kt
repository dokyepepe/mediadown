package com.mediadownloader.mobile.data

/** Cookie profile definition used only for URL matching (see [CookieProfileMatcher]). */
data class CookieProfileRule(
    val id: String,
    val hosts: List<String> = emptyList(),
)

/**
 * Pure host-matching logic that decides which cookies.txt profile applies to a
 * URL. Specific-host profiles take precedence over the global profile
 * (`hosts == empty`); a host matches when it equals the configured host or is a
 * sub-domain of it, so `www.youtube.com` matches a rule for `youtube.com`.
 */
object CookieProfileMatcher {

    /** Returns the winning profile id, or null when no rule matches. */
    fun matchingRuleId(rules: List<CookieProfileRule>, url: String): String? {
        val host = extractHost(url)
        if (host != null) {
            val specific = rules.firstOrNull { rule ->
                rule.hosts.isNotEmpty() && rule.hosts.any { matches(host, it) }
            }
            if (specific != null) return specific.id
        }
        return rules.firstOrNull { rule -> rule.hosts.isEmpty() }?.id
    }

    /** Normalizes a configured host pattern to a comparable root host. */
    fun normalize(pattern: String): String {
        val withoutScheme = pattern
            .substringAfterLast("://", pattern)
            .substringAfterLast('@', pattern)
            .substringBefore(':')
            .removePrefix("[")
            .removeSuffix("]")
            .removePrefix("www.")
            .trim()
            .trimEnd('/')
        return if (withoutScheme.isBlank()) "" else withoutScheme
    }

    private fun extractHost(url: String): String? {
        if (!url.contains("://")) return null
        val rest = url.substringAfter("://", url)
        val afterUserInfo = rest.substringAfterLast('@', rest)
        val hostAndPort = afterUserInfo.takeWhile { it != '/' && it != '?' && it != '#' }
        val host = hostAndPort
            .removePrefix("[")
            .removeSuffix("]")
            .substringBefore(':')
            .lowercase()
        return host.ifBlank { null }
    }

    private fun matches(urlHost: String, pattern: String): Boolean {
        val normalized = normalize(pattern)
        if (normalized.isEmpty()) return false
        val host = urlHost.lowercase().removePrefix("www.")
        val target = normalized.removePrefix("www.")
        return host == target || host.endsWith(".$target")
    }
}