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
import com.mediadownloader.mobile.data.VideoContainer
import com.mediadownloader.mobile.download.AndroidDownloadEngine
import com.mediadownloader.mobile.download.DownloadService
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
import com.mediadownloader.mobile.ui.ThemePreference
import com.mediadownloader.mobile.ui.UiMessage
import com.mediadownloader.mobile.ui.YtDlpUpdateState
import com.yausername.youtubedl_android.YoutubeDL
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
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
import kotlinx.coroutines.withContext
import java.text.DateFormat
import java.io.File
import java.util.Date

class MediaDownloaderViewModel(application: Application) : AndroidViewModel(application), MobileUiController {
    private val appContext = application.applicationContext
    private val repository = DownloadRepository.getInstance(appContext)
    private val engine = AndroidDownloadEngine(appContext)
    private val preferences = appContext.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)
    private val analysisMutex = Mutex()

    private val _state = MutableStateFlow(
        MobileUiState(
            settings = SettingsUiState(
                theme = savedTheme(),
                autoUpdateYtDlp = preferences.getBoolean(KEY_AUTO_UPDATE, true),
                appVersion = appVersion(),
                ytDlpVersion = YoutubeDL.getInstance().versionName(appContext)
                    ?: YoutubeDL.getInstance().version(appContext),
            ),
        ),
    )
    override val state: StateFlow<MobileUiState> = _state.asStateFlow()

    private var currentAnalysis: MediaAnalysis? = null
    private var analysisJob: Job? = null
    private var messageSequence = 0L
    private var requestStoragePermission: ((() -> Unit) -> Unit)? = null
    private var pendingStorageAction: (() -> Unit)? = null

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
        if (_state.value.settings.autoUpdateYtDlp) {
            updateYtDlp(showUpToDateMessage = false)
        }
    }

    override fun onAction(action: MobileUiAction) {
        when (action) {
            is MobileUiAction.Navigate -> updateState { it.copy(selectedTab = action.tab) }
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
            MobileUiAction.CheckYtDlpUpdate,
            MobileUiAction.UpdateYtDlp -> updateYtDlp(showUpToDateMessage = true)
            MobileUiAction.ChooseDownloadLocation -> showMessage(
                "O Android salva os arquivos em Downloads/MediaDownloader.",
            )
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
    }

    private fun updateYtDlp(showUpToDateMessage: Boolean) {
        val current = _state.value.settings.updateState
        if (current == YtDlpUpdateState.CHECKING || current == YtDlpUpdateState.UPDATING) return
        viewModelScope.launch {
            updateSettings {
                it.copy(updateState = YtDlpUpdateState.CHECKING, updateDetail = "Verificando a versão estável…")
            }
            try {
                val result = withContext(Dispatchers.IO) {
                    engine.initialize()
                    YoutubeDL.getInstance().updateYoutubeDL(appContext, YoutubeDL.UpdateChannel.STABLE)
                }
                val version = YoutubeDL.getInstance().versionName(appContext)
                    ?: YoutubeDL.getInstance().version(appContext)
                val changed = result == YoutubeDL.UpdateStatus.DONE
                updateSettings {
                    it.copy(
                        updateState = YtDlpUpdateState.UP_TO_DATE,
                        updateDetail = if (changed) "yt-dlp atualizado com sucesso." else "A versão instalada já é a mais recente.",
                        ytDlpVersion = version,
                    )
                }
                if (changed || showUpToDateMessage) {
                    showMessage(if (changed) "yt-dlp atualizado com sucesso." else "O yt-dlp já está atualizado.")
                }
            } catch (error: Throwable) {
                updateSettings {
                    it.copy(
                        updateState = YtDlpUpdateState.FAILED,
                        updateDetail = readableError(error, "Não foi possível atualizar o yt-dlp."),
                    )
                }
                if (showUpToDateMessage) showMessage("Não foi possível atualizar o yt-dlp agora.")
            }
        }
    }

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
