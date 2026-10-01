package com.mediadownloader.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DownloadGateTest {

    @Test
    fun contiguousWindowContainsNow() {
        val contents = listOf(
            8 * 60,   // 08:00 start boundary
            12 * 60,  // middle
            22 * 60 - 1 // end boundary - 1
        )
        contents.forEach { now ->
            assertTrue("deveria conter $now", DownloadGate.windowContains(8 * 60, 22 * 60, now))
        }
    }

    @Test
    fun contiguousWindowExcludesOutside() {
        listOf(0, 8 * 60 - 1, 22 * 60, 23 * 60 + 59).forEach { now ->
            assertFalse("não deveria conter $now", DownloadGate.windowContains(8 * 60, 22 * 60, now))
        }
    }

    @Test
    fun overnightWindowWrapsMidnight() {
        // Janela 22:00–06:00
        listOf(22 * 60, 23 * 60 + 59, 0, 5 * 60 + 59).forEach { now ->
            assertTrue("deveria conter $now", DownloadGate.windowContains(22 * 60, 6 * 60, now))
        }
        listOf(6 * 60, 10 * 60, 21 * 60 + 59).forEach { now ->
            assertFalse("não deveria conter $now", DownloadGate.windowContains(22 * 60, 6 * 60, now))
        }
    }

    @Test
    fun equalBoundsAlwaysAllowed() {
        listOf(0, 6 * 60, 12 * 60 + 30, 23 * 60 + 59).forEach { now ->
            assertTrue(DownloadGate.windowContains(6 * 60, 6 * 60, now))
        }
    }

    @Test
    fun hhmmFormatsAndClamps() {
        assertEquals("00:00", DownloadGate.hhmm(0))
        assertEquals("07:05", DownloadGate.hhmm(425))
        assertEquals("14:30", DownloadGate.hhmm(870))
        assertEquals("23:59", DownloadGate.hhmm(1439))
        assertEquals("00:00", DownloadGate.hhmm(-5))
        assertEquals("23:59", DownloadGate.hhmm(9999))
    }

    @Test
    fun labelUsesWindowTimes() {
        assertEquals("Janela agendada (22:00–06:00)", DownloadGate.windowLabel(22 * 60, 6 * 60))
        assertEquals("Janela agendada (08:00–22:00)", DownloadGate.windowLabel(8 * 60, 22 * 60))
    }
}