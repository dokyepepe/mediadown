package com.mediadownloader.mobile.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class QrCodeImageTest {
    @Test
    fun generatedQrCodeUsesRequestedResolutionAndPureContrast() {
        val qrCode = createQrCodePixels("https://example.com/media", size = 512)

        assertEquals(512, qrCode.size)
        assertEquals(512 * 512, qrCode.values.size)
        assertTrue(qrCode.values.any { it == QR_BLACK })
        assertTrue(qrCode.values.any { it == QR_WHITE })
        assertTrue(qrCode.values.all { it == QR_BLACK || it == QR_WHITE })
    }

    @Test
    fun generatedQrCodeKeepsWhiteQuietZoneAroundEveryEdge() {
        val qrCode = createQrCodePixels("https://example.com", size = 512)
        val last = qrCode.size - 1

        assertTrue((0 until qrCode.size).all { x -> qrCode.values[x] == QR_WHITE })
        assertTrue((0 until qrCode.size).all { x -> qrCode.values[last * qrCode.size + x] == QR_WHITE })
        assertTrue((0 until qrCode.size).all { y -> qrCode.values[y * qrCode.size] == QR_WHITE })
        assertTrue((0 until qrCode.size).all { y -> qrCode.values[y * qrCode.size + last] == QR_WHITE })
    }

    @Test
    fun differentUrlsProduceDifferentQrCodes() {
        val first = createQrCodePixels("https://example.com/one", size = 512)
        val second = createQrCodePixels("https://example.com/two", size = 512)

        assertFalse(first.values.contentEquals(second.values))
    }

    @Test
    fun qrCodeRejectsUnsafeSmallOutput() {
        assertThrows(IllegalArgumentException::class.java) {
            createQrCodePixels("https://example.com", size = 128)
        }
    }
}
