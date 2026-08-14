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

    @Test
    fun ytDlpActionsExposeOnlyTheSafeNextStep() {
        val available = SettingsUiState(
            updateState = YtDlpUpdateState.AVAILABLE,
            availableYtDlpVersion = "2026.08.12",
        )
        assertTrue(available.canInstallYtDlpUpdate)
        assertFalse(available.isYtDlpOperationBusy)

        val updating = available.copy(updateState = YtDlpUpdateState.UPDATING)
        assertFalse(updating.canInstallYtDlpUpdate)
        assertTrue(updating.isYtDlpOperationBusy)

        val rollingBack = available.copy(updateState = YtDlpUpdateState.ROLLING_BACK)
        assertTrue(rollingBack.isYtDlpOperationBusy)
    }
}
