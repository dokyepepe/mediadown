package com.mediadownloader.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Test

class DefaultsTest {

    @Test
    fun preferredChoiceWinsWhenAvailable() {
        val choices = listOf("best", "1080p", "480p")
        assertEquals("1080p", resolveChoiceId(choices, "1080p", "best"))
    }

    @Test
    fun unknownPreferredFallsBackToRecommended() {
        val choices = listOf("best", "1080p", "480p")
        assertEquals("480p", resolveChoiceId(choices, "999p", "480p"))
    }

    @Test
    fun nullPreferredUsesRecommended() {
        assertEquals("best", resolveChoiceId(listOf("best", "1080p"), null, "best"))
    }

    @Test
    fun emptyChoicesFallsBackToRecommended() {
        assertEquals("best", resolveChoiceId(emptyList(), "1080p", "best"))
    }

    @Test
    fun blankTemplateFallsBackToDefault() {
        assertEquals(FileNameTemplates.DEFAULT_TEMPLATE, FileNameTemplates.resolved(""))
        assertEquals(FileNameTemplates.DEFAULT_TEMPLATE, FileNameTemplates.resolved("   "))
        assertEquals(FileNameTemplates.DEFAULT_TEMPLATE, FileNameTemplates.resolved(null))
    }

    @Test
    fun templateKeepsItsOwnExtensionToken() {
        val template = "%(title)s [%(id)s].%(ext)s"
        assertEquals(template, FileNameTemplates.resolved(template))
    }

    @Test
    fun templateWithoutExtensionTokenGetsOneAppended() {
        assertEquals("%(title)s.%(ext)s", FileNameTemplates.resolved("%(title)s"))
        assertEquals("%(title)s.%(ext)s", FileNameTemplates.resolved("  %(title)s  "))
    }

    @Test
    fun partialExtensionTokenIsTreatedAsMissing() {
        assertEquals("%(title).180B.%(ext)s", FileNameTemplates.resolved("%(title).180B"))
    }
}