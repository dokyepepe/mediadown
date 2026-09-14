package com.mediadownloader.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CookieDiagnosticsTest {

    private val netscapeHeader = "# Netscape HTTP Cookie File"

    @Test
    fun emptyContentReportsNoCookies() {
        val check = CookieDiagnostics.check("", "cookies.txt")
        assertFalse(check.ok)
        assertEquals(0, check.cookieCount)
        assertFalse(check.loggedIn)
    }

    @Test
    fun headerCommentAloneReportsNoCookies() {
        val check = CookieDiagnostics.check(netscapeHeader, "cookies.txt")
        assertFalse(check.ok)
    }

    @Test
    fun parsesNetscapeCookieNames() {
        val content = """
            $netscapeHeader
            #HttpOnly_.youtube.com	TRUE	/	TRUE	2337244126	SID	fake-session
            .example.com	TRUE	/	FALSE	0	pref	color=blue
        """.trimIndent()
        val check = CookieDiagnostics.check(content, "cookies.txt")
        assertTrue(check.ok)
        assertEquals(2, check.cookieCount)
    }

    @Test
    fun maxAgeJumpedLinesAreSkipped() {
        val content = """
            .youtube.com	TRUE	/	FALSE	4102444800	SAPISID	fake
            this line has no tabs
            end
        """.trimIndent()
        val names = CookieDiagnostics.cookieNames(content)
        assertEquals(listOf("SAPISID"), names)
    }

    @Test
    fun recognisesYouTubeSessionCookies() {
        val content = buildString {
            appendLine(netscapeHeader)
            appendLine(".youtube.com\tTRUE\t/\tTRUE\t2337244126\tSID\tfake")
            appendLine(".youtube.com\tTRUE\t/\tFALSE\t2337244126\t__Secure-3PAPISID\tfake")
        }
        val check = CookieDiagnostics.check(content, "youtube.txt")
        assertTrue(check.ok)
        assertTrue(check.loggedIn)
        assertEquals(2, check.cookieCount)
    }

    @Test
    fun anonymousCookiesAreNotLoggedIn() {
        val content = buildString {
            appendLine(netscapeHeader)
            appendLine(".example.com\tTRUE\t/\tFALSE\t0\tpref\tcolor=blue")
        }
        val check = CookieDiagnostics.check(content, "cookies.txt")
        assertTrue(check.ok)
        assertFalse(check.loggedIn)
        assertEquals(1, check.cookieCount)
    }

    @Test
    fun messageMentionsConfiguredLabel() {
        val check = CookieDiagnostics.check("", "minhas-cookies.txt")
        assertTrue(check.message.contains("minhas-cookies.txt"))
    }
}