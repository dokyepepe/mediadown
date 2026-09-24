package com.mediadownloader.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CookieProfileMatcherTest {

    private val rules = listOf(
        CookieProfileRule(id = "global", hosts = emptyList()),
        CookieProfileRule(id = "youtube", hosts = listOf("youtube.com")),
        CookieProfileRule(id = "all-google", hosts = listOf("google.com", "gstatic.com")),
    )

    @Test
    fun exactHostMatchesSpecificRule() {
        assertEquals("youtube", CookieProfileMatcher.matchingRuleId(rules, "https://youtube.com/watch?v=1"))
    }

    @Test
    fun subdomainMatchesConfiguredRoot() {
        assertEquals("youtube", CookieProfileMatcher.matchingRuleId(rules, "https://www.youtube.com/watch?v=1"))
        assertEquals("youtube", CookieProfileMatcher.matchingRuleId(rules, "https://music.youtube.com/playlist"))
    }

    @Test
    fun configureWithWwwMatchesSameRule() {
        val withWww = listOf(CookieProfileRule(id = "yt", hosts = listOf("www.youtube.com")))
        assertEquals("yt", CookieProfileMatcher.matchingRuleId(withWww, "https://youtube.com/a"))
        assertEquals("yt", CookieProfileMatcher.matchingRuleId(withWww, "https://www.youtube.com/a"))
    }

    @Test
    fun schemePortAndUserInfoAreIgnored() {
        assertEquals("youtube", CookieProfileMatcher.matchingRuleId(rules, "http://user:pass@youtube.com:8443/watch?v=1"))
    }

    @Test
    fun secondConfiguredHostAlsoMatches() {
        assertEquals("all-google", CookieProfileMatcher.matchingRuleId(rules, "https://cdn.gstatic.com/x"))
    }

    @Test
    fun specificRuleBeatsGlobalFallback() {
        assertEquals("youtube", CookieProfileMatcher.matchingRuleId(rules, "https://youtube.com/v"))
    }

    @Test
    fun unrelatedHostFallsBackToGlobalProfile() {
        assertEquals("global", CookieProfileMatcher.matchingRuleId(rules, "https://vimeo.com/1"))
    }

    @Test
    fun noRulesAndNoMatchReturnsNull() {
        assertNull(CookieProfileMatcher.matchingRuleId(emptyList(), "https://example.com"))
    }

    @Test
    fun withoutGlobalNoMatchReturnsNull() {
        val onlySpecific = rules.filter { it.id != "global" }
        assertNull(CookieProfileMatcher.matchingRuleId(onlySpecific, "https://vimeo.com/1"))
    }

    @Test
    fun firstMatchingSpecificRuleWins() {
        val overlap = listOf(
            CookieProfileRule(id = "first", hosts = listOf("example.com")),
            CookieProfileRule(id = "second", hosts = listOf("sub.example.com")),
        )
        assertEquals("first", CookieProfileMatcher.matchingRuleId(overlap, "https://sub.example.com/a"))
    }

    @Test
    fun invalidUrlFallsBackToGlobalOnly() {
        val onlySpecific = rules.filter { it.id != "global" }
        assertNull(CookieProfileMatcher.matchingRuleId(onlySpecific, "not a url"))
        assertEquals("global", CookieProfileMatcher.matchingRuleId(rules, "not a url"))
        val globalOnly = listOf(CookieProfileRule(id = "g", hosts = emptyList()))
        assertEquals("g", CookieProfileMatcher.matchingRuleId(globalOnly, "not a url"))
    }
}