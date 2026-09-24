package com.mediadownloader.mobile.ui

import org.junit.Assert.assertEquals
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
    fun siteScanRequiresUrlKindAndIdleState() {
        assertFalse(SiteFilesUiState().canScan)
        assertTrue(SiteFilesUiState(url = "https://example.com").canScan)
        assertFalse(
            SiteFilesUiState(
                url = "https://example.com",
                includePdfs = false,
                includeImages = false,
            ).canScan,
        )
        assertFalse(SiteFilesUiState(url = "https://example.com", isScanning = true).canScan)
    }

    @Test
    fun savedSiteFilesAreNotOfferedForDownloadAgain() {
        val ready = SiteFileUi(
            id = "one",
            url = "https://example.com/one.pdf",
            name = "one.pdf",
            sourceHost = "example.com",
            kind = SiteFileKindUi.PDF,
        )
        val saved = ready.copy(id = "two", status = SiteFileStatus.SAVED)
        val state = SiteFilesUiState(items = listOf(ready, saved))

        assertEquals(1, state.selectedCount)
        assertTrue(state.canDownload)
    }

    @Test
    fun qrCodeRequiresNonBlankUrl() {
        assertFalse(QrCodeUiState().canGenerate)
        assertTrue(QrCodeUiState(url = "https://example.com").canGenerate)
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

    @Test
    fun settingsExposeOneDestinationForEachFileCategory() {
        val state = SettingsUiState()

        assertEquals(3, state.storageLocations.size)
        assertTrue(state.storageLocations.all { it.locationLabel == "Downloads/MediaDownloader" })
    }

    @Test
    fun audioPreviewRequiresAnalyzedAudioAndIdlePlayer() {
        val audioPreview = preview.copy(supportsAudio = true)
        assertTrue(HomeUiState(preview = audioPreview).canPreviewAudio)
        assertFalse(HomeUiState(preview = audioPreview, isAudioPreviewRendering = true).canPreviewAudio)
        assertFalse(HomeUiState(preview = audioPreview, isAudioPreviewPlaying = true).canPreviewAudio)
        assertFalse(HomeUiState().canPreviewAudio)
        assertFalse(HomeUiState(preview = audioPreview.copy(supportsAudio = false)).canPreviewAudio)
    }

    @Test
    fun audioEffectsDefaultReflectsSliderValues() {
        assertTrue(HomeUiState().audioEffectsDefault)
        assertFalse(HomeUiState(audioSpeed = 1.5f).audioEffectsDefault)
        assertFalse(HomeUiState(audioPitchSemitones = 3f).audioEffectsDefault)
        assertFalse(HomeUiState(audioVolumePercent = 130).audioEffectsDefault)
        assertTrue(
            HomeUiState(audioSpeed = 1.5f, audioPitchSemitones = 3f, audioVolumePercent = 130)
                .copy(audioSpeed = 1f, audioPitchSemitones = 0f, audioVolumePercent = 100)
                .audioEffectsDefault,
        )
    }

    @Test
    fun audioTrimDefaultReflectsTrimAndFadeValues() {
        assertTrue(HomeUiState().audioTrimDefault)
        assertFalse(HomeUiState(trimStartSeconds = 5f).audioTrimDefault)
        assertFalse(HomeUiState(trimDurationSeconds = 10f).audioTrimDefault)
        assertFalse(HomeUiState(fadeInSeconds = 1f).audioTrimDefault)
        assertFalse(HomeUiState(fadeOutSeconds = 1f).audioTrimDefault)
        assertTrue(
            HomeUiState(trimStartSeconds = 5f, fadeInSeconds = 1f)
                .copy(trimStartSeconds = 0f, fadeInSeconds = 0f)
                .audioTrimDefault,
        )
    }

    @Test
    fun trimValuesDoNotAffectAudioEffectsDefault() {
        assertTrue(HomeUiState().audioEffectsDefault)
        assertTrue(HomeUiState(trimStartSeconds = 5f).audioEffectsDefault)
        assertFalse(HomeUiState(trimStartSeconds = 5f, audioSpeed = 1.5f).audioEffectsDefault)
    }

    @Test
    fun videoPreviewToggleOnlyOfferedWhenVideoExists() {
        assertFalse(HomeUiState(preview = preview.copy(supportsVideo = false)).canTogglePreviewVideo)
        assertTrue(HomeUiState(preview = preview).canTogglePreviewVideo)
        assertTrue(HomeUiState(preview = preview).previewUsesVideo)
        assertFalse(
            HomeUiState(preview = preview, previewUsesVideo = false).previewUsesVideo,
        )
    }

    @Test
    fun partialPlaylistDownloadRequiresASelection() {
        val playlist = MediaPreviewUi(
            title = "Playlist",
            sourceName = "Example",
            isPlaylist = true,
            playlistItemCount = 2,
            playlistItems = listOf(
                PlaylistItemUi(1, "one", "Item um", "https://example.com/a"),
                PlaylistItemUi(2, "two", "Item dois", "https://example.com/b"),
            ),
        )
        val base = HomeUiState(
            preview = playlist,
            selectedQualityId = "best",
            selectedFormatId = "mp4",
            downloadPlaylist = false,
        )
        assertFalse(base.canDownload)
        assertTrue(base.copy(playlistSelection = setOf(1)).canDownload)
        assertTrue(base.copy(playlistSelection = setOf(1, 2)).canDownload)
        assertTrue(base.copy(downloadPlaylist = true).canDownload)
        assertFalse(base.copy(playlistSelection = setOf(99)).canDownload)
    }

    @Test
    fun playlistSelectionUsesPlaylistIndexes() {
        val playlist = MediaPreviewUi(
            title = "Playlist",
            sourceName = "Example",
            isPlaylist = true,
            playlistItems = listOf(
                PlaylistItemUi(1, "one", "Item um", "https://example.com/a"),
                PlaylistItemUi(2, "two", "Item dois", "https://example.com/b"),
            ),
        )
        val state = HomeUiState(preview = playlist, playlistSelection = setOf(2))

        assertEquals(1, state.selectedPlaylistItems.size)
        assertEquals("Item dois", state.selectedPlaylistItems.single().title)
        assertEquals(emptyList<PlaylistItemUi>(), HomeUiState().selectedPlaylistItems)
    }

    @Test
    fun playlistTargetsResolvePerEntryOrToTheSource() {
        val playlist = MediaPreviewUi(
            title = "Playlist",
            sourceName = "Example",
            isPlaylist = true,
            playlistItems = listOf(
                PlaylistItemUi(1, "one", "Item um", "https://example.com/a"),
                PlaylistItemUi(2, "two", "Item dois", "https://example.com/b"),
            ),
        )
        val fallback = QueuedDownloadTarget("https://example.com/playlist", "Playlist")

        val partial = playlistDownloadTargets(
            preview = playlist,
            selection = setOf(1, 2),
            wholePlaylist = false,
            fallbackUrl = fallback.url,
            fallbackTitle = fallback.title,
        )
        assertEquals(2, partial.size)
        assertEquals("https://example.com/a", partial[0].url)
        assertEquals("https://example.com/b", partial[1].url)

        val single = playlistDownloadTargets(
            preview = playlist,
            selection = setOf(2),
            wholePlaylist = false,
            fallbackUrl = fallback.url,
            fallbackTitle = fallback.title,
        )
        assertEquals(listOf(QueuedDownloadTarget("https://example.com/b", "Item dois")), single)

        assertTrue(
            playlistDownloadTargets(
                preview = playlist,
                selection = emptySet(),
                wholePlaylist = false,
                fallbackUrl = fallback.url,
                fallbackTitle = fallback.title,
            ).isEmpty(),
        )

        // Whole playlist, non-playlists and playlists without entries fall back to the source.
        assertEquals(
            listOf(fallback),
            playlistDownloadTargets(
                preview = playlist,
                selection = emptySet(),
                wholePlaylist = true,
                fallbackUrl = fallback.url,
                fallbackTitle = fallback.title,
            ),
        )
        assertEquals(
            listOf(fallback),
            playlistDownloadTargets(
                preview = preview,
                selection = emptySet(),
                wholePlaylist = false,
                fallbackUrl = fallback.url,
                fallbackTitle = fallback.title,
            ),
        )
        assertEquals(
            listOf(fallback),
            playlistDownloadTargets(
                preview = playlist.copy(playlistItems = emptyList()),
                selection = emptySet(),
                wholePlaylist = false,
                fallbackUrl = fallback.url,
                fallbackTitle = fallback.title,
            ),
        )
    }
}
