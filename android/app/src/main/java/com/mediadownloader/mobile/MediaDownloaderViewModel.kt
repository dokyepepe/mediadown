package com.mediadownloader.mobile

import android.app.Application
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.core.content.FileProvider
import com.mediadownloader.mobile.data.AudioFormat
import com.mediadownloader.mobile.data.DownloadItem
import com.mediadownloader.mobile.data.DownloadOptions
import com.mediadownloader.mobile.data.DownloadRepository
import com.mediadownloader.mobile.data.DownloadState
import com.mediadownloader.mobile.data.HistoryItem
import com.mediadownloader.mobile.data.MediaAnalysis
import com.mediadownloader.mobile.data.MediaFormat
import com.mediadownloader.mobile.data.MediaType
import com.mediadownloader.mobile.data.StorageCategory
import com.mediadownloader.mobile.data.StorageLocationStore
import com.mediadownloader.mobile.data.VideoContainer
import com.mediadownloader.mobile.download.AndroidDownloadEngine
import com.mediadownloader.mobile.download.DownloadService
import com.mediadownloader.mobile.site.AndroidSiteFileService
import com.mediadownloader.mobile.site.SiteFile
import com.mediadownloader.mobile.site.SiteFileKind
import com.mediadownloader.mobile.support.SupportConfig
import com.mediadownloader.mobile.ui.AppTab
import com.mediadownloader.mobile.ui.ChoiceUi
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
import com.mediadownloader.mobile.ui.SettingsUiState
import com.mediadownloader.mobile.ui.StorageLocationUi
import com.mediadownloader.mobile.ui.SiteFileKindUi
import com.mediadownloader.mobile.ui.SiteFileStatus
import com.mediadownloader.mobile.ui.SiteFileUi
import com.mediadownloader.mobile.ui.SiteFilesUiState
import com.mediadownloader.mobile.ui.ThemePreference
import com.mediadownloader.mobile.ui.UiMessage
import com.mediadownloader.mobile.ui.YtDlpUpdateState
import com.mediadownloader.mobile.update.YtDlpCheckOutcome
import com.mediadownloader.mobile.update.YtDlpInstallOutcome
import com.mediadownloader.mobile.update.YtDlpRuntimeStatus
import com.mediadownloader.mobile.update.YtDlpUpdateManager
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import java.text.DateFormat
import java.io.File
import java.util.Date

class MediaDownloaderViewModel(application: Application) : AndroidViewModel(application), MobileUiController {
    private val appContext = application.applicationContext
    private val repository = DownloadRepository.getInstance(appContext)
    private val engine = AndroidDownloadEngine(appContext)
    private val siteFileService = AndroidSiteFileService(appContext)
    private val preferences = appContext.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)
    private val storageLocations = StorageLocationStore(appContext)
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
    }

    override fun onAction(action: MobileUiAction) {
        when (action) {
            is MobileUiAction.Navigate -> updateState { it.copy(selectedTab = action.tab) }
            is MobileUiAction.QrCodeUrlChanged -> updateState {
                it.copy(qrCode = it.qrCode.copy(url = action.value, urlError = null, generatedUrl = null))
            }
            MobileUiAction.GenerateQrCode -> generateQrCode()
            is MobileUiAction.ReceiveSharedUrl -> receiveUrl(action.value)
            is MobileUiAction.UrlChanged -> updateHome {
                it.copy(url = action.value, urlError = null, preview = null, analysisHint = null)
            }.also {
                analysisJob?.cancel()
                currentAnalysis = null
            }
            MobileUiAction.PasteUrl -> pasteUrl()
            MobileUiAction.AnalyzeUrl -> analyzeUrl()
            MobileUiAction.ClearAnalysis -> clearAnalysis()
            is MobileUiAction.SelectMediaKind -> selectMediaKind(action.kind)
            is MobileUiAction.SelectQuality -> updateHome { it.copy(selectedQualityId = action.id) }
            is MobileUiAction.SelectFormat -> updateHome { it.copy(selectedFormatId = action.id) }
            is MobileUiAction.SetDownloadPlaylist -> updateHome { it.copy(downloadPlaylist = action.enabled) }
            is MobileUiAction.SetIncludeSubtitles -> updateHome { it.copy(includeSubtitles = action.enabled) }
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
            is MobileUiAction.CancelDownload -> cancelDownload(action.id)
            is MobileUiAction.RetryDownload -> retryDownload(action.id)
            is MobileUiAction.RemoveDownload -> launchRepositoryAction { repository.deleteDownload(action.id) }
            is MobileUiAction.OpenDownload -> openDownload(action.id)
            MobileUiAction.ClearFinishedDownloads -> launchRepositoryAction(repository::clearFinishedDownloads)
            is MobileUiAction.OpenHistoryItem -> openHistoryItem(action.id)
            is MobileUiAction.ShareHistoryItem -> shareHistoryItem(action.id)
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
        val value = when (intent?.action) {
            Intent.ACTION_SEND -> intent.getStringExtra(Intent.EXTRA_TEXT)
            Intent.ACTION_VIEW -> intent.dataString
            else -> null
        }
        value?.let { onAction(MobileUiAction.ReceiveSharedUrl(it)) }
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

    private fun receiveUrl(raw: String) {
        val url = extractHttpUrl(raw)
        if (url == null) {
            showMessage("O conteúdo compartilhado não contém uma URL HTTP ou HTTPS válida.")
            return
        }
        clearAnalysis(cancelJob = true)
        updateState {
            it.copy(
                selectedTab = AppTab.HOME,
                home = it.home.copy(url = url, urlError = null),
            )
        }
    }

    private fun pasteUrl() {
        val clipboard = appContext.getSystemService(ClipboardManager::class.java)
        val raw = clipboard?.primaryClip?.getItemAt(0)?.coerceToText(appContext)?.toString().orEmpty()
        val url = extractHttpUrl(raw)
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

    private fun analyzeUrl() {
        val url = _state.value.home.url.trim()
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
                }
            }
        }
    }

    private fun clearAnalysis(cancelJob: Boolean = true) {
        if (cancelJob) analysisJob?.cancel()
        currentAnalysis = null
        updateHome {
            HomeUiState(url = it.url, canPaste = it.canPaste)
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
                selectedQualityId = qualities.recommendedId(),
                selectedFormatId = formats.recommendedId(),
                includeSubtitles = home.includeSubtitles && kind == MediaKind.VIDEO,
            )
        }
    }

    private fun startDownload() {
        val home = _state.value.home
        val analysis = currentAnalysis ?: run {
            showMessage("Analise o link antes de iniciar o download.")
            return
        }
        val options = home.toDownloadOptions()
        val startAction: () -> Unit = {
            viewModelScope.launch {
                updateHome { it.copy(isStartingDownload = true) }
                try {
                    repository.enqueue(
                        sourceUrl = analysis.sourceUrl,
                        title = analysis.title,
                        sourceName = analysis.sourceName,
                        thumbnailUrl = analysis.thumbnailUrl,
                        options = options,
                    )
                    DownloadService.processQueue(appContext)
                    updateState {
                        it.copy(
                            selectedTab = AppTab.DOWNLOADS,
                            home = HomeUiState(),
                        )
                    }
                    currentAnalysis = null
                    showMessage("Download adicionado à fila.")
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
        val clipboard = appContext.getSystemService(ClipboardManager::class.java)
        val raw = clipboard?.primaryClip?.getItemAt(0)?.coerceToText(appContext)?.toString().orEmpty()
        val url = extractHttpUrl(raw)
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

    @Suppress("DEPRECATION")
    private fun appVersion(): String = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        appContext.packageManager.getPackageInfo(
            appContext.packageName,
            PackageManager.PackageInfoFlags.of(0),
        ).versionName.orEmpty()
    } else {
        appContext.packageManager.getPackageInfo(appContext.packageName, 0).versionName.orEmpty()
    }

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
            thumbnailUrl = thumbnailUrl,
            isPlaylist = isPlaylist,
            playlistItemCount = playlistItemCount,
            supportsVideo = videoFormats.isNotEmpty() || isPlaylist,
            supportsAudio = audioOnlyFormats.isNotEmpty() || formats.any(MediaFormat::hasAudio) || isPlaylist,
            supportsSubtitles = true,
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
            selectedQualityId = qualities.recommendedId(),
            selectedFormatId = formats.recommendedId(),
            downloadPlaylist = preview.isPlaylist,
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
                maxVideoHeight = null,
                audioFormat = AudioFormat.entries.firstOrNull { it.extension == format } ?: AudioFormat.MP3,
                audioBitrateKbps = quality.toIntOrNull()?.coerceIn(32, 320) ?: 192,
                downloadPlaylist = downloadPlaylist,
            )
        } else {
            DownloadOptions(
                mediaType = MediaType.VIDEO,
                maxVideoHeight = quality.removePrefix("height:").toIntOrNull(),
                videoContainer = VideoContainer.entries.firstOrNull { it.extension == format } ?: VideoContainer.MP4,
                downloadPlaylist = downloadPlaylist,
                includeSubtitles = includeSubtitles,
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

        private fun List<ChoiceUi>.recommendedId(): String? =
            firstOrNull(ChoiceUi::recommended)?.id ?: firstOrNull()?.id

        private fun isHttpUrl(value: String): Boolean = runCatching {
            val uri = Uri.parse(value.trim())
            (uri.scheme.equals("http", true) || uri.scheme.equals("https", true)) && !uri.host.isNullOrBlank()
        }.getOrDefault(false)

        private fun extractHttpUrl(value: String): String? = value
            .split(Regex("\\s+"))
            .map { it.trim().trimEnd('.', ',', ';', ')', ']', '}') }
            .firstOrNull(::isHttpUrl)

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
