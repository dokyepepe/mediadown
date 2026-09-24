package com.mediadownloader.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class UrlExtractionTest {

    @Test
    fun rejectsNonHttpSchemes() {
        assertFalse(UrlExtraction.isValidHttpUrl("ftp://example.com/x"))
        assertFalse(UrlExtraction.isValidHttpUrl("file:///tmp/a.mp3"))
        assertFalse(UrlExtraction.isValidHttpUrl("example.com/watch?v=1"))
        assertFalse(UrlExtraction.isValidHttpUrl(""))
    }

    @Test
    fun acceptsHttpAndHttpsWithHost() {
        assertTrue(UrlExtraction.isValidHttpUrl("https://www.youtube.com/watch?v=abc"))
        assertTrue(UrlExtraction.isValidHttpUrl("http://example.com"))
        assertTrue(UrlExtraction.isValidHttpUrl("  https://example.com  "))
    }

    @Test
    fun schemeWithoutHostIsInvalid() {
        assertFalse(UrlExtraction.isValidHttpUrl("https://"))
        assertFalse(UrlExtraction.isValidHttpUrl("https://?q=1"))
    }

    @Test
    fun extractsUrlsFromShareStyleText() {
        val text = "Veja: https://www.youtube.com/watch?v=abc e https://example.com/a"
        assertEquals(
            listOf("https://www.youtube.com/watch?v=abc", "https://example.com/a"),
            UrlExtraction.extractHttpUrls(text),
        )
    }

    @Test
    fun extractsMultipleUrlsInOrderWithoutDuplicates() {
        val text = "https://a.com/1 https://a.com/1 https://b.com/2 https://a.com/3"
        assertEquals(
            listOf("https://a.com/1", "https://b.com/2", "https://a.com/3"),
            UrlExtraction.extractHttpUrls(text),
        )
    }

    @Test
    fun stripsTrailingSentencePunctuation() {
        val text = "Baixe aqui: https://example.com/video.mp4. Depois curta!"
        assertEquals(listOf("https://example.com/video.mp4"), UrlExtraction.extractHttpUrls(text))
    }

    @Test
    fun extractHttpUrlReturnsFirstOrNull() {
        assertEquals(
            "https://a.com/1",
            UrlExtraction.extractHttpUrl("x https://a.com/1 e https://b.com/2"),
        )
        assertNull(UrlExtraction.extractHttpUrl("nada aqui"))
    }
}