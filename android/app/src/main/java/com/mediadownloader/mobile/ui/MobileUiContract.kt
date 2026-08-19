package com.mediadownloader.mobile.ui

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

enum class AppTab(val label: String, val glyph: String) {
    HOME("Início", "⌂"),
    SITE_FILES("Arquivos", "▤"),
    QR_CODE("QR Code", "▦"),
    DOWNLOADS("Downloads", "⇩"),
    HISTORY("Histórico", "↶"),
    SETTINGS("Ajustes", "⚙"),
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

enum class SiteFileStatus(val label: String) {
    READY("Pronto"),
    DOWNLOADING("Baixando"),
    SAVED("Salvo"),
    FAILED("Falhou"),
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
    val includeSubtitles: Boolean = false,
    val canPaste: Boolean = true,
    val isStartingDownload: Boolean = false,
    val analysisHint: String? = null,
) {
    val canAnalyze: Boolean
        get() = url.isNotBlank() && !isAnalyzing && !isStartingDownload

    val canDownload: Boolean
        get() = preview != null && selectedQualityId != null && selectedFormatId != null &&
            !isAnalyzing && !isStartingDownload
}

data class MediaPreviewUi(
    val title: String,
    val creator: String? = null,
    val sourceName: String,
    val sourceUrl: String? = null,
    val durationText: String? = null,
    val thumbnailUrl: String? = null,
    val isPlaylist: Boolean = false,
    val playlistItemCount: Int? = null,
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

enum class MediaKind(val label: String, val supportingText: String) {
    VIDEO("Vídeo", "Imagem e som"),
    AUDIO("Áudio", "Somente o áudio"),
}

data class DownloadsUiState(
    val items: List<DownloadItemUi> = emptyList(),
    val selectedFilter: DownloadFilter = DownloadFilter.ALL,
)

enum class DownloadFilter(val label: String) {
    ALL("Todos"),
    ACTIVE("Em andamento"),
    COMPLETED("Concluídos"),
    FAILED("Com erro"),
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
)

enum class DownloadStatus(val label: String) {
    QUEUED("Na fila"),
    PREPARING("Preparando"),
    DOWNLOADING("Baixando"),
    PROCESSING("Processando"),
    COMPLETED("Concluído"),
    FAILED("Falhou"),
    CANCELLED("Cancelado"),
}

data class HistoryUiState(
    val items: List<HistoryItemUi> = emptyList(),
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

enum class ThemePreference(val label: String) {
    SYSTEM("Sistema"),
    LIGHT("Claro"),
    DARK("Escuro"),
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
    OPEN_SOURCE_LICENSES,
}

sealed interface MobileUiAction {
    data class Navigate(val tab: AppTab) : MobileUiAction
    data class QrCodeUrlChanged(val value: String) : MobileUiAction
    object GenerateQrCode : MobileUiAction

    /** Usada pela Activity ao receber ACTION_SEND ou ACTION_VIEW. */
    data class ReceiveSharedUrl(val value: String) : MobileUiAction
    data class UrlChanged(val value: String) : MobileUiAction
    object PasteUrl : MobileUiAction
    object AnalyzeUrl : MobileUiAction
    object ClearAnalysis : MobileUiAction
    data class SelectMediaKind(val kind: MediaKind) : MobileUiAction
    data class SelectQuality(val id: String) : MobileUiAction
    data class SelectFormat(val id: String) : MobileUiAction
    data class SetDownloadPlaylist(val enabled: Boolean) : MobileUiAction
    data class SetIncludeSubtitles(val enabled: Boolean) : MobileUiAction
    object StartDownload : MobileUiAction

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
    data class CancelDownload(val id: String) : MobileUiAction
    data class RetryDownload(val id: String) : MobileUiAction
    data class RemoveDownload(val id: String) : MobileUiAction
    data class OpenDownload(val id: String) : MobileUiAction
    object ClearFinishedDownloads : MobileUiAction

    data class OpenHistoryItem(val id: String) : MobileUiAction
    data class ShareHistoryItem(val id: String) : MobileUiAction
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
    data class OpenLegalDocument(val document: LegalDocument) : MobileUiAction
    object DismissLegalDocument : MobileUiAction

    data class DismissMessage(val id: Long) : MobileUiAction
}
