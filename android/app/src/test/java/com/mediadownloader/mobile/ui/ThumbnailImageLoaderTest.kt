package com.mediadownloader.mobile.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ThumbnailImageLoaderTest {
    @Test
    fun `uses browser headers and the media page as referer`() {
        val headers = ThumbnailImageLoader.requestHeaders("https://example.com/watch/123")

        assertTrue(headers.getValue("User-Agent").startsWith("Mozilla/5.0"))
        assertTrue(headers.getValue("Accept").contains("image/webp"))
        assertEquals("https://example.com/watch/123", headers["Referer"])
    }

    @Test
    fun `does not forward a non-http referer`() {
        val headers = ThumbnailImageLoader.requestHeaders("file:///private/source")

        assertFalse(headers.containsKey("Referer"))
    }
}
