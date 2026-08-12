package com.mediadownloader.mobile.ui

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MobileUiStateTest {
    private val preview = MediaPreviewUi(
        title = "Example",
        sourceName = "Example",
    )

    @Test
    fun analyzeRequiresNonBlankUrlAndIdleState() {
        assertFalse(HomeUiState().canAnalyze)
        assertTrue(HomeUiState(url = "https://example.com").canAnalyze)
        assertFalse(HomeUiState(url = "https://example.com", isAnalyzing = true).canAnalyze)
    }

    @Test
    fun downloadRequiresPreviewQualityAndFormat() {
        assertFalse(HomeUiState(preview = preview).canDownload)
        assertTrue(
            HomeUiState(
                preview = preview,
                selectedQualityId = "best",
                selectedFormatId = "mp4",
            ).canDownload,
        )
    }
}
