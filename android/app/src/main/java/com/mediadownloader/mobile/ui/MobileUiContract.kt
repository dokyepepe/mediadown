package com.mediadownloader.mobile.ui

import android.net.Uri
import com.mediadownloader.mobile.R
import com.mediadownloader.mobile.data.AudioFormat
import com.mediadownloader.mobile.data.CookieCheckUi
import com.mediadownloader.mobile.media.SoundRole
import com.mediadownloader.mobile.data.StorageCategory

import kotlinx.coroutines.flow.StateFlow

/**
 * Ponte pequena entre a UI Compose e a implementação Android.
 *
 * A Activity pode expor um ViewModel que implemente este contrato. Toda operação que acessa
 * rede, área de transferência, armazenamento ou serviços Android permanece fora da UI.
 */
interface MobileUiController {
    val state: StateFlow<MobileUiState>

    /** ExoPlayer used to play rendered preview clips (bound by a PlayerView). */
    val previewExoPlayer: androidx.media3.exoplayer.ExoPlayer?
        get() = null

    fun onAction(action: MobileUiAction)
}

data class MobileUiState(
    val selectedTab: AppTab = AppTab.HOME,
    val home: HomeUiState = HomeUiState(),
    val siteFiles: SiteFilesUiState = SiteFilesUiState(),
    val qrCode: QrCodeUiState = QrCodeUiState(),
    val downloads: DownloadsUiState = DownloadsUiState(),
    val history: HistoryUiState = HistoryUiState(),
    val settings: SettingsUiState = SettingsUiState(),
    val message: UiMessage? = null,
    val legalDocument: LegalDocument? = null,
)

data class UiMessage(
    val id: Long,
    val text: String,
)

enum class AppTab(val labelRes: Int, val glyph: String) {
    HOME(R.string.tab_home, "⌂"),
    SITE_FILES(R.string.tab_site_files, "▤"),
    QR_CODE(R.string.tab_qr_code, "▦"),
    DOWNLOADS(R.string.tab_downloads, "⇩"),
    HISTORY(R.string.tab_history, "↶"),
    SETTINGS(R.string.tab_settings, "⚙"),
}

data class QrCodeUiState(
    val url: String = "",
    val urlError: String? = null,
    val generatedUrl: String? = null,
) {
    val canGenerate: Boolean
        get() = url.isNotBlank()
}

data class SiteFilesUiState(
    val url: String = "",
    val urlError: String? = null,
    val includePdfs: Boolean = true,
    val includeImages: Boolean = true,
    val isScanning: Boolean = false,
    val pageTitle: String? = null,
    val items: List<SiteFileUi> = emptyList(),
    val isDownloading: Boolean = false,
    val completedDownloads: Int = 0,
    val totalDownloads: Int = 0,
) {
    val selectedCount: Int
        get() = items.count { it.selected && it.status != SiteFileStatus.SAVED }

    val canScan: Boolean
        get() = url.isNotBlank() && (includePdfs || includeImages) && !isScanning && !isDownloading

    val canDownload: Boolean
        get() = selectedCount > 0 && !isScanning && !isDownloading
}

data class SiteFileUi(
    val id: String,
    val url: String,
    val name: String,
    val sourceHost: String,
    val kind: SiteFileKindUi,
    val selected: Boolean = true,
    val status: SiteFileStatus = SiteFileStatus.READY,
    val progress: Float? = null,
    val progressText: String? = null,
    val errorMessage: String? = null,
    val savedUri: String? = null,
    val mimeType: String? = null,
)

enum class SiteFileKindUi(val label: String) {
    PDF("PDF"),
    IMAGE("Imagem"),
}

enum class SiteFileStatus(val labelRes: Int) {
    READY(R.string.site_status_ready),
    DOWNLOADING(R.string.site_status_downloading),
    SAVED(R.string.site_status_saved),
    FAILED(R.string.site_status_failed),
}

data class HomeUiState(
    val url: String = "",
    val urlError: String? = null,
    val isAnalyzing: Boolean = false,
    val preview: MediaPreviewUi? = null,
    val selectedKind: MediaKind = MediaKind.VIDEO,
    val selectedQualityId: String? = null,
    val selectedFormatId: String? = null,
    val downloadPlaylist: Boolean = true,
    val playlistSelection: Set<Int> = emptySet(),
    val includeSubtitles: Boolean = false,
    val editorCompatible: Boolean = true,
    val embedMetadata: Boolean = true,
    val embedThumbnail: Boolean = true,
    val itemRateLimitText: String = "",
    val canPaste: Boolean = true,
    /** Valid HTTP links currently typed in the field; above one enables the batch action. */
    val batchCount: Int = 0,
    val isStartingDownload: Boolean = false,
    val analysisHint: String? = null,
    /** Caption languages found for the analyzed media; empty when none are offered. */
    val subtitleLanguages: List<String> = emptyList(),
    val selectedSubtitleLanguages: Set<String> = emptySet(),
    val audioSpeed: Float = 1f,
    val audioPitchSemitones: Float = 0f,
    val audioVolumePercent: Int = 100,
    val audioBass: Boolean = false,
    val audioEcho: Boolean = false,
    val audioTremolo: Boolean = false,
    val audioNormalize: Boolean = false,
    val trimStartSeconds: Float = 0f,
    val trimDurationSeconds: Float? = null,
    val fadeInSeconds: Float = 0f,
    val fadeOutSeconds: Float = 0f,
    val previewUsesVideo: Boolean = true,
    val isAudioPreviewRendering: Boolean = false,
    val isAudioPreviewPlaying: Boolean = false,
    val audioPreviewError: String? = null,
    val spotify: SpotifyMediaUi? = null,
    val isSpotifyDownloading: Boolean = false,
) {
    val canAnalyze: Boolean
        get() = url.isNotBlank() && batchCount <= 1 && !isAnalyzing && !isStartingDownload &&
            !isSpotifyDownloading

    /** True when the field holds a list that can be queued in one go. */
    val canEnqueueBatch: Boolean
        get() = batchCount > 1 && !isAnalyzing && !isStartingDownload

    val canDownload: Boolean
        get() = preview != null && selectedQualityId != null && selectedFormatId != null &&
            !isAnalyzing && !isStartingDownload &&
            (!preview.isPlaylist || downloadPlaylist || selectedPlaylistItems.isNotEmpty())

    val selectedPlaylistItems: List<PlaylistItemUi>
        get() = preview?.playlistItems
            ?.filter { it.index in playlistSelection }
            .orEmpty()

    val audioPreviewActive: Boolean
        get() = isAudioPreviewRendering || isAudioPreviewPlaying

    val canPreviewAudio: Boolean
        get() = preview?.supportsAudio == true && !audioPreviewActive

    /** Whether the "Com vídeo" / "Somente áudio" toggle is offered. */
    val canTogglePreviewVideo: Boolean
        get() = preview?.supportsVideo == true

    val audioEffectsDefault: Boolean
        get() = audioSpeed == 1f && audioPitchSemitones == 0f && audioVolumePercent == 100 &&
            !(audioBass || audioEcho || audioTremolo || audioNormalize)

    val audioTrimDefault: Boolean
        get() = trimStartSeconds == 0f && trimDurationSeconds == null &&
            fadeInSeconds == 0f && fadeOutSeconds == 0f

    /** WAV carries no tags, so the metadata switch is hidden for it. */
    val embedMetadataSupported: Boolean
        get() = selectedKind != MediaKind.AUDIO || selectedFormatId != AudioFormat.WAV.extension
}

data class MediaPreviewUi(
    val title: String,
    val creator: String? = null,
    val sourceName: String,
    val sourceUrl: String? = null,
    val durationText: String? = null,
    val durationSeconds: Float? = null,
    val thumbnailUrl: String? = null,
    val isPlaylist: Boolean = false,
    val playlistItemCount: Int? = null,
    val playlistItems: List<PlaylistItemUi> = emptyList(),
    val supportsVideo: Boolean = true,
    val supportsAudio: Boolean = true,
    val supportsSubtitles: Boolean = false,
    val videoQualities: List<ChoiceUi> = emptyList(),
    val audioQualities: List<ChoiceUi> = emptyList(),
    val videoFormats: List<ChoiceUi> = emptyList(),
    val audioFormats: List<ChoiceUi> = emptyList(),
)

data class ChoiceUi(
    val id: String,
    val label: String,
    val description: String? = null,
    val recommended: Boolean = false,
)

enum class MediaKind(val labelRes: Int, val supportingTextRes: Int) {
    VIDEO(R.string.media_kind_video, R.string.media_kind_video_support),
    AUDIO(R.string.media_kind_audio, R.string.media_kind_audio_support),
}

data class PlaylistItemUi(
    val index: Int,
    val id: String,
    val title: String,
    val url: String,
    val thumbnailUrl: String? = null,
)

/** Metadata-only Spotify preview shown on the home tab. */
data class SpotifyMediaUi(
    val title: String,
    val subtitle: String?,
    val thumbnailUrl: String?,
    val resourceLabel: String,
    val webpageUrl: String,
    val isPlaylist: Boolean,
    val requiresAuth: Boolean,
    val authenticated: Boolean,
    val notice: String?,
    val itemCount: Int?,
    val tracks: List<SpotifyTrackUi>,
) {
    val hasTracks: Boolean
        get() = tracks.isNotEmpty()
}

data class SpotifyTrackUi(
    val index: Int,
    val title: String,
    val artist: String,
    val album: String,
    val durationText: String?,
    val thumbnailUrl: String?,
    /** The `ytsearch1:` query used to obtain the audio from YouTube. */
    val query: String,
)

/** One queue entry resolved from the current analysis. */
data class QueuedDownloadTarget(
    val url: String,
    val title: String,
    val thumbnailUrl: String? = null,
)

/**
 * Resolves which URLs become queue items. A single media, an unrecognized playlist or a
 * "whole playlist" download resolves to the original source; otherwise every selected
 * entry is queued individually. An empty list means a partial playlist has no selection.
 */
fun playlistDownloadTargets(
    preview: MediaPreviewUi,
    selection: Set<Int>,
    wholePlaylist: Boolean,
    fallbackUrl: String,
    fallbackTitle: String,
    fallbackThumbnail: String? = null,
): List<QueuedDownloadTarget> {
    if (!preview.isPlaylist || wholePlaylist || preview.playlistItems.isEmpty()) {
        return listOf(QueuedDownloadTarget(fallbackUrl, fallbackTitle, fallbackThumbnail))
    }
    return preview.playlistItems
        .filter { it.index in selection }
        .map { QueuedDownloadTarget(it.url, it.title, it.thumbnailUrl ?: fallbackThumbnail) }
}

data class DownloadsUiState(
    val items: List<DownloadItemUi> = emptyList(),
    val selectedFilter: DownloadFilter = DownloadFilter.ALL,
    val searchQuery: String = "",
)

enum class DownloadFilter(val labelRes: Int) {
    ALL(R.string.filter_all),
    ACTIVE(R.string.filter_active),
    COMPLETED(R.string.filter_completed),
    FAILED(R.string.filter_failed),
}

data class DownloadItemUi(
    val id: String,
    val title: String,
    val detail: String,
    val status: DownloadStatus,
    val progress: Float? = null,
    val progressText: String? = null,
    val speedText: String? = null,
    val etaText: String? = null,
    val errorMessage: String? = null,
    val thumbnailUrl: String? = null,
    val canOpen: Boolean = false,
    val sourceUrl: String? = null,
    val canPause: Boolean = false,
    val canResume: Boolean = false,
    val canMoveUp: Boolean = false,
    val canMoveDown: Boolean = false,
    val canSetAsSound: Boolean = false,
)

enum class DownloadStatus(val labelRes: Int) {
    QUEUED(R.string.status_queued),
    PREPARING(R.string.status_preparing),
    DOWNLOADING(R.string.status_downloading),
    PROCESSING(R.string.status_processing),
    PAUSED(R.string.status_paused),
    COMPLETED(R.string.status_completed),
    FAILED(R.string.status_failed),
    CANCELLED(R.string.status_cancelled),
}

data class HistoryUiState(
    val items: List<HistoryItemUi> = emptyList(),
    val searchQuery: String = "",
    /** Ids picked in multi-select mode; empty means the screen is browsing normally. */
    val selectedIds: Set<String> = emptySet(),
)

data class HistoryItemUi(
    val id: String,
    val title: String,
    val detail: String,
    val completedAtText: String,
    val fileSizeText: String? = null,
    val thumbnailUrl: String? = null,
    val canOpen: Boolean = true,
    val canShare: Boolean = true,
    val canSetAsSound: Boolean = false,
)

data class SettingsUiState(
    val theme: ThemePreference = ThemePreference.SYSTEM,
    val autoUpdateYtDlp: Boolean = true,
    val updateState: YtDlpUpdateState = YtDlpUpdateState.IDLE,
    val updateDetail: String? = null,
    val ytDlpVersion: String? = null,
    val previousYtDlpVersion: String? = null,
    val availableYtDlpVersion: String? = null,
    val canRollbackYtDlp: Boolean = false,
    val showYtDlpRollbackConfirmation: Boolean = false,
    val appVersion: String = "—",
    val storageLocations: List<StorageLocationUi> = StorageCategory.entries.map {
        StorageLocationUi(category = it)
    },
    val cookieFileName: String? = null,
    val cookie: CookieCheckUi? = null,
    val cookieSubProfiles: List<CookieSubProfileUi> = emptyList(),
    val siteCookieHosts: String = "",
    val siteCookieHostsError: String? = null,
    val proxy: String = "",
    val proxyError: String? = null,
    val rateLimitText: String = "",
    val filenameTemplate: String = "",
    val defaultVideoQualityId: String = "best",
    val defaultVideoFormatId: String = "mp4",
    val defaultAudioBitrate: Int = 192,
    val defaultAudioFormatId: String = "mp3",
    val spotifyClientId: String = "",
    val spotifyClientIdError: String? = null,
    val spotifyConnected: Boolean = false,
    val spotifyAccountName: String? = null,
    val isSpotifyConnecting: Boolean = false,
    val parallelDownloads: Int = 1,
    val wifiOnly: Boolean = false,
    val downloadWindowEnabled: Boolean = false,
    val downloadWindowStartMin: Int = 0,
    val downloadWindowEndMin: Int = 360,
    val completionSound: Boolean = true,
    val completionVibrate: Boolean = false,
    /** Site ids the user can currently download from; drives the compatibility card. */
    val compatSupportedSites: Set<String> = emptySet(),
    val keepAwakeDuringDownloads: Boolean = false,
    val statsCompletedCount: Int = 0,
    val statsDownloadedBytes: Long = 0,
    val statsTempBytes: Long = 0,
    val statsFreeBytes: Long = 0,
) {
    val isYtDlpOperationBusy: Boolean
        get() = updateState == YtDlpUpdateState.CHECKING ||
            updateState == YtDlpUpdateState.UPDATING ||
            updateState == YtDlpUpdateState.ROLLING_BACK

    val canInstallYtDlpUpdate: Boolean
        get() = updateState == YtDlpUpdateState.AVAILABLE &&
            !availableYtDlpVersion.isNullOrBlank()
}

data class StorageLocationUi(
    val category: StorageCategory,
    val locationLabel: String = "Downloads/MediaDownloader",
    val isCustom: Boolean = false,
)

/** A cookies.txt profile scoped to specific site hosts, shown in Settings. */
data class CookieSubProfileUi(
    val id: String,
    val label: String,
    val hosts: String,
    val cookie: CookieCheckUi? = null,
    val impersonate: String = "",
)

enum class ThemePreference(val labelRes: Int) {
    SYSTEM(R.string.theme_system),
    LIGHT(R.string.theme_light),
    DARK(R.string.theme_dark),
    AMOLED(R.string.theme_amoled),
}

enum class YtDlpUpdateState {
    IDLE,
    CHECKING,
    AVAILABLE,
    UPDATING,
    ROLLING_BACK,
    UP_TO_DATE,
    ROLLED_BACK,
    REJECTED,
    FAILED,
}

enum class LegalDocument {
    RESPONSIBLE_USE,
    PRIVACY,
    APPLICATION_LICENSE,
    OPEN_SOURCE_LICENSES,
}

sealed interface MobileUiAction {
    data class Navigate(val tab: AppTab) : MobileUiAction
    data class QrCodeUrlChanged(val value: String) : MobileUiAction
    object GenerateQrCode : MobileUiAction
    object OpenGeneratedQrCode : MobileUiAction
    object SaveGeneratedQrCode : MobileUiAction
    object ShareGeneratedQrCode : MobileUiAction

    /** Usada pela Activity ao receber ACTION_SEND ou ACTION_VIEW. */
    data class ReceiveSharedUrl(val value: String) : MobileUiAction
    data class UrlChanged(val value: String) : MobileUiAction
    object PasteUrl : MobileUiAction
    object EnqueueUrlBatch : MobileUiAction
    data class ToggleSubtitleLanguage(val language: String) : MobileUiAction
    object AnalyzeUrl : MobileUiAction
    object ClearAnalysis : MobileUiAction
    data class SelectMediaKind(val kind: MediaKind) : MobileUiAction
    data class SelectQuality(val id: String) : MobileUiAction
    data class SelectFormat(val id: String) : MobileUiAction
    data class SetDownloadPlaylist(val enabled: Boolean) : MobileUiAction
    data class TogglePlaylistItem(val index: Int) : MobileUiAction
    data class SelectAllPlaylistItems(val selected: Boolean) : MobileUiAction
    data class SetIncludeSubtitles(val enabled: Boolean) : MobileUiAction
    data class SelectPreviewKind(val kind: MediaKind) : MobileUiAction
    data class SetItemRateLimitText(val value: String) : MobileUiAction
    data class ToggleEditorCompatibility(val enabled: Boolean) : MobileUiAction

    data class SetEmbedMetadata(val enabled: Boolean) : MobileUiAction

    data class SetEmbedThumbnail(val enabled: Boolean) : MobileUiAction
    object StartDownload : MobileUiAction
    data class SetAudioSpeed(val value: Float) : MobileUiAction
    data class SetAudioPitch(val semitones: Float) : MobileUiAction
    data class SetAudioVolume(val percent: Int) : MobileUiAction
    data class SetAudioBass(val enabled: Boolean) : MobileUiAction
    data class SetAudioEcho(val enabled: Boolean) : MobileUiAction
    data class SetAudioTremolo(val enabled: Boolean) : MobileUiAction
    data class SetAudioNormalize(val enabled: Boolean) : MobileUiAction
    data class SetTrimStartSeconds(val value: Float) : MobileUiAction
    data class SetTrimDurationSeconds(val value: Float?) : MobileUiAction
    data class SetFadeInSeconds(val value: Float) : MobileUiAction
    data class SetFadeOutSeconds(val value: Float) : MobileUiAction
    object ResetAudioEffects : MobileUiAction
    object PreviewAudio : MobileUiAction
    object StopAudioPreview : MobileUiAction
    data class SelectPreviewUsesVideo(val enabled: Boolean) : MobileUiAction

    data class SiteUrlChanged(val value: String) : MobileUiAction
    object PasteSiteUrl : MobileUiAction
    data class SetSiteIncludePdfs(val enabled: Boolean) : MobileUiAction
    data class SetSiteIncludeImages(val enabled: Boolean) : MobileUiAction
    object ScanSiteFiles : MobileUiAction
    data class ToggleSiteFile(val id: String) : MobileUiAction
    data class SelectAllSiteFiles(val selected: Boolean) : MobileUiAction
    object DownloadSelectedSiteFiles : MobileUiAction
    object CancelSiteFileDownloads : MobileUiAction
    data class OpenSiteFile(val id: String) : MobileUiAction

    data class SelectDownloadFilter(val filter: DownloadFilter) : MobileUiAction
    data class DownloadsSearchQueryChanged(val value: String) : MobileUiAction
    data class CancelDownload(val id: String) : MobileUiAction
    data class PauseDownload(val id: String) : MobileUiAction
    data class ResumeDownload(val id: String) : MobileUiAction
    data class MoveDownload(val id: String, val up: Boolean) : MobileUiAction
    data class RetryDownload(val id: String) : MobileUiAction
    data class RemoveDownload(val id: String) : MobileUiAction
    data class OpenDownload(val id: String) : MobileUiAction
    object ClearFinishedDownloads : MobileUiAction

    data class OpenHistoryItem(val id: String) : MobileUiAction
    data class ShareHistoryItem(val id: String) : MobileUiAction
    data class HistorySearchQueryChanged(val value: String) : MobileUiAction
    data class BeginHistorySelection(val id: String) : MobileUiAction
    data class ToggleHistorySelection(val id: String) : MobileUiAction
    data class ToggleSelectAllHistoryItems(val selected: Boolean) : MobileUiAction
    object ClearHistorySelection : MobileUiAction
    object DeleteSelectedHistoryItems : MobileUiAction
    object ExportHistory : MobileUiAction
    object ClearHistory : MobileUiAction

    data class SetTheme(val theme: ThemePreference) : MobileUiAction
    data class SetAutoUpdateYtDlp(val enabled: Boolean) : MobileUiAction
    object CheckYtDlpUpdate : MobileUiAction
    object UpdateYtDlp : MobileUiAction
    object RequestYtDlpRollback : MobileUiAction
    object ConfirmYtDlpRollback : MobileUiAction
    object DismissYtDlpRollback : MobileUiAction
    data class ChooseDownloadLocation(val category: StorageCategory) : MobileUiAction
    data class ResetDownloadLocation(val category: StorageCategory) : MobileUiAction
    object ChooseCookieFile : MobileUiAction
    object ClearCookies : MobileUiAction
    data class SiteCookieHostsChanged(val value: String) : MobileUiAction
    object ChooseSiteCookieFile : MobileUiAction
    data class ReplaceSiteCookieFile(val id: String) : MobileUiAction
    data class RemoveCookieProfile(val id: String) : MobileUiAction
    data class SetProxy(val value: String) : MobileUiAction
    data class SetRateLimitText(val value: String) : MobileUiAction
    data class SetFilenameTemplate(val value: String) : MobileUiAction
    object ResetFilenameTemplate : MobileUiAction
    data class SetDefaultVideoQuality(val id: String) : MobileUiAction
    data class SetDefaultVideoFormat(val id: String) : MobileUiAction
    data class SetDefaultAudioBitrate(val value: Int) : MobileUiAction
    data class SetDefaultAudioFormat(val id: String) : MobileUiAction
    data class SetParallelDownloads(val value: Int) : MobileUiAction
    data class SetWifiOnly(val enabled: Boolean) : MobileUiAction
    data class SetDownloadWindowEnabled(val enabled: Boolean) : MobileUiAction
    data class SetDownloadWindowStartMin(val value: Int) : MobileUiAction
    data class SetDownloadWindowEndMin(val value: Int) : MobileUiAction
    data class SetCompletionSound(val enabled: Boolean) : MobileUiAction
    data class SetCompletionVibrate(val enabled: Boolean) : MobileUiAction
    data class SetKeepAwakeDuringDownloads(val enabled: Boolean) : MobileUiAction
    object ExportSettings : MobileUiAction
    data class ImportSettings(val uri: Uri) : MobileUiAction
    data class SetCookieProfileImpersonate(val id: String, val value: String) : MobileUiAction
    data class CopyDownloadLink(val id: String) : MobileUiAction
    object RemoveTemporaryFiles : MobileUiAction
    object RefreshStats : MobileUiAction
    data class RedownloadHistoryItem(val id: String) : MobileUiAction
    data class RenameHistoryItem(val id: String, val newFileName: String) : MobileUiAction
    data class SetDownloadSound(val id: String, val role: SoundRole) : MobileUiAction
    data class SetHistorySound(val id: String, val role: SoundRole) : MobileUiAction
    object ShareDiagnostics : MobileUiAction
    object WidgetDownloadFromClipboard : MobileUiAction
    data class SetSpotifyClientId(val value: String) : MobileUiAction
    object ConnectSpotify : MobileUiAction
    object DisconnectSpotify : MobileUiAction
    object DownloadSpotifyOnYouTube : MobileUiAction
    object CopySupportPixPayload : MobileUiAction
    object CopySupportPixKey : MobileUiAction
    data class OpenLegalDocument(val document: LegalDocument) : MobileUiAction
    object DismissLegalDocument : MobileUiAction

    data class DismissMessage(val id: Long) : MobileUiAction
}
