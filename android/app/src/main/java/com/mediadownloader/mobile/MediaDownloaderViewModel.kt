package com.mediadownloader.mobile

import android.app.Application
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.OpenableColumns
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.core.content.FileProvider
import androidx.media3.exoplayer.ExoPlayer
import com.mediadownloader.mobile.data.AudioEffects
import com.mediadownloader.mobile.data.AudioFormat
import com.mediadownloader.mobile.data.CookieCheckUi
import com.mediadownloader.mobile.data.CookieDiagnostics
import com.mediadownloader.mobile.data.CookieProfile
import com.mediadownloader.mobile.data.CookieProfilesStore
import com.mediadownloader.mobile.data.DownloadItem
import com.mediadownloader.mobile.data.DownloadOptions
import com.mediadownloader.mobile.data.DownloadRepository
import com.mediadownloader.mobile.data.DownloadState
import com.mediadownloader.mobile.data.HistoryCsvRow
import com.mediadownloader.mobile.data.HistoryItem
import com.mediadownloader.mobile.data.MediaAnalysis
import com.mediadownloader.mobile.data.MediaFormat
import com.mediadownloader.mobile.data.MediaType
import com.mediadownloader.mobile.data.MobileSettingsStore
import com.mediadownloader.mobile.data.PreviewSourceResolver
import com.mediadownloader.mobile.data.SpotifyMedia
import com.mediadownloader.mobile.data.SpotifyModels
import com.mediadownloader.mobile.data.SpotifyTokenStore
import com.mediadownloader.mobile.data.SpotifyTrack
import com.mediadownloader.mobile.data.StorageCategory
import com.mediadownloader.mobile.data.StorageLocationStore
import com.mediadownloader.mobile.data.UrlExtraction
import com.mediadownloader.mobile.data.VideoContainer
import com.mediadownloader.mobile.data.historyToCsv
import com.mediadownloader.mobile.data.resolveChoiceId
import com.mediadownloader.mobile.download.AndroidDownloadEngine
import com.mediadownloader.mobile.download.DownloadService
import com.mediadownloader.mobile.preview.PreviewPlayer
import com.mediadownloader.mobile.preview.PreviewRenderer
import com.mediadownloader.mobile.site.AndroidSiteFileService
import com.mediadownloader.mobile.site.SiteFile
import com.mediadownloader.mobile.site.SiteFileKind
import com.mediadownloader.mobile.spotify.SpotifyMetadataClient
import com.mediadownloader.mobile.support.SupportConfig
import com.mediadownloader.mobile.ui.AppTab
import com.mediadownloader.mobile.ui.ChoiceUi
import com.mediadownloader.mobile.ui.CookieSubProfileUi
import com.mediadownloader.mobile.ui.DownloadFilter
import com.mediadownloader.mobile.ui.DownloadItemUi
import com.mediadownloader.mobile.ui.DownloadStatus
import com.mediadownloader.mobile.ui.HistoryItemUi
import com.mediadownloader.mobile.ui.HistoryUiState
import com.mediadownloader.mobile.ui.HomeUiState
import com.mediadownloader.mobile.ui.MediaKind
import com.mediadownloader.mobile.ui.MediaPreviewUi
import com.mediadownloader.mobile.ui.MobileUiAction
import com.mediadownloader.mobile.ui.MobileUiController
import com.mediadownloader.mobile.ui.MobileUiState
import com.mediadownloader.mobile.ui.PlaylistItemUi
import com.mediadownloader.mobile.ui.QrCodeFileService
import com.mediadownloader.mobile.ui.SettingsUiState
import com.mediadownloader.mobile.ui.StorageLocationUi
import com.mediadownloader.mobile.ui.SiteFileKindUi
import com.mediadownloader.mobile.ui.SiteFileStatus
import com.mediadownloader.mobile.ui.SiteFileUi
import com.mediadownloader.mobile.ui.SiteFilesUiState
import com.mediadownloader.mobile.ui.SpotifyMediaUi
import com.mediadownloader.mobile.ui.SpotifyTrackUi
import com.mediadownloader.mobile.ui.ThemePreference
import com.mediadownloader.mobile.ui.UiMessage
import com.mediadownloader.mobile.ui.YtDlpUpdateState
import com.mediadownloader.mobile.ui.playlistDownloadTargets
import com.mediadownloader.mobile.update.YtDlpCheckOutcome
import com.mediadownloader.mobile.update.YtDlpInstallOutcome
import com.mediadownloader.mobile.update.YtDlpRuntimeStatus
import com.mediadownloader.mobile.update.YtDlpUpdateManager
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.text.DateFormat
import java.io.File
import java.io.IOException
import java.util.Date

class MediaDownloaderViewModel(application: Application) : AndroidViewModel(application), MobileUiController {
    private val appContext = application.applicationContext
    private val repository = DownloadRepository.getInstance(appContext)
    private val engine = AndroidDownloadEngine(appContext)
    private val siteFileService = AndroidSiteFileService(appContext)
    private val qrCodeFiles = QrCodeFileService(appContext)
    private val preferences = appContext.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)
    private val settingsStore = MobileSettingsStore(preferences)
    private val storageLocations = StorageLocationStore(appContext)
    private val cookieProfilesStore = CookieProfilesStore(appContext)
    private val spotifyTokenStore = SpotifyTokenStore(appContext)
    private val spotifyClient = SpotifyMetadataClient(spotifyTokenStore, ::savedSpotifyClientId)
    private var spotifyVerifier: String? = null
    private var spotifyState: String? = null
    private var pendingCookieProfileId: String? = null
    private var pendingCookieHosts: List<String> = emptyList()
    private val analysisMutex = Mutex()
    private val ytDlpUpdateManager = (application as? MediaDownloaderApplication)
        ?.ytDlpUpdateManager
        ?: YtDlpUpdateManager.getInstance(appContext)
    private val initialYtDlpStatus = ytDlpUpdateManager.snapshot()

    private val _state = MutableStateFlow(
        MobileUiState(
            settings = SettingsUiState(
                theme = savedTheme(),
                autoUpdateYtDlp = preferences.getBoolean(KEY_AUTO_UPDATE, true),
                appVersion = appVersion(),
                ytDlpVersion = initialYtDlpStatus.currentVersion,
                previousYtDlpVersion = initialYtDlpStatus.previousVersion,
                canRollbackYtDlp = initialYtDlpStatus.canRollback,
                storageLocations = storageLocationUi(),
                cookieFileName = cookieProfilesStore.globalProfile?.label?.takeIf(String::isNotBlank),
                spotifyClientId = savedSpotifyClientId(),
                spotifyConnected = spotifyClient.isConnected(),
                spotifyAccountName = spotifyClient.accountName(),
                proxy = settingsStore.proxy,
                rateLimitText = settingsStore.rateLimitKbps.toString(),
                filenameTemplate = settingsStore.fileNameTemplate,
                defaultVideoQualityId = settingsStore.defaultVideoQuality,
                defaultVideoFormatId = settingsStore.defaultVideoFormat,
                defaultAudioBitrate = settingsStore.defaultAudioBitrate,
                defaultAudioFormatId = settingsStore.defaultAudioFormat,
                cookieSubProfiles = cookieSubProfilesUi(),
            ),
        ),
    )
    override val state: StateFlow<MobileUiState> = _state.asStateFlow()

    private var currentAnalysis: MediaAnalysis? = null
    private var analysisJob: Job? = null
    private var siteFilesJob: Job? = null
    private var siteFileAssets: Map<String, SiteFile> = emptyMap()
    private var messageSequence = 0L
    private var requestStoragePermission: ((() -> Unit) -> Unit)? = null
    private var pendingStorageAction: (() -> Unit)? = null
    private var requestDownloadLocation: (() -> Unit)? = null
    private var pendingDownloadLocation: StorageCategory? = null
    private var requestCookieFile: (() -> Unit)? = null
    private val previewRenderer = PreviewRenderer(appContext)
    private val previewPlayer = PreviewPlayer(appContext)
    private var audioPreviewJob: Job? = null

    override val previewExoPlayer: ExoPlayer?
        get() = previewPlayer.player

    init {
        viewModelScope.launch {
            combine(repository.downloads, repository.history) { downloads, history ->
                downloads to history
            }.collectLatest { (downloads, history) ->
                _state.update { current ->
                    current.copy(
                        downloads = current.downloads.copy(items = downloads.map(::toDownloadUi)),
                        history = HistoryUiState(history.map(::toHistoryUi)),
                    )
                }
            }
        }
        viewModelScope.launch {
            refreshYtDlpStatus()
            ytDlpUpdateManager.consumeRecoveryNotice()?.let(::showMessage)
            if (_state.value.settings.autoUpdateYtDlp &&
                ytDlpUpdateManager.shouldCheckAutomatically()
            ) {
                checkYtDlpUpdate(showResultMessage = false)
            }
        }
        viewModelScope.launch {
            refreshCookieDiagnostics()
        }
        viewModelScope.launch {
            autoFillFromClipboardIfQuiet()
        }
    }

    override fun onAction(action: MobileUiAction) {
        when (action) {
            is MobileUiAction.Navigate -> updateState { it.copy(selectedTab = action.tab) }
            is MobileUiAction.QrCodeUrlChanged -> updateState {
                it.copy(qrCode = it.qrCode.copy(url = action.value, urlError = null, generatedUrl = null))
            }
            MobileUiAction.GenerateQrCode -> generateQrCode()
            MobileUiAction.OpenGeneratedQrCode -> openGeneratedQrCode()
            MobileUiAction.SaveGeneratedQrCode -> saveGeneratedQrCode()
            MobileUiAction.ShareGeneratedQrCode -> shareGeneratedQrCode()
            is MobileUiAction.ReceiveSharedUrl -> receiveUrl(action.value)
            is MobileUiAction.UrlChanged -> {
                stopAudioPreview()
                analysisJob?.cancel()
                currentAnalysis = null
                updateHome {
                    it.copy(
                        url = action.value,
                        urlError = null,
                        preview = null,
                        spotify = null,
                        analysisHint = null,
                        audioPreviewError = null,
                        previewUsesVideo = true,
                        isAnalyzing = false,
                        isSpotifyDownloading = false,
                    )
                }
            }
            MobileUiAction.PasteUrl -> pasteUrl()
            MobileUiAction.AnalyzeUrl -> analyzeUrl()
            MobileUiAction.ClearAnalysis -> clearAnalysis()
            is MobileUiAction.SelectMediaKind -> selectMediaKind(action.kind)
            is MobileUiAction.SelectQuality -> updateHome { it.copy(selectedQualityId = action.id) }
            is MobileUiAction.SelectFormat -> updateHome { it.copy(selectedFormatId = action.id) }
            is MobileUiAction.SetDownloadPlaylist -> updateHome { it.copy(downloadPlaylist = action.enabled) }
            is MobileUiAction.TogglePlaylistItem -> updateHome { home ->
                home.copy(
                    playlistSelection = if (action.index in home.playlistSelection) {
                        home.playlistSelection - action.index
                    } else {
                        home.playlistSelection + action.index
                    },
                )
            }
            is MobileUiAction.SelectAllPlaylistItems -> updateHome { home ->
                home.copy(
                    playlistSelection = if (action.selected) {
                        home.preview?.playlistItems?.mapTo(mutableSetOf(), PlaylistItemUi::index)
                            ?: emptySet()
                    } else {
                        emptySet()
                    },
                )
            }
            is MobileUiAction.SetIncludeSubtitles -> updateHome { it.copy(includeSubtitles = action.enabled) }
            is MobileUiAction.SetAudioSpeed -> updateHome { it.copy(audioSpeed = action.value.coerceIn(0.5f, 2f)) }
            is MobileUiAction.SetAudioPitch -> updateHome {
                it.copy(audioPitchSemitones = action.semitones.coerceIn(-12f, 12f))
            }
            is MobileUiAction.SetAudioVolume -> updateHome {
                it.copy(audioVolumePercent = action.percent.coerceIn(5, 200))
            }
            is MobileUiAction.SetAudioBass -> updateHome { it.copy(audioBass = action.enabled) }
            is MobileUiAction.SetAudioEcho -> updateHome { it.copy(audioEcho = action.enabled) }
            is MobileUiAction.SetAudioTremolo -> updateHome { it.copy(audioTremolo = action.enabled) }
            is MobileUiAction.SetAudioNormalize -> updateHome { it.copy(audioNormalize = action.enabled) }
            is MobileUiAction.SetTrimStartSeconds -> updateHome {
                it.copy(trimStartSeconds = action.value.coerceAtLeast(0f))
            }
            is MobileUiAction.SetTrimDurationSeconds -> updateHome {
                it.copy(trimDurationSeconds = action.value?.takeIf { value -> value > 0f })
            }
            is MobileUiAction.SetFadeInSeconds -> updateHome {
                it.copy(fadeInSeconds = action.value.coerceIn(0f, MAX_FADE_SECONDS))
            }
            is MobileUiAction.SetFadeOutSeconds -> updateHome {
                it.copy(fadeOutSeconds = action.value.coerceIn(0f, MAX_FADE_SECONDS))
            }
            MobileUiAction.PreviewAudio -> previewAudio()
            MobileUiAction.StopAudioPreview -> stopAudioPreview()
            MobileUiAction.ResetAudioEffects -> resetAudioEffects()
            is MobileUiAction.SelectPreviewUsesVideo -> updateHome {
                it.copy(previewUsesVideo = action.enabled)
            }
            MobileUiAction.StartDownload -> startDownload()
            is MobileUiAction.SiteUrlChanged -> changeSiteUrl(action.value)
            MobileUiAction.PasteSiteUrl -> pasteSiteUrl()
            is MobileUiAction.SetSiteIncludePdfs -> updateSiteFiles {
                it.copy(
                    includePdfs = action.enabled,
                    pageTitle = null,
                    items = emptyList(),
                    urlError = null,
                )
            }
            is MobileUiAction.SetSiteIncludeImages -> updateSiteFiles {
                it.copy(
                    includeImages = action.enabled,
                    pageTitle = null,
                    items = emptyList(),
                    urlError = null,
                )
            }
            MobileUiAction.ScanSiteFiles -> scanSiteFiles()
            is MobileUiAction.ToggleSiteFile -> toggleSiteFile(action.id)
            is MobileUiAction.SelectAllSiteFiles -> selectAllSiteFiles(action.selected)
            MobileUiAction.DownloadSelectedSiteFiles -> downloadSelectedSiteFiles()
            MobileUiAction.CancelSiteFileDownloads -> cancelSiteFileDownloads()
            is MobileUiAction.OpenSiteFile -> openSiteFile(action.id)
            is MobileUiAction.SelectDownloadFilter -> updateState {
                it.copy(downloads = it.downloads.copy(selectedFilter = action.filter))
            }
            is MobileUiAction.DownloadsSearchQueryChanged -> updateState {
                it.copy(downloads = it.downloads.copy(searchQuery = action.value))
            }
            is MobileUiAction.CancelDownload -> cancelDownload(action.id)
            is MobileUiAction.RetryDownload -> retryDownload(action.id)
            is MobileUiAction.RemoveDownload -> launchRepositoryAction { repository.deleteDownload(action.id) }
            is MobileUiAction.OpenDownload -> openDownload(action.id)
            MobileUiAction.ClearFinishedDownloads -> launchRepositoryAction(repository::clearFinishedDownloads)
            is MobileUiAction.OpenHistoryItem -> openHistoryItem(action.id)
            is MobileUiAction.ShareHistoryItem -> shareHistoryItem(action.id)
            is MobileUiAction.HistorySearchQueryChanged -> updateState {
                it.copy(history = it.history.copy(searchQuery = action.value))
            }
            MobileUiAction.ExportHistory -> exportHistory()
            MobileUiAction.ClearHistory -> launchRepositoryAction(repository::clearHistory)
            is MobileUiAction.SetTheme -> saveTheme(action.theme)
            is MobileUiAction.SetAutoUpdateYtDlp -> saveAutoUpdate(action.enabled)
            MobileUiAction.CheckYtDlpUpdate -> checkYtDlpUpdate(showResultMessage = true)
            MobileUiAction.UpdateYtDlp -> installYtDlpUpdate()
            MobileUiAction.RequestYtDlpRollback -> updateSettings {
                it.copy(showYtDlpRollbackConfirmation = true)
            }
            MobileUiAction.DismissYtDlpRollback -> updateSettings {
                it.copy(showYtDlpRollbackConfirmation = false)
            }
            MobileUiAction.ConfirmYtDlpRollback -> {
                updateSettings { it.copy(showYtDlpRollbackConfirmation = false) }
                rollbackYtDlp()
            }
            is MobileUiAction.ChooseDownloadLocation -> chooseDownloadLocation(action.category)
            is MobileUiAction.ResetDownloadLocation -> resetDownloadLocation(action.category)
            MobileUiAction.ChooseCookieFile -> chooseCookieFile()
            MobileUiAction.ClearCookies -> clearCookies()
            is MobileUiAction.SiteCookieHostsChanged -> updateSettings {
                it.copy(siteCookieHosts = action.value, siteCookieHostsError = null)
            }
            MobileUiAction.ChooseSiteCookieFile -> chooseSiteCookieFile()
            is MobileUiAction.ReplaceSiteCookieFile -> replaceSiteCookieFile(action.id)
            is MobileUiAction.RemoveCookieProfile -> removeCookieProfile(action.id)
            is MobileUiAction.SetProxy -> setProxy(action.value)
            is MobileUiAction.SetRateLimitText -> setRateLimitText(action.value)
            is MobileUiAction.SetItemRateLimitText -> setItemRateLimitText(action.value)
            is MobileUiAction.ToggleEditorCompatibility -> updateHome {
                it.copy(editorCompatible = action.enabled)
            }
            is MobileUiAction.SelectPreviewKind -> updateHome { it.copy(selectedKind = action.kind) }
            is MobileUiAction.SetFilenameTemplate -> setFilenameTemplate(action.value)
            MobileUiAction.ResetFilenameTemplate -> resetFilenameTemplate()
            is MobileUiAction.SetDefaultVideoQuality -> setDefaultVideoQuality(action.id)
            is MobileUiAction.SetDefaultVideoFormat -> setDefaultVideoFormat(action.id)
            is MobileUiAction.SetDefaultAudioBitrate -> setDefaultAudioBitrate(action.value)
            is MobileUiAction.SetDefaultAudioFormat -> setDefaultAudioFormat(action.id)
            MobileUiAction.ShareDiagnostics -> shareDiagnostics()
            MobileUiAction.WidgetDownloadFromClipboard -> widgetDownloadFromClipboard()
            is MobileUiAction.SetSpotifyClientId -> changeSpotifyClientId(action.value)
            MobileUiAction.ConnectSpotify -> connectSpotify()
            MobileUiAction.DisconnectSpotify -> disconnectSpotify()
            MobileUiAction.DownloadSpotifyOnYouTube -> downloadSpotifyOnYouTube()
            MobileUiAction.CopySupportPixPayload -> copySupportPixPayload()
            MobileUiAction.CopySupportPixKey -> copySupportPixKey()
            is MobileUiAction.OpenLegalDocument -> updateState { it.copy(legalDocument = action.document) }
            MobileUiAction.DismissLegalDocument -> updateState { it.copy(legalDocument = null) }
            is MobileUiAction.DismissMessage -> updateState {
                if (it.message?.id == action.id) it.copy(message = null) else it
            }
        }
    }

    fun receiveIntent(intent: Intent?) {
        if (intent?.action == WIDGET_ACTION_DOWNLOAD) {
            onAction(MobileUiAction.WidgetDownloadFromClipboard)
            return
        }
        val value = when (intent?.action) {
            Intent.ACTION_SEND -> intent.getStringExtra(Intent.EXTRA_TEXT)
            Intent.ACTION_VIEW -> intent.dataString
            else -> null
        }
        value?.let { onAction(MobileUiAction.ReceiveSharedUrl(it)) }
    }

    override fun onCleared() {
        previewPlayer.release()
        super.onCleared()
    }

    fun setStoragePermissionRequester(requester: (() -> Unit) -> Unit) {
        requestStoragePermission = requester
    }

    fun setPendingStorageAction(action: () -> Unit) {
        pendingStorageAction = action
    }

    fun onStoragePermissionResult(granted: Boolean) {
        val action = pendingStorageAction
        pendingStorageAction = null
        if (granted) action?.invoke() else showMessage(
            "Permita o acesso ao armazenamento para salvar em Downloads neste Android.",
        )
    }

    fun setDownloadLocationRequester(requester: () -> Unit) {
        requestDownloadLocation = requester
    }

    fun onDownloadLocationSelected(uri: String?) {
        val category = pendingDownloadLocation
        pendingDownloadLocation = null
        if (category == null || uri.isNullOrBlank()) return
        storageLocations.set(category, uri)
        refreshStorageLocations()
        showMessage("Nova pasta de ${category.label.lowercase()} salva.")
    }

    fun onDownloadLocationSelectionFailed() {
        pendingDownloadLocation = null
        showMessage("O Android não concedeu acesso permanente à pasta selecionada.")
    }

    fun setCookieFileRequester(requester: () -> Unit) {
        requestCookieFile = requester
    }

    fun onCookieFileSelected(uri: Uri?) {
        if (uri == null) return
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val content = cookieFileText(uri)
                val name = cookieFileName(uri)
                val targetId = pendingCookieProfileId
                pendingCookieProfileId = null
                when {
                    targetId == null -> cookieProfilesStore.upsert(
                        CookieProfile(CookieProfilesStore.DEFAULT_PROFILE_ID, name),
                        content,
                    )
                    targetId == CREATE_SITE_PROFILE_ID -> cookieProfilesStore.upsert(
                        CookieProfile(java.util.UUID.randomUUID().toString(), name, pendingCookieHosts),
                        content,
                    )
                    else -> {
                        val hosts = cookieProfilesStore.list()
                            .firstOrNull { it.id == targetId }?.hosts.orEmpty()
                        cookieProfilesStore.upsert(CookieProfile(targetId, name, hosts), content)
                    }
                }
                pendingCookieHosts = emptyList()
                refreshCookieDiagnostics()
                showMessage("Cookies carregados de ${_state.value.settings.cookieFileName.orEmpty()}.")
            } catch (error: Throwable) {
                showMessage(
                    readableError(error, "Não foi possível ler o arquivo de cookies selecionado."),
                )
            }
        }
    }

    fun onCookieFileSelectionFailed() {
        showMessage("Não foi possível ler o arquivo de cookies selecionado.")
    }

    private fun chooseCookieFile() {
        pendingCookieProfileId = null
        requestCookieFile?.invoke() ?: showMessage("Não foi possível abrir o seletor de arquivos.")
    }

    private fun chooseSiteCookieFile() {
        val hosts = parseCookieHosts(_state.value.settings.siteCookieHosts)
        if (hosts.isEmpty()) {
            updateSettings {
                it.copy(siteCookieHostsError = "Digite ao menos um site (ex.: youtube.com) separado por vírgula.")
            }
            return
        }
        pendingCookieProfileId = CREATE_SITE_PROFILE_ID
        pendingCookieHosts = hosts
        requestCookieFile?.invoke() ?: showMessage("Não foi possível abrir o seletor de arquivos.")
    }

    private fun replaceSiteCookieFile(id: String) {
        pendingCookieProfileId = id
        requestCookieFile?.invoke() ?: showMessage("Não foi possível abrir o seletor de arquivos.")
    }

    private fun removeCookieProfile(id: String) {
        cookieProfilesStore.remove(id)
        viewModelScope.launch { refreshCookieDiagnostics() }
        showMessage("Cookies do perfil removidos.")
    }

    private fun parseCookieHosts(raw: String): List<String> = raw
        .split(Regex("[,;\\s]+"))
        .map(String::trim)
        .filter(String::isNotBlank)
        .distinct()

    private fun clearCookies() {
        cookieProfilesStore.remove(CookieProfilesStore.DEFAULT_PROFILE_ID)
        viewModelScope.launch { refreshCookieDiagnostics() }
        showMessage("Cookies removidos do Media Downloader.")
    }

    private fun cookieSubProfilesUi(): List<CookieSubProfileUi> = cookieProfilesStore.subProfiles
        .map { profile ->
            val check = cookieProfilesStore.fileFor(profile.id)?.let { file ->
                CookieDiagnostics.check(file.readText(), profile.label)
            }
            CookieSubProfileUi(
                id = profile.id,
                label = profile.label,
                hosts = profile.hosts.joinToString(", "),
                cookie = check,
            )
        }

    private suspend fun refreshCookieDiagnostics() {
        val global = cookieProfilesStore.globalProfile
        val label = global?.label?.takeIf(String::isNotBlank) ?: "cookies.txt"
        val check = if (global == null) {
            CookieCheckUi(
                ok = false,
                message = "Nenhum arquivo de cookies configurado.",
                detail = "A maioria dos vídeos funciona sem cookies. Use-os apenas se precisar acessar mídia restrita à sua conta.",
            )
        } else {
            val file = cookieProfilesStore.fileFor(global.id)
            if (file == null) {
                CookieCheckUi(
                    ok = false,
                    message = "O arquivo de cookies global não foi encontrado.",
                    detail = "Escolha um arquivo de cookies novamente.",
                )
            } else {
                CookieDiagnostics.check(file.readText(), label)
            }
        }
        updateSettings {
            it.copy(
                cookieFileName = cookieProfilesStore.globalProfile?.label?.takeIf(String::isNotBlank),
                cookie = check,
                cookieSubProfiles = cookieSubProfilesUi(),
            )
        }
    }

    private suspend fun cookieFileText(uri: Uri): String =
        appContext.contentResolver.openInputStream(uri)?.use { input ->
            input.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } ?: throw IOException("O arquivo de cookies selecionado não pôde ser aberto.")

    private suspend fun cookieFileName(uri: Uri): String {
        val resolver = appContext.contentResolver
        val displayName = runCatching {
            resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) {
                    val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    if (index >= 0) cursor.getString(index) else null
                } else {
                    null
                }
            }
        }.getOrNull()
        return displayName ?: uri.lastPathSegment ?: "cookies.txt"
    }

    private fun receiveUrl(raw: String) {
        val urls = UrlExtraction.extractHttpUrls(raw)
        when {
            urls.isEmpty() -> showMessage(
                "O conteúdo compartilhado não contém uma URL HTTP ou HTTPS válida.",
            )
            urls.size > 1 -> enqueueUrls(urls.take(MAX_BULK_URLS))
            else -> {
                val url = urls.first()
                clearAnalysis(cancelJob = true)
                updateState {
                    it.copy(
                        selectedTab = AppTab.HOME,
                        home = it.home.copy(url = url, urlError = null),
                    )
                }
            }
        }
    }

    private fun enqueueUrls(urls: List<String>) {
        val startAction: () -> Unit = {
            viewModelScope.launch {
                try {
                    urls.forEachIndexed { index, url ->
                        repository.enqueue(
                            sourceUrl = url,
                            title = "Link ${index + 1}",
                            sourceName = null,
                            thumbnailUrl = null,
                            options = DownloadOptions(
                                mediaType = MediaType.VIDEO,
                                downloadPlaylist = false,
                            ),
                        )
                    }
                    DownloadService.processQueue(appContext)
                    updateState { it.copy(selectedTab = AppTab.DOWNLOADS) }
                    showMessage("${urls.size} links adicionados à fila.")
                } catch (error: Throwable) {
                    showMessage(readableError(error, "Não foi possível adicionar os links à fila."))
                }
            }
            Unit
        }
        requestStoragePermission?.invoke(startAction) ?: startAction()
    }

    private fun widgetDownloadFromClipboard() {
        val urls = UrlExtraction.extractHttpUrls(clipboardText())
        if (urls.isEmpty()) {
            updateState { it.copy(selectedTab = AppTab.HOME) }
            showMessage("A área de transferência não contém um link de mídia.")
            return
        }
        enqueueUrls(urls.take(MAX_BULK_URLS))
    }

    private fun autoFillFromClipboardIfQuiet() {
        if (_state.value.home.url.isNotBlank()) return
        val urls = UrlExtraction.extractHttpUrls(clipboardText())
        if (urls.size != 1) return
        updateHome { HomeUiState(url = urls.first(), canPaste = true) }
    }

    private fun clipboardText(): String {
        val clipboard = appContext.getSystemService(ClipboardManager::class.java)
        return clipboard?.primaryClip?.getItemAt(0)?.coerceToText(appContext)?.toString().orEmpty()
    }

    private fun pasteUrl() {
        val url = UrlExtraction.extractHttpUrl(clipboardText())
        if (url == null) {
            updateHome { it.copy(urlError = "A área de transferência não contém um link válido.") }
        } else {
            clearAnalysis(cancelJob = true)
            updateHome { it.copy(url = url, urlError = null) }
        }
    }

    private fun copySupportPixKey() {
        val clipboard = appContext.getSystemService(ClipboardManager::class.java)
        clipboard?.setPrimaryClip(ClipData.newPlainText("Chave Pix", SupportConfig.PIX_KEY))
        showMessage("Chave Pix copiada.")
    }

    private fun copySupportPixPayload() {
        val clipboard = appContext.getSystemService(ClipboardManager::class.java)
        clipboard?.setPrimaryClip(
            ClipData.newPlainText("Pix Copia e Cola", SupportConfig.PIX_PAYLOAD),
        )
        showMessage("Pix Copia e Cola copiado.")
    }

    private fun generateQrCode() {
        val url = _state.value.qrCode.url.trim()
        updateState {
            it.copy(
                qrCode = if (!isHttpUrl(url)) {
                    it.qrCode.copy(
                        urlError = "Informe uma URL HTTP ou HTTPS válida.",
                        generatedUrl = null,
                    )
                } else if (url.toByteArray(Charsets.UTF_8).size > 1500) {
                    it.qrCode.copy(
                        urlError = "A URL é longa demais para gerar um QR Code confiável.",
                        generatedUrl = null,
                    )
                } else {
                    it.qrCode.copy(url = url, urlError = null, generatedUrl = url)
                },
            )
        }
    }

    private fun openGeneratedQrCode() {
        val value = generatedQrCodeValue() ?: return
        viewModelScope.launch {
            try {
                val file = withContext(Dispatchers.IO) { qrCodeFiles.createShareable(value) }
                openUri(file.uri, QR_CODE_MIME_TYPE)
            } catch (error: Throwable) {
                showMessage(readableError(error, "Não foi possível abrir o QR Code."))
            }
        }
    }

    private fun saveGeneratedQrCode() {
        val value = generatedQrCodeValue() ?: return
        val saveAction: () -> Unit = {
            viewModelScope.launch {
                try {
                    val saved = withContext(Dispatchers.IO) { qrCodeFiles.save(value) }
                    showMessage("QR Code salvo como ${saved.displayName}.")
                } catch (error: Throwable) {
                    showMessage(readableError(error, "Não foi possível salvar o QR Code."))
                }
            }
            Unit
        }
        requestStoragePermission?.invoke(saveAction) ?: saveAction()
    }

    private fun shareGeneratedQrCode() {
        val value = generatedQrCodeValue() ?: return
        viewModelScope.launch {
            try {
                val file = withContext(Dispatchers.IO) { qrCodeFiles.createShareable(value) }
                val uri = Uri.parse(file.uri)
                val intent = Intent(Intent.ACTION_SEND).apply {
                    type = QR_CODE_MIME_TYPE
                    putExtra(Intent.EXTRA_STREAM, uri)
                    putExtra(Intent.EXTRA_TEXT, value)
                    clipData = ClipData.newUri(appContext.contentResolver, file.displayName, uri)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                launchIntent(
                    Intent.createChooser(intent, "Compartilhar QR Code")
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                )
            } catch (error: Throwable) {
                showMessage(readableError(error, "Não foi possível compartilhar o QR Code."))
            }
        }
    }

    private fun generatedQrCodeValue(): String? = _state.value.qrCode.generatedUrl
        ?.takeIf(String::isNotBlank)
        ?: run {
            showMessage("Gere um QR Code antes de usar esta ação.")
            null
        }

    private fun analyzeUrl() {
        val url = _state.value.home.url.trim()
        if (SpotifyModels.parseSpotifyResource(url) != null) {
            analyzeSpotify(url)
            return
        }
        if (!isHttpUrl(url)) {
            updateHome { it.copy(urlError = "Informe uma URL HTTP ou HTTPS válida.") }
            return
        }
        analysisJob?.cancel()
        analysisJob = viewModelScope.launch {
            analysisMutex.withLock {
                updateHome { it.copy(isAnalyzing = true, urlError = null, analysisHint = "Consultando a origem…") }
                try {
                    val analysis = engine.analyze(url)
                    currentAnalysis = analysis
                    val preview = analysis.toPreviewUi()
                    val kind = when {
                        preview.supportsVideo -> MediaKind.VIDEO
                        preview.supportsAudio -> MediaKind.AUDIO
                        else -> MediaKind.VIDEO
                    }
                    updateHome { home -> home.withAnalysis(preview, kind) }
                } catch (_: CancellationException) {
                    throw CancellationException()
                } catch (error: Throwable) {
                    currentAnalysis = null
                    updateHome {
                        it.copy(
                            isAnalyzing = false,
                            preview = null,
                            urlError = readableError(error, "Não foi possível analisar este link."),
                            analysisHint = null,
                        )
                    }
                } finally {
                    // A cancelled analysis would otherwise leave the flag stuck on,
                    // permanently disabling the Analyze/Download buttons.
                    updateHome { it.copy(isAnalyzing = false, analysisHint = null) }
                }
            }
        }
    }

    private fun analyzeSpotify(url: String) {
        analysisJob?.cancel()
        analysisJob = viewModelScope.launch {
            analysisMutex.withLock {
                updateHome {
                    it.copy(
                        isAnalyzing = true,
                        urlError = null,
                        preview = null,
                        spotify = null,
                        analysisHint = "Consultando o Spotify…",
                    )
                }
                try {
                    val media = spotifyClient.analyze(url)
                    updateHome {
                        it.copy(
                            isAnalyzing = false,
                            spotify = media.toSpotifyUi(),
                            preview = null,
                            analysisHint = null,
                        )
                    }
                } catch (_: CancellationException) {
                    throw CancellationException()
                } catch (error: Throwable) {
                    updateHome {
                        it.copy(
                            isAnalyzing = false,
                            spotify = null,
                            analysisHint = null,
                            urlError = readableError(
                                error,
                                "Não foi possível consultar este link do Spotify.",
                            ),
                        )
                    }
                }
            }
        }
    }

    private fun changeSpotifyClientId(value: String) {
        preferences.edit().putString(KEY_SPOTIFY_CLIENT_ID, value.trim()).apply()
        val connected = spotifyClient.isConnected()
        updateSettings {
            it.copy(
                spotifyClientId = value,
                spotifyClientIdError = null,
                spotifyConnected = connected,
                spotifyAccountName = if (connected) spotifyClient.accountName() else null,
            )
        }
    }

    private fun connectSpotify() {
        val clientId = _state.value.settings.spotifyClientId.trim()
        if (!SpotifyModels.validClientId(clientId)) {
            updateSettings {
                it.copy(
                    spotifyClientIdError =
                        "Informe um Client ID válido do Spotify (20 a 64 caracteres).",
                )
            }
            return
        }
        val verifier = SpotifyModels.randomVerifier()
        val state = SpotifyModels.randomState()
        spotifyVerifier = verifier
        spotifyState = state
        updateSettings { it.copy(spotifyClientIdError = null, isSpotifyConnecting = true) }
        launchIntent(
            Intent(
                Intent.ACTION_VIEW,
                Uri.parse(SpotifyModels.authorizationUrl(clientId, state, SpotifyModels.codeChallenge(verifier))),
            ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        )
        showMessage("Conclua a autorização no navegador e volte ao app.")
    }

    private fun disconnectSpotify() {
        spotifyClient.disconnect()
        updateSettings {
            it.copy(
                spotifyConnected = false,
                spotifyAccountName = null,
                isSpotifyConnecting = false,
            )
        }
        showMessage("Conta do Spotify desconectada.")
    }

    /** Handles the `mediadownloader://spotify/callback` deep link from [MainActivity]. */
    fun onSpotifyAuthUri(rawUri: String) {
        val redirect = SpotifyModels.parseRedirect(rawUri) ?: return
        val verifier = spotifyVerifier
        val expectedState = spotifyState
        spotifyVerifier = null
        spotifyState = null
        if (verifier == null || expectedState == null) {
            updateSettings { it.copy(isSpotifyConnecting = false) }
            showMessage("A autorização do Spotify expirou. Tente conectar novamente.")
            return
        }
        if (redirect.error != null) {
            updateSettings { it.copy(isSpotifyConnecting = false) }
            showMessage("A autorização do Spotify foi cancelada.")
            return
        }
        if (redirect.state != expectedState) {
            updateSettings { it.copy(isSpotifyConnecting = false) }
            showMessage("A resposta de autorização não pôde ser validada.")
            return
        }
        val code = redirect.code
        if (code.isNullOrBlank()) {
            updateSettings { it.copy(isSpotifyConnecting = false) }
            showMessage("O Spotify não retornou um código de autorização.")
            return
        }
        viewModelScope.launch {
            try {
                val account = spotifyClient.exchangeCode(code, verifier)
                updateSettings {
                    it.copy(
                        isSpotifyConnecting = false,
                        spotifyConnected = true,
                        spotifyAccountName = account,
                    )
                }
                showMessage("Spotify conectado como $account.")
            } catch (error: Throwable) {
                updateSettings { it.copy(isSpotifyConnecting = false, spotifyConnected = false) }
                showMessage(
                    readableError(error, "Não foi possível concluir a conexão com o Spotify."),
                )
            }
        }
    }

    private fun downloadSpotifyOnYouTube() {
        val media = _state.value.home.spotify ?: return
        val targets = if (media.tracks.isNotEmpty()) {
            media.tracks
        } else {
            listOf(
                SpotifyTrackUi(
                    index = 1,
                    title = media.title,
                    artist = media.subtitle.orEmpty(),
                    album = "",
                    durationText = null,
                    thumbnailUrl = media.thumbnailUrl,
                    query = SpotifyModels.youTubeSearchQuery(media.title, media.subtitle),
                ),
            )
        }
        val startAction: () -> Unit = {
            viewModelScope.launch {
                updateHome { it.copy(isSpotifyDownloading = true) }
                try {
                    targets.forEach { target ->
                        repository.enqueue(
                            sourceUrl = target.query,
                            title = target.title,
                            sourceName = SPOTIFY_SOURCE_NAME,
                            thumbnailUrl = target.thumbnailUrl,
                            options = DownloadOptions(
                                mediaType = MediaType.AUDIO,
                                downloadPlaylist = false,
                            ),
                        )
                    }
                    DownloadService.processQueue(appContext)
                    updateState {
                        it.copy(selectedTab = AppTab.DOWNLOADS, home = HomeUiState())
                    }
                    val message = if (targets.size == 1) {
                        "Buscando a faixa no YouTube e adicionando à fila."
                    } else {
                        "${targets.size} faixas serão buscadas no YouTube e adicionadas à fila."
                    }
                    showMessage(message)
                } catch (error: Throwable) {
                    updateHome { it.copy(isSpotifyDownloading = false) }
                    showMessage(readableError(error, "Não foi possível iniciar os downloads."))
                }
            }
            Unit
        }
        requestStoragePermission?.invoke(startAction) ?: startAction()
    }

    private fun clearAnalysis(cancelJob: Boolean = true) {
        if (cancelJob) analysisJob?.cancel()
        currentAnalysis = null
        updateHome {
            HomeUiState(url = it.url, canPaste = it.canPaste)
        }
    }

    private fun previewAudio() {
        val home = _state.value.home
        if (!home.canPreviewAudio) return
        val analysis = currentAnalysis ?: return
        val effects = AudioEffects(
            speed = home.audioSpeed,
            semitones = home.audioPitchSemitones,
            volumePercent = home.audioVolumePercent,
            bass = home.audioBass,
            echo = home.audioEcho,
            tremolo = home.audioTremolo,
            normalize = home.audioNormalize,
        ).sanitized()
        val source = PreviewSourceResolver.resolve(analysis.formats)
        val sourceUrl = source?.url ?: analysis.sourceUrl
        val includeVideo = home.previewUsesVideo && source?.hasVideo == true && !analysis.isPlaylist
        audioPreviewJob?.cancel()
        audioPreviewJob = viewModelScope.launch {
            updateHome {
                it.copy(isAudioPreviewRendering = true, audioPreviewError = null)
            }
            try {
                val file = withContext(Dispatchers.IO) {
                    engine.initialize()
                    previewRenderer.render(
                        sourceUrl = sourceUrl,
                        effects = effects,
                        outputFile = File(appContext.cacheDir, "preview_clip.mp4"),
                        windowSeconds = previewWindowSeconds(includeVideo),
                        includeVideo = includeVideo,
                        startSeconds = home.trimStartSeconds,
                        trimDurationSeconds = home.trimDurationSeconds,
                        fadeInSeconds = home.fadeInSeconds,
                        fadeOutSeconds = home.fadeOutSeconds,
                    )
                }
                if (!isActive) {
                    // "Parar prévia" foi acionado durante a geração do clip;
                    // não inicie a reprodução de um cancelamento atrasado.
                    return@launch
                }
                previewPlayer.play(
                    file = file,
                    onStarted = {
                        updateHome {
                            it.copy(
                                isAudioPreviewRendering = false,
                                isAudioPreviewPlaying = true,
                                audioPreviewError = null,
                            )
                        }
                    },
                    onFinished = {
                        updateHome { it.copy(isAudioPreviewPlaying = false) }
                    },
                    onError = { message ->
                        updateHome {
                            it.copy(
                                isAudioPreviewPlaying = false,
                                isAudioPreviewRendering = false,
                                audioPreviewError = message,
                            )
                        }
                    },
                )
            } catch (_: CancellationException) {
                throw CancellationException()
            } catch (error: Throwable) {
                updateHome {
                    it.copy(
                        isAudioPreviewRendering = false,
                        isAudioPreviewPlaying = false,
                        audioPreviewError = readableError(
                            error,
                            "Não foi possível gerar a prévia. Confira se este link aponta para uma mídia aberta.",
                        ),
                    )
                }
            }
        }
    }

    private fun stopAudioPreview() {
        audioPreviewJob?.cancel()
        audioPreviewJob = null
        previewRenderer.cancel()
        previewPlayer.stop()
        updateHome {
            it.copy(
                isAudioPreviewRendering = false,
                isAudioPreviewPlaying = false,
            )
        }
    }

    private fun resetAudioEffects() {
        stopAudioPreview()
        updateHome {
            it.copy(
                audioSpeed = 1f,
                audioPitchSemitones = 0f,
                audioVolumePercent = 100,
                audioBass = false,
                audioEcho = false,
                audioTremolo = false,
                audioNormalize = false,
                trimStartSeconds = 0f,
                trimDurationSeconds = null,
                fadeInSeconds = 0f,
                fadeOutSeconds = 0f,
            )
        }
    }

    private fun previewWindowSeconds(includeVideo: Boolean): Float {
        val maxWindow = if (includeVideo) PREVIEW_VIDEO_WINDOW_SECONDS else PREVIEW_WINDOW_SECONDS
        val duration = currentAnalysis?.durationSeconds
        return when {
            duration == null || duration <= 0L -> maxWindow
            else -> minOf(maxWindow, duration.toFloat())
        }
    }

    private fun selectMediaKind(kind: MediaKind) {
        val preview = _state.value.home.preview ?: return
        val enabled = if (kind == MediaKind.VIDEO) preview.supportsVideo else preview.supportsAudio
        if (!enabled) return
        updateHome { home ->
            val qualities = if (kind == MediaKind.VIDEO) preview.videoQualities else preview.audioQualities
            val formats = if (kind == MediaKind.VIDEO) preview.videoFormats else preview.audioFormats
            home.copy(
                selectedKind = kind,
                selectedQualityId = preferredQualityId(kind, qualities),
                selectedFormatId = preferredFormatId(kind, formats),
                includeSubtitles = home.includeSubtitles && kind == MediaKind.VIDEO,
            )
        }
    }

    private fun startDownload() {
        val home = _state.value.home
        val preview = home.preview
        val analysis = currentAnalysis ?: run {
            showMessage("Analise o link antes de iniciar o download.")
            return
        }
        val targets = playlistDownloadTargets(
            preview = preview ?: run {
                showMessage("Analise o link antes de iniciar o download.")
                return
            },
            selection = home.playlistSelection,
            wholePlaylist = home.downloadPlaylist,
            fallbackUrl = analysis.sourceUrl,
            fallbackTitle = analysis.title,
            fallbackThumbnail = analysis.thumbnailUrl,
        )
        if (targets.isEmpty()) {
            showMessage("Selecione pelo menos um item da playlist para baixar.")
            return
        }
        val options = home.toDownloadOptions()
        val wholePlaylist = home.downloadPlaylist && preview.isPlaylist
        val startAction: () -> Unit = {
            viewModelScope.launch {
                updateHome { it.copy(isStartingDownload = true) }
                try {
                    targets.forEach { target ->
                        repository.enqueue(
                            sourceUrl = target.url,
                            title = target.title,
                            sourceName = analysis.sourceName,
                            thumbnailUrl = target.thumbnailUrl,
                            options = if (wholePlaylist) options else options.copy(downloadPlaylist = false),
                        )
                    }
                    DownloadService.processQueue(appContext)
                    updateState {
                        it.copy(
                            selectedTab = AppTab.DOWNLOADS,
                            home = HomeUiState(),
                        )
                    }
                    currentAnalysis = null
                    val message = if (targets.size == 1) {
                        "Download adicionado à fila."
                    } else {
                        "${targets.size} itens adicionados à fila."
                    }
                    showMessage(message)
                } catch (error: Throwable) {
                    updateHome { it.copy(isStartingDownload = false) }
                    showMessage(readableError(error, "Não foi possível iniciar o download."))
                }
            }
            Unit
        }
        requestStoragePermission?.invoke(startAction) ?: startAction()
    }

    private fun changeSiteUrl(value: String) {
        if (_state.value.siteFiles.isDownloading) return
        siteFilesJob?.cancel()
        siteFileAssets = emptyMap()
        updateSiteFiles { current ->
            SiteFilesUiState(
                url = value,
                includePdfs = current.includePdfs,
                includeImages = current.includeImages,
            )
        }
    }

    private fun pasteSiteUrl() {
        if (_state.value.siteFiles.isDownloading) return
        val url = UrlExtraction.extractHttpUrl(clipboardText())
        if (url == null) {
            updateSiteFiles { it.copy(urlError = "A área de transferência não contém um link válido.") }
        } else {
            changeSiteUrl(url)
        }
    }

    private fun scanSiteFiles() {
        val current = _state.value.siteFiles
        val url = current.url.trim()
        if (!isHttpUrl(url)) {
            updateSiteFiles { it.copy(urlError = "Informe uma URL HTTP ou HTTPS válida.") }
            return
        }
        if (!current.includePdfs && !current.includeImages) {
            updateSiteFiles { it.copy(urlError = "Selecione PDFs, imagens ou ambos.") }
            return
        }
        siteFilesJob?.cancel()
        siteFileAssets = emptyMap()
        siteFilesJob = viewModelScope.launch {
            updateSiteFiles {
                it.copy(
                    isScanning = true,
                    urlError = null,
                    pageTitle = null,
                    items = emptyList(),
                    completedDownloads = 0,
                    totalDownloads = 0,
                )
            }
            try {
                val result = siteFileService.discover(
                    url = url,
                    includePdfs = current.includePdfs,
                    includeImages = current.includeImages,
                )
                siteFileAssets = result.files.associateBy(SiteFile::url)
                updateSiteFiles {
                    it.copy(
                        isScanning = false,
                        pageTitle = result.pageTitle,
                        items = result.files.map { it.toUi() },
                    )
                }
                if (result.files.isEmpty()) {
                    showMessage("Nenhum PDF ou imagem pública foi encontrado nesta página.")
                } else {
                    showMessage("${result.files.size} arquivo(s) encontrado(s).")
                }
            } catch (_: CancellationException) {
                throw CancellationException()
            } catch (error: Throwable) {
                siteFileAssets = emptyMap()
                updateSiteFiles {
                    it.copy(
                        isScanning = false,
                        pageTitle = null,
                        items = emptyList(),
                        urlError = readableError(error, "Não foi possível analisar este site."),
                    )
                }
            }
        }
    }

    private fun toggleSiteFile(id: String) {
        if (_state.value.siteFiles.isDownloading) return
        updateSiteFiles { state ->
            state.copy(items = state.items.map { item ->
                if (item.id == id && item.status != SiteFileStatus.SAVED) {
                    item.copy(selected = !item.selected)
                } else item
            })
        }
    }

    private fun selectAllSiteFiles(selected: Boolean) {
        if (_state.value.siteFiles.isDownloading) return
        updateSiteFiles { state ->
            state.copy(items = state.items.map { item ->
                item.copy(selected = selected && item.status != SiteFileStatus.SAVED)
            })
        }
    }

    private fun downloadSelectedSiteFiles() {
        val selected = _state.value.siteFiles.items
            .filter { it.selected && it.status != SiteFileStatus.SAVED }
            .mapNotNull { siteFileAssets[it.id] }
        if (selected.isEmpty()) {
            showMessage("Selecione pelo menos um arquivo para baixar.")
            return
        }
        val startAction: () -> Unit = {
            siteFilesJob?.cancel()
            siteFilesJob = viewModelScope.launch {
                updateSiteFiles {
                    it.copy(
                        isDownloading = true,
                        completedDownloads = 0,
                        totalDownloads = selected.size,
                    )
                }
                var saved = 0
                var failed = 0
                try {
                    selected.forEachIndexed { index, asset ->
                        updateSiteFile(asset.url) {
                            it.copy(
                                status = SiteFileStatus.DOWNLOADING,
                                progress = null,
                                progressText = "Conectando…",
                                errorMessage = null,
                            )
                        }
                        try {
                            val published = siteFileService.download(asset) { downloaded, total ->
                                updateSiteFile(asset.url) { item ->
                                    item.copy(
                                        progress = total?.takeIf { it > 0 }
                                            ?.let { (downloaded.toFloat() / it).coerceIn(0f, 1f) },
                                        progressText = if (total != null) {
                                            "${formatBytes(downloaded)} de ${formatBytes(total)}"
                                        } else {
                                            formatBytes(downloaded)
                                        },
                                    )
                                }
                            }
                            saved += 1
                            updateSiteFile(asset.url) {
                                it.copy(
                                    selected = false,
                                    status = SiteFileStatus.SAVED,
                                    progress = 1f,
                                    progressText = "Salvo em Downloads/MediaDownloader",
                                    savedUri = published.uri,
                                    mimeType = published.mimeType,
                                )
                            }
                        } catch (_: CancellationException) {
                            throw CancellationException()
                        } catch (error: Throwable) {
                            failed += 1
                            updateSiteFile(asset.url) {
                                it.copy(
                                    status = SiteFileStatus.FAILED,
                                    progress = null,
                                    progressText = null,
                                    errorMessage = readableError(error, "Falha ao baixar este arquivo."),
                                )
                            }
                        }
                        updateSiteFiles { it.copy(completedDownloads = index + 1) }
                    }
                    updateSiteFiles { it.copy(isDownloading = false) }
                    when {
                        failed == 0 -> showMessage("$saved arquivo(s) salvo(s) em Downloads/MediaDownloader.")
                        saved == 0 -> showMessage("Nenhum arquivo foi salvo. Revise os erros e tente novamente.")
                        else -> showMessage("$saved arquivo(s) salvo(s) e $failed com falha.")
                    }
                } catch (_: CancellationException) {
                    updateSiteFiles { state ->
                        state.copy(
                            isDownloading = false,
                            items = state.items.map { item ->
                                if (item.status == SiteFileStatus.DOWNLOADING) {
                                    item.copy(
                                        status = SiteFileStatus.READY,
                                        progress = null,
                                        progressText = null,
                                    )
                                } else item
                            },
                        )
                    }
                }
            }
            Unit
        }
        requestStoragePermission?.invoke(startAction) ?: startAction()
    }

    private fun cancelSiteFileDownloads() {
        if (!_state.value.siteFiles.isDownloading) return
        siteFilesJob?.cancel()
        showMessage("Cancelando os downloads de arquivos…")
    }

    private fun openSiteFile(id: String) {
        val item = _state.value.siteFiles.items.firstOrNull { it.id == id }
        openUri(item?.savedUri, item?.mimeType)
    }

    private fun cancelDownload(id: String) {
        DownloadService.cancel(appContext, id)
    }

    private fun retryDownload(id: String) {
        val action = { DownloadService.retry(appContext, id) }
        requestStoragePermission?.invoke(action) ?: action()
    }

    private fun openDownload(id: String) {
        viewModelScope.launch {
            val item = repository.getDownload(id)
            openUri(item?.outputUri, item?.outputMimeType)
        }
    }

    private fun openHistoryItem(id: String) {
        repository.history.value.firstOrNull { it.id == id }?.let {
            openUri(it.fileUri, it.mimeType)
        } ?: showMessage("Este item não está mais no histórico.")
    }

    private fun shareHistoryItem(id: String) {
        val item = repository.history.value.firstOrNull { it.id == id }
        val uri = item?.fileUri?.let(::shareableUri)
        if (item == null || uri == null) {
            showMessage("Este arquivo não está mais disponível.")
            return
        }
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = item.mimeType
            putExtra(Intent.EXTRA_STREAM, uri)
            clipData = ClipData.newUri(appContext.contentResolver, item.fileName, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        launchIntent(Intent.createChooser(intent, "Compartilhar arquivo").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    private fun openUri(rawUri: String?, mimeType: String?) {
        if (rawUri.isNullOrBlank()) {
            showMessage("O arquivo de destino não foi encontrado.")
            return
        }
        launchIntent(
            Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(shareableUri(rawUri), mimeType ?: "*/*")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
            },
        )
    }

    private fun launchIntent(intent: Intent) {
        try {
            appContext.startActivity(intent)
        } catch (_: Exception) {
            showMessage("Nenhum aplicativo compatível foi encontrado para esta ação.")
        }
    }

    private fun shareableUri(rawUri: String): Uri {
        val uri = Uri.parse(rawUri)
        if (!uri.scheme.equals("file", ignoreCase = true)) return uri
        val path = uri.path ?: return uri
        return FileProvider.getUriForFile(
            appContext,
            "${BuildConfig.APPLICATION_ID}.files",
            File(path),
        )
    }

    private fun setProxy(value: String) {
        val trimmed = value.trim()
        val error = if (trimmed.isNotEmpty() && !isPlausibleProxy(trimmed)) {
            "Use o formato scheme://host:porta (ex.: socks5://10.0.2.2:1080)."
        } else {
            null
        }
        if (error == null) settingsStore.proxy = trimmed
        updateSettings { it.copy(proxy = value, proxyError = error) }
    }

    private fun isPlausibleProxy(value: String): Boolean {
        val withScheme = Regex("""^[a-zA-Z][a-zA-Z0-9+.-]*://[^:/\s]+(:[0-9]{1,5})?$""")
        val hostPort = Regex("""^[a-zA-Z0-9._-]+:[0-9]{1,5}$""")
        return withScheme.matches(value) || hostPort.matches(value)
    }

    private fun setRateLimitText(value: String) {
        val digits = value.filter(Char::isDigit).take(6)
        val kbps = digits.toIntOrNull() ?: 0
        settingsStore.rateLimitKbps = kbps
        updateSettings { it.copy(rateLimitText = digits) }
    }

    /** Per-item speed cap; overrides the persistent network limit (desktop parity). */
    private fun setItemRateLimitText(value: String) {
        val digits = value.filter(Char::isDigit).take(6)
        updateHome { it.copy(itemRateLimitText = digits) }
    }

    private fun setFilenameTemplate(value: String) {
        settingsStore.fileNameTemplate = value
        updateSettings { it.copy(filenameTemplate = value) }
    }

    private fun resetFilenameTemplate() {
        settingsStore.fileNameTemplate = ""
        updateSettings { it.copy(filenameTemplate = "") }
        showMessage("Template de nome de arquivo restaurado ao padrão.")
    }

    private fun setDefaultVideoQuality(id: String) {
        settingsStore.defaultVideoQuality = id
        updateSettings { it.copy(defaultVideoQualityId = id) }
    }

    private fun setDefaultVideoFormat(id: String) {
        settingsStore.defaultVideoFormat = id
        updateSettings { it.copy(defaultVideoFormatId = id) }
    }

    private fun setDefaultAudioBitrate(value: Int) {
        settingsStore.defaultAudioBitrate = value
        updateSettings { it.copy(defaultAudioBitrate = value) }
    }

    private fun setDefaultAudioFormat(id: String) {
        settingsStore.defaultAudioFormat = id
        updateSettings { it.copy(defaultAudioFormatId = id) }
    }

    private fun preferredQualityId(kind: MediaKind, qualities: List<ChoiceUi>): String? =
        resolveChoiceId(
            qualities.map(ChoiceUi::id),
            if (kind == MediaKind.VIDEO) settingsStore.defaultVideoQuality
            else settingsStore.defaultAudioBitrate.toString(),
            qualities.recommendedId(),
        )

    private fun preferredFormatId(kind: MediaKind, formats: List<ChoiceUi>): String? =
        resolveChoiceId(
            formats.map(ChoiceUi::id),
            if (kind == MediaKind.VIDEO) settingsStore.defaultVideoFormat
            else settingsStore.defaultAudioFormat,
            formats.recommendedId(),
        )

    private fun exportHistory() {
        val history = repository.history.value
        if (history.isEmpty()) {
            showMessage("O histórico está vazio; nada para exportar.")
            return
        }
        viewModelScope.launch {
            try {
                val csv = withContext(Dispatchers.IO) {
                    val rows = history.map { item ->
                        HistoryCsvRow(
                            id = item.id,
                            title = item.title,
                            fileName = item.fileName,
                            sizeBytes = item.sizeBytes,
                            completedAtIso = java.time.Instant
                                .ofEpochMilli(item.completedAtEpochMs)
                                .toString(),
                            sourceUrl = item.sourceUrl,
                            mimeType = item.mimeType,
                        )
                    }
                    historyToCsv(rows)
                }
                val file = withContext(Dispatchers.IO) {
                    val dir = File(appContext.cacheDir, "shared")
                    dir.mkdirs()
                    File(dir, "media_downloader_history.csv")
                        .also { it.writeText(csv) }
                }
                val uri = FileProvider.getUriForFile(
                    appContext,
                    "${BuildConfig.APPLICATION_ID}.files",
                    file,
                )
                val intent = Intent(Intent.ACTION_SEND).apply {
                    type = "text/csv"
                    putExtra(Intent.EXTRA_STREAM, uri)
                    clipData = ClipData.newUri(appContext.contentResolver, file.name, uri)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                launchIntent(
                    Intent.createChooser(intent, "Exportar histórico")
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                )
            } catch (error: Throwable) {
                showMessage(readableError(error, "Não foi possível exportar o histórico."))
            }
        }
    }

    private fun shareDiagnostics() {
        viewModelScope.launch {
            val settings = _state.value.settings
            val cookieSummary = when {
                settings.cookieFileName != null ->
                    "${settings.cookieFileName} (${settings.cookie?.cookieCount ?: 0} cookies, sessão: ${settings.cookie?.loggedIn == true})"
                else -> "nenhum"
            }
            val diag = buildString {
                appendLine("Media Downloader Android — Diagnóstico")
                appendLine("Versão do app: ${settings.appVersion}")
                appendLine("Versão do yt-dlp: ${settings.ytDlpVersion ?: "desconhecida"}")
                appendLine("Tema: ${settings.theme.label}")
                appendLine("Atualização automática do yt-dlp: ${if (settings.autoUpdateYtDlp) "sim" else "não"}")
                appendLine("Proxy configurado: ${if (settings.proxy.isNotBlank()) "sim" else "não"}")
                appendLine("Limite de velocidade: ${if (settings.rateLimitText.toIntOrNull()?.takeIf { it > 0 } != null) "${settings.rateLimitText} KiB/s" else "sem limite"}")
                appendLine("Template de arquivo: ${settings.filenameTemplate.ifBlank { "padrão" }}")
                appendLine("Padrão vídeo: ${settings.defaultVideoQualityId} / ${settings.defaultVideoFormatId}")
                appendLine("Padrão áudio: ${settings.defaultAudioBitrate} kbps / ${settings.defaultAudioFormatId}")
                appendLine("Cookies global: $cookieSummary")
                appendLine("Perfis de cookies por site: ${settings.cookieSubProfiles.size}")
                appendLine("Pasta de vídeos customizada: ${settings.storageLocations.firstOrNull()?.isCustom == true}")
                appendLine("Spotify conectado: ${if (settings.spotifyConnected) "sim" else "não"}")
            }
            val intent = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_SUBJECT, "Diagnóstico Media Downloader")
                putExtra(Intent.EXTRA_TEXT, diag)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            launchIntent(
                Intent.createChooser(intent, "Compartilhar diagnóstico")
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            )
        }
    }

    private fun saveTheme(theme: ThemePreference) {
        preferences.edit().putString(KEY_THEME, theme.name).apply()
        updateState { it.copy(settings = it.settings.copy(theme = theme)) }
    }

    private fun saveAutoUpdate(enabled: Boolean) {
        preferences.edit().putBoolean(KEY_AUTO_UPDATE, enabled).apply()
        updateState { it.copy(settings = it.settings.copy(autoUpdateYtDlp = enabled)) }
        if (enabled && ytDlpUpdateManager.shouldCheckAutomatically()) {
            checkYtDlpUpdate(showResultMessage = false)
        }
    }

    private fun chooseDownloadLocation(category: StorageCategory) {
        pendingDownloadLocation = category
        requestDownloadLocation?.invoke() ?: run {
            pendingDownloadLocation = null
            showMessage("Não foi possível abrir o seletor de pastas.")
        }
    }

    private fun resetDownloadLocation(category: StorageCategory) {
        storageLocations.reset(category)
        refreshStorageLocations()
        showMessage("${category.label} voltarão para Downloads/MediaDownloader.")
    }

    private fun refreshStorageLocations() {
        updateSettings { it.copy(storageLocations = storageLocationUi()) }
    }

    private fun storageLocationUi(): List<StorageLocationUi> = StorageCategory.entries.map { category ->
        StorageLocationUi(
            category = category,
            locationLabel = storageLocations.label(category),
            isCustom = storageLocations.uri(category) != null,
        )
    }

    private suspend fun refreshYtDlpStatus() {
        try {
            val status = ytDlpUpdateManager.refreshStatus()
            updateSettings { it.withRuntimeStatus(status) }
        } catch (error: Throwable) {
            updateSettings {
                it.copy(
                    updateState = YtDlpUpdateState.FAILED,
                    updateDetail = readableError(
                        error,
                        "Não foi possível validar a instalação atual do yt-dlp.",
                    ),
                )
            }
        }
    }

    private fun checkYtDlpUpdate(showResultMessage: Boolean) {
        if (_state.value.settings.isYtDlpOperationBusy) return
        viewModelScope.launch {
            updateSettings {
                it.copy(
                    updateState = YtDlpUpdateState.CHECKING,
                    updateDetail = "Verificando a versão estável…",
                    availableYtDlpVersion = null,
                )
            }
            try {
                val result = ytDlpUpdateManager.checkForUpdate()
                when (result.outcome) {
                    YtDlpCheckOutcome.AVAILABLE -> {
                        updateSettings {
                            it.withRuntimeStatus(result.status).copy(
                                updateState = YtDlpUpdateState.AVAILABLE,
                                updateDetail = "Versão ${result.latestVersion} disponível. Você escolhe quando instalar.",
                                availableYtDlpVersion = result.latestVersion,
                            )
                        }
                        if (showResultMessage) {
                            showMessage("Há uma atualização do yt-dlp pronta para instalar.")
                        }
                    }

                    YtDlpCheckOutcome.UP_TO_DATE -> {
                        updateSettings {
                            it.withRuntimeStatus(result.status).copy(
                                updateState = YtDlpUpdateState.UP_TO_DATE,
                                updateDetail = "A versão instalada já é a mais recente.",
                                availableYtDlpVersion = null,
                            )
                        }
                        if (showResultMessage) showMessage("O yt-dlp já está atualizado.")
                    }

                    YtDlpCheckOutcome.REJECTED -> {
                        updateSettings {
                            it.withRuntimeStatus(result.status).copy(
                                updateState = YtDlpUpdateState.REJECTED,
                                updateDetail = "A versão ${result.latestVersion} foi descartada neste aparelho. A próxima versão estável poderá ser instalada.",
                                availableYtDlpVersion = null,
                            )
                        }
                        if (showResultMessage) {
                            showMessage("Esta versão foi descartada para proteger seus downloads.")
                        }
                    }
                }
            } catch (error: Throwable) {
                updateSettings {
                    it.copy(
                        updateState = YtDlpUpdateState.FAILED,
                        updateDetail = readableError(
                            error,
                            "Não foi possível verificar agora. A versão instalada não foi alterada.",
                        ),
                        availableYtDlpVersion = null,
                    )
                }
                if (showResultMessage) {
                    showMessage("Não foi possível verificar agora. Tente novamente mais tarde.")
                }
            }
        }
    }

    private fun installYtDlpUpdate() {
        val settings = _state.value.settings
        if (settings.isYtDlpOperationBusy || !settings.canInstallYtDlpUpdate) return
        viewModelScope.launch {
            updateSettings {
                it.copy(
                    updateState = YtDlpUpdateState.UPDATING,
                    updateDetail = "Aguardando operações em andamento e instalando com backup…",
                )
            }
            try {
                val result = ytDlpUpdateManager.installAvailableUpdate()
                when (result.outcome) {
                    YtDlpInstallOutcome.UPDATED -> {
                        updateSettings {
                            it.withRuntimeStatus(result.status).copy(
                                updateState = YtDlpUpdateState.UP_TO_DATE,
                                updateDetail = "Atualização concluída e validada. A versão anterior foi preservada.",
                                availableYtDlpVersion = null,
                            )
                        }
                        showMessage("yt-dlp atualizado com segurança.")
                    }

                    YtDlpInstallOutcome.UP_TO_DATE -> {
                        updateSettings {
                            it.withRuntimeStatus(result.status).copy(
                                updateState = YtDlpUpdateState.UP_TO_DATE,
                                updateDetail = "A versão instalada já é a mais recente.",
                                availableYtDlpVersion = null,
                            )
                        }
                        showMessage("O yt-dlp já está atualizado.")
                    }

                    YtDlpInstallOutcome.REJECTED -> {
                        updateSettings {
                            it.withRuntimeStatus(result.status).copy(
                                updateState = YtDlpUpdateState.REJECTED,
                                updateDetail = "Essa versão já apresentou problema e não será reinstalada.",
                                availableYtDlpVersion = null,
                            )
                        }
                        showMessage("A versão problemática foi ignorada.")
                    }

                    YtDlpInstallOutcome.FAILED -> {
                        updateSettings {
                            it.withRuntimeStatus(result.status).copy(
                                updateState = YtDlpUpdateState.FAILED,
                                updateDetail = "Não foi possível instalar. A versão ${result.status.currentVersion ?: "atual"} continua ativa.",
                                availableYtDlpVersion = result.failedVersion,
                            )
                        }
                        showMessage("A atualização não foi instalada; nada mudou nos seus downloads.")
                    }

                    YtDlpInstallOutcome.RESTORED_AFTER_FAILURE -> {
                        updateSettings {
                            it.withRuntimeStatus(result.status).copy(
                                updateState = YtDlpUpdateState.ROLLED_BACK,
                                updateDetail = "A atualização apresentou um problema. Restauramos a versão ${result.status.currentVersion ?: "anterior"}.",
                                availableYtDlpVersion = null,
                            )
                        }
                        showMessage("A atualização falhou, mas a versão anterior foi restaurada.")
                    }
                }
            } catch (error: Throwable) {
                updateSettings {
                    it.copy(
                        updateState = YtDlpUpdateState.FAILED,
                        updateDetail = readableError(
                            error,
                            "Não foi possível concluir nem restaurar a atualização.",
                        ),
                    )
                }
                showMessage("A atualização precisa de atenção. Reinicie o aplicativo para recuperar.")
            }
        }
    }

    private fun rollbackYtDlp() {
        val settings = _state.value.settings
        if (settings.isYtDlpOperationBusy || !settings.canRollbackYtDlp) return
        viewModelScope.launch {
            updateSettings {
                it.copy(
                    updateState = YtDlpUpdateState.ROLLING_BACK,
                    updateDetail = "Aguardando operações em andamento e restaurando a versão anterior…",
                )
            }
            try {
                val result = ytDlpUpdateManager.rollbackToPrevious()
                when (result.outcome) {
                    YtDlpInstallOutcome.UPDATED -> {
                        updateSettings {
                            it.withRuntimeStatus(result.status).copy(
                                updateState = YtDlpUpdateState.ROLLED_BACK,
                                updateDetail = "Versão ${result.status.currentVersion} restaurada e validada.",
                                availableYtDlpVersion = null,
                            )
                        }
                        showMessage("Versão anterior restaurada. Seus downloads podem continuar.")
                    }

                    YtDlpInstallOutcome.UP_TO_DATE -> {
                        updateSettings {
                            it.withRuntimeStatus(result.status).copy(
                                updateState = YtDlpUpdateState.ROLLED_BACK,
                                updateDetail = "A versão anterior já está ativa.",
                            )
                        }
                    }

                    YtDlpInstallOutcome.FAILED,
                    YtDlpInstallOutcome.RESTORED_AFTER_FAILURE -> {
                        updateSettings {
                            it.withRuntimeStatus(result.status).copy(
                                updateState = YtDlpUpdateState.FAILED,
                                updateDetail = "A versão anterior não passou na validação. Mantivemos a versão ${result.status.currentVersion ?: "atual"}.",
                            )
                        }
                        showMessage("Não foi seguro restaurar essa versão; mantivemos a atual.")
                    }

                    YtDlpInstallOutcome.REJECTED -> Unit
                }
            } catch (error: Throwable) {
                updateSettings {
                    it.copy(
                        updateState = YtDlpUpdateState.FAILED,
                        updateDetail = readableError(error, "Não foi possível restaurar a versão anterior."),
                    )
                }
                showMessage("Não foi possível restaurar a versão anterior.")
            }
        }
    }

    private fun SettingsUiState.withRuntimeStatus(status: YtDlpRuntimeStatus): SettingsUiState = copy(
        ytDlpVersion = status.currentVersion,
        previousYtDlpVersion = status.previousVersion,
        canRollbackYtDlp = status.canRollback,
    )

    private fun launchRepositoryAction(action: suspend () -> Unit) {
        viewModelScope.launch {
            try {
                action()
            } catch (error: Throwable) {
                showMessage(readableError(error, "A operação não pôde ser concluída."))
            }
        }
    }

    private fun updateState(transform: (MobileUiState) -> MobileUiState) = _state.update(transform)
    private fun updateHome(transform: (HomeUiState) -> HomeUiState) =
        updateState { it.copy(home = transform(it.home)) }
    private fun updateSiteFiles(transform: (SiteFilesUiState) -> SiteFilesUiState) =
        updateState { it.copy(siteFiles = transform(it.siteFiles)) }
    private fun updateSiteFile(id: String, transform: (SiteFileUi) -> SiteFileUi) =
        updateSiteFiles { state ->
            state.copy(items = state.items.map { if (it.id == id) transform(it) else it })
        }
    private fun updateSettings(transform: (SettingsUiState) -> SettingsUiState) =
        updateState { it.copy(settings = transform(it.settings)) }

    private fun showMessage(text: String) {
        messageSequence += 1
        updateState { it.copy(message = UiMessage(messageSequence, text)) }
    }

    private fun savedTheme(): ThemePreference = runCatching {
        ThemePreference.valueOf(preferences.getString(KEY_THEME, ThemePreference.SYSTEM.name).orEmpty())
    }.getOrDefault(ThemePreference.SYSTEM)

    private fun savedSpotifyClientId(): String =
        preferences.getString(KEY_SPOTIFY_CLIENT_ID, "").orEmpty()

    @Suppress("DEPRECATION")
    private fun appVersion(): String = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        appContext.packageManager.getPackageInfo(
            appContext.packageName,
            PackageManager.PackageInfoFlags.of(0),
        ).versionName.orEmpty()
    } else {
        appContext.packageManager.getPackageInfo(appContext.packageName, 0).versionName.orEmpty()
    }

    private fun SpotifyMedia.toSpotifyUi(): SpotifyMediaUi = SpotifyMediaUi(
        title = title,
        subtitle = subtitle,
        thumbnailUrl = thumbnailUrl,
        resourceLabel = when {
            isPlaylist -> "Playlist"
            resourceKind == "album" -> "Álbum"
            resourceKind == "artist" -> "Artista"
            resourceKind == "show" -> "Podcast"
            resourceKind == "episode" -> "Episódio"
            resourceKind == "audiobook" -> "Audiolivro"
            resourceKind == "track" -> "Faixa"
            else -> "Spotify"
        },
        webpageUrl = webpageUrl,
        isPlaylist = isPlaylist,
        requiresAuth = requiresAuth,
        authenticated = authenticated,
        notice = notice,
        itemCount = itemCount,
        tracks = tracks.map(::toSpotifyTrackUi),
    )

    private fun toSpotifyTrackUi(track: SpotifyTrack): SpotifyTrackUi = SpotifyTrackUi(
        index = track.index,
        title = track.title,
        artist = track.artist,
        album = track.album,
        durationText = track.durationSeconds?.let(::formatDuration),
        thumbnailUrl = track.thumbnailUrl,
        query = SpotifyModels.youTubeSearchQuery(track.title, track.artist),
    )

    private fun MediaAnalysis.toPreviewUi(): MediaPreviewUi {
        val videoFormats = formats.filter(MediaFormat::hasVideo)
        val audioOnlyFormats = formats.filter { it.hasAudio && !it.hasVideo }
        val heights = videoFormats.mapNotNull(MediaFormat::height).distinct().sortedDescending()
        return MediaPreviewUi(
            title = title,
            creator = uploader,
            sourceName = sourceName ?: Uri.parse(sourceUrl).host.orEmpty().ifBlank { "Origem da mídia" },
            sourceUrl = sourceUrl,
            durationText = durationSeconds?.let(::formatDuration),
            durationSeconds = durationSeconds?.toFloat(),
            thumbnailUrl = thumbnailUrl,
            isPlaylist = isPlaylist,
            playlistItemCount = playlistItemCount,
            playlistItems = playlistItems.map { item ->
                PlaylistItemUi(
                    index = item.index,
                    id = item.id,
                    title = item.title,
                    url = item.url,
                    thumbnailUrl = item.thumbnailUrl,
                )
            },
            supportsVideo = videoFormats.isNotEmpty() || isPlaylist,
            supportsAudio = audioOnlyFormats.isNotEmpty() || formats.any(MediaFormat::hasAudio) || isPlaylist,
            supportsSubtitles = supportsSubtitles,
            videoQualities = buildList {
                add(ChoiceUi("best", "Melhor disponível", "Escolhe a melhor combinação de vídeo e áudio.", true))
                heights.filter { it <= 2160 }.forEach { height ->
                    add(ChoiceUi("height:$height", "${height}p", "Limite de resolução: ${height}p"))
                }
            }.distinctBy(ChoiceUi::id),
            audioQualities = listOf(
                ChoiceUi("320", "320 kbps", "Maior qualidade e arquivo maior."),
                ChoiceUi("192", "192 kbps", "Bom equilíbrio entre qualidade e tamanho.", true),
                ChoiceUi("128", "128 kbps", "Arquivo menor."),
            ),
            videoFormats = listOf(
                ChoiceUi("mp4", "MP4", "Maior compatibilidade com aparelhos.", true),
                ChoiceUi("mkv", "MKV", "Contêiner flexível para vídeo e legendas."),
                ChoiceUi("webm", "WEBM", "Formato aberto para web."),
            ),
            audioFormats = listOf(
                ChoiceUi("mp3", "MP3", "Maior compatibilidade.", true),
                ChoiceUi("m4a", "M4A", "Áudio AAC em contêiner MP4."),
                ChoiceUi("opus", "OPUS", "Boa qualidade com arquivo compacto."),
                ChoiceUi("flac", "FLAC", "Áudio sem perdas."),
                ChoiceUi("wav", "WAV", "Áudio PCM sem compressão."),
            ),
        )
    }

    private fun HomeUiState.withAnalysis(preview: MediaPreviewUi, kind: MediaKind): HomeUiState {
        val qualities = if (kind == MediaKind.VIDEO) preview.videoQualities else preview.audioQualities
        val formats = if (kind == MediaKind.VIDEO) preview.videoFormats else preview.audioFormats
        return copy(
            isAnalyzing = false,
            preview = preview,
            selectedKind = kind,
            selectedQualityId = preferredQualityId(kind, qualities),
            selectedFormatId = preferredFormatId(kind, formats),
            downloadPlaylist = preview.isPlaylist,
            playlistSelection = if (preview.isPlaylist) {
                preview.playlistItems.mapTo(mutableSetOf(), PlaylistItemUi::index)
            } else {
                emptySet()
            },
            includeSubtitles = false,
            analysisHint = null,
        )
    }

    private fun HomeUiState.toDownloadOptions(): DownloadOptions {
        val quality = selectedQualityId.orEmpty()
        val format = selectedFormatId.orEmpty()
        return if (selectedKind == MediaKind.AUDIO) {
            DownloadOptions(
                mediaType = MediaType.AUDIO,
                rateLimitKbps = itemRateLimitText.toIntOrNull() ?: 0,
                maxVideoHeight = null,
                audioFormat = AudioFormat.entries.firstOrNull { it.extension == format } ?: AudioFormat.MP3,
                audioBitrateKbps = quality.toIntOrNull()?.coerceIn(32, 320) ?: 192,
                downloadPlaylist = downloadPlaylist,
                audioSpeed = audioSpeed,
                audioPitchSemitones = audioPitchSemitones,
                audioVolumePercent = audioVolumePercent,
                audioBass = audioBass,
                audioEcho = audioEcho,
                audioTremolo = audioTremolo,
                audioNormalize = audioNormalize,
                trimStartSeconds = trimStartSeconds,
                trimDurationSeconds = trimDurationSeconds,
                fadeInSeconds = fadeInSeconds,
                fadeOutSeconds = fadeOutSeconds,
            )
        } else {
            DownloadOptions(
                mediaType = MediaType.VIDEO,
                editorCompatible = editorCompatible,
                rateLimitKbps = itemRateLimitText.toIntOrNull() ?: 0,
                maxVideoHeight = quality.removePrefix("height:").toIntOrNull(),
                videoContainer = VideoContainer.entries.firstOrNull { it.extension == format } ?: VideoContainer.MP4,
                downloadPlaylist = downloadPlaylist,
                includeSubtitles = includeSubtitles,
                audioSpeed = audioSpeed,
                audioPitchSemitones = audioPitchSemitones,
                audioVolumePercent = audioVolumePercent,
                audioBass = audioBass,
                audioEcho = audioEcho,
                audioTremolo = audioTremolo,
                audioNormalize = audioNormalize,
                trimStartSeconds = trimStartSeconds,
                trimDurationSeconds = trimDurationSeconds,
                fadeInSeconds = fadeInSeconds,
                fadeOutSeconds = fadeOutSeconds,
            )
        }
    }

    private fun toDownloadUi(item: DownloadItem): DownloadItemUi = DownloadItemUi(
        id = item.id,
        title = item.title,
        detail = listOfNotNull(item.sourceName, item.outputFileName).joinToString(" • ").ifBlank {
            if (item.options.mediaType == MediaType.VIDEO) "Vídeo" else "Áudio"
        },
        status = when (item.state) {
            DownloadState.QUEUED -> DownloadStatus.QUEUED
            DownloadState.INITIALIZING -> DownloadStatus.PREPARING
            DownloadState.DOWNLOADING -> DownloadStatus.DOWNLOADING
            DownloadState.PROCESSING -> DownloadStatus.PROCESSING
            DownloadState.COMPLETED -> DownloadStatus.COMPLETED
            DownloadState.FAILED -> DownloadStatus.FAILED
            DownloadState.CANCELLED -> DownloadStatus.CANCELLED
        },
        progress = if (item.state in setOf(
                DownloadState.DOWNLOADING,
                DownloadState.PROCESSING,
                DownloadState.COMPLETED,
            )
        ) item.progress / 100f else null,
        progressText = item.statusLine ?: if (item.progress > 0) "${item.progress}%" else null,
        etaText = item.etaSeconds?.takeIf { it > 0 }?.let { "ETA ${formatDuration(it)}" },
        errorMessage = item.errorMessage,
        thumbnailUrl = item.thumbnailUrl,
        canOpen = !item.outputUri.isNullOrBlank(),
    )

    private fun toHistoryUi(item: HistoryItem): HistoryItemUi = HistoryItemUi(
        id = item.id,
        title = item.title,
        detail = item.fileName,
        completedAtText = DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT)
            .format(Date(item.completedAtEpochMs)),
        fileSizeText = formatBytes(item.sizeBytes),
        thumbnailUrl = item.thumbnailUrl,
        canOpen = item.fileUri.isNotBlank(),
        canShare = item.fileUri.isNotBlank(),
    )

    private fun SiteFile.toUi(): SiteFileUi = SiteFileUi(
        id = url,
        url = url,
        name = name,
        sourceHost = Uri.parse(url).host.orEmpty().removePrefix("www.").ifBlank { "Site" },
        kind = when (kind) {
            SiteFileKind.PDF -> SiteFileKindUi.PDF
            SiteFileKind.IMAGE -> SiteFileKindUi.IMAGE
        },
        mimeType = mimeType,
    )

    companion object {
        private const val PREFERENCES_NAME = "mobile_settings"
        private const val KEY_THEME = "theme"
        private const val KEY_AUTO_UPDATE = "auto_update_ytdlp"
        private const val KEY_SPOTIFY_CLIENT_ID = "spotify_client_id"
        private const val SPOTIFY_SOURCE_NAME = "YouTube (via Spotify)"
        private const val QR_CODE_MIME_TYPE = "image/png"
        private const val PREVIEW_WINDOW_SECONDS = 30f
        private const val PREVIEW_VIDEO_WINDOW_SECONDS = 12f
        private const val MAX_FADE_SECONDS = 30f
        private const val WIDGET_ACTION_DOWNLOAD = "com.mediadownloader.mobile.action.WIDGET_DOWNLOAD"
        private const val CREATE_SITE_PROFILE_ID = "__create__"
        private const val MAX_BULK_URLS = 10

        private fun List<ChoiceUi>.recommendedId(): String? =
            firstOrNull(ChoiceUi::recommended)?.id ?: firstOrNull()?.id

        private fun isHttpUrl(value: String): Boolean = UrlExtraction.isValidHttpUrl(value)

        private fun extractHttpUrl(value: String): String? = UrlExtraction.extractHttpUrl(value)

        private fun formatDuration(seconds: Long): String {
            val hours = seconds / 3600
            val minutes = (seconds % 3600) / 60
            val remaining = seconds % 60
            return if (hours > 0) "%d:%02d:%02d".format(hours, minutes, remaining)
            else "%d:%02d".format(minutes, remaining)
        }

        private fun formatBytes(bytes: Long): String {
            if (bytes < 1024) return "$bytes B"
            val units = arrayOf("KB", "MB", "GB", "TB")
            var value = bytes / 1024.0
            var index = 0
            while (value >= 1024 && index < units.lastIndex) {
                value /= 1024
                index += 1
            }
            return "%.1f %s".format(value, units[index])
        }

        private fun readableError(error: Throwable, fallback: String): String =
            generateSequence(error) { it.cause }
                .mapNotNull { it.message?.trim()?.takeIf(String::isNotBlank) }
                .firstOrNull()
                ?.lineSequence()
                ?.lastOrNull(String::isNotBlank)
                ?.removePrefix("ERROR:")
                ?.trim()
                ?.take(800)
                ?: fallback
    }
}
