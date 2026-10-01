package com.mediadownloader.mobile.download

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import androidx.core.net.toUri
import com.mediadownloader.mobile.R
import com.mediadownloader.mobile.data.DownloadGate
import com.mediadownloader.mobile.data.DownloadItem
import com.mediadownloader.mobile.data.DownloadRepository
import com.mediadownloader.mobile.data.HistoryItem
import com.mediadownloader.mobile.data.MobileSettingsStore
import com.mediadownloader.mobile.widget.DownloadListWidget
import com.mediadownloader.mobile.widget.QuickDownloadWidget
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Persistent download worker with up to [MobileSettingsStore.parallelDownloads]
 * concurrent downloads and optional Wi-Fi/window gating. Add this service to the
 * manifest with foregroundServiceType "dataSync" and declare FOREGROUND_SERVICE
 * plus FOREGROUND_SERVICE_DATA_SYNC where applicable.
 */
class DownloadService : Service() {
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val kicks = MutableSharedFlow<Unit>(extraBufferCapacity = 4)
    private val recoveryGate = CompletableDeferred<Unit>()
    private val workerStarted = AtomicBoolean(false)
    private val activeDownloads = AtomicInteger(0)
    private val idleWorkers = AtomicInteger(0)
    private val activeIds: MutableSet<String> = ConcurrentHashMap.newKeySet()
    private val foregroundLock = Any()
    private var keepAwakeLock: PowerManager.WakeLock? = null
    private lateinit var repository: DownloadRepository
    private lateinit var engine: AndroidDownloadEngine
    private lateinit var notificationManager: NotificationManager
    private lateinit var settings: MobileSettingsStore

    @Volatile
    private var latestStartId: Int = 0

    @Volatile
    private var workerCountAtStart = 0

    private val connectivityManager by lazy(LazyThreadSafetyMode.NONE) {
        getSystemService(ConnectivityManager::class.java)
    }

    private val connectivityCallback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) = kickWorkers()
        override fun onLost(network: Network) = kickWorkers()
        override fun onCapabilitiesChanged(network: Network, networkCapabilities: NetworkCapabilities) {
            if (networkCapabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)) kickWorkers()
        }
    }

    override fun onCreate() {
        super.onCreate()
        repository = DownloadRepository.getInstance(applicationContext)
        engine = AndroidDownloadEngine(applicationContext)
        settings = MobileSettingsStore.open(applicationContext)
        notificationManager = getSystemService(NotificationManager::class.java)
        createNotificationChannel()
        serviceScope.launch { ensureForeground("Preparando a fila", indeterminate = true) }
        startWorkers()
        connectivityManager.registerDefaultNetworkCallback(connectivityCallback)
        serviceScope.launch {
            runCatching { repository.recoverInterrupted() }
            recoveryGate.complete(Unit)
            kickWorkers()
        }
        serviceScope.launch { superviseStop() }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        latestStartId = startId
        workerCountAtStart = settings.parallelDownloads.coerceIn(1, MAX_PARALLEL)
        serviceScope.launch { ensureForeground("Verificando a fila", indeterminate = true) }
        syncKeepAwakeLock()
        when (intent?.action) {
            ACTION_CANCEL -> intent.getStringExtra(EXTRA_DOWNLOAD_ID)?.let(::requestCancellation)
            ACTION_PAUSE -> intent.getStringExtra(EXTRA_DOWNLOAD_ID)?.let(::requestPause)
            ACTION_RESUME -> intent.getStringExtra(EXTRA_DOWNLOAD_ID)?.let(::requestResume)
            ACTION_RETRY -> intent.getStringExtra(EXTRA_DOWNLOAD_ID)?.let { id ->
                serviceScope.launch {
                    repository.retry(id)
                    kickWorkers()
                }
            }
            ACTION_PROCESS_QUEUE, null -> kickWorkers()
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        activeIds.forEach { id ->
            engine.cancel(id)
            notificationManager.cancel(id.hashCode())
        }
        releaseKeepAwakeLock()
        try {
            connectivityManager.unregisterNetworkCallback(connectivityCallback)
        } catch (_: IllegalArgumentException) {
            // never registered; safe to ignore
        }
        serviceScope.cancel()
        super.onDestroy()
    }

    override fun onTimeout(startId: Int, fgsType: Int) {
        activeIds.forEach { id ->
            engine.cancel(id)
            notificationManager.cancel(id.hashCode())
        }
        releaseKeepAwakeLock()
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf(startId)
    }

    private fun syncKeepAwakeLock() {
        if (settings.keepAwakeDuringDownloads && activeDownloads.get() > 0) {
            acquireKeepAwakeLock()
        } else {
            releaseKeepAwakeLock()
        }
    }

    private fun acquireKeepAwakeLock() {
        if (keepAwakeLock != null) return
        val powerManager = getSystemService(PowerManager::class.java) ?: return
        keepAwakeLock = powerManager.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK,
            "$packageName:downloads",
        ).apply {
            setReferenceCounted(false)
            // Safety net: a download can outlive any single file, but the lock must not
            // be held forever if the release path is missed.
            acquire(KEEP_AWAKE_TIMEOUT_MS)
        }
    }

    private fun releaseKeepAwakeLock() {
        keepAwakeLock?.takeIf { it.isHeld }?.release()
        keepAwakeLock = null
    }

    private fun startWorkers() {
        if (!workerStarted.compareAndSet(false, true)) return
        val count = workerCountAtStart.let { if (it > 0) it else settings.parallelDownloads.coerceIn(1, MAX_PARALLEL) }
        idleWorkers.set(count)
        repeat(count) { serviceScope.launch { workerLoop() } }
    }

    private suspend fun workerLoop() {
        recoveryGate.await()
        while (serviceScope.isActive) {
            val pause = DownloadGate.pauseReason(this@DownloadService)
            if (pause != null) {
                showPausedNotification(pause)
                waitForKick()
                continue
            }
            val item = repository.claimNextQueued()
            if (item == null) {
                waitForKick()
                continue
            }
            activeDownloads.incrementAndGet()
            try {
                runDownload(item)
            } finally {
                activeDownloads.decrementAndGet()
                kickWorkers()
            }
        }
    }

    private suspend fun waitForKick() {
        idleWorkers.incrementAndGet()
        try {
            withTimeoutOrNull(KICK_WAIT_MS) { kicks.first() }
        } finally {
            idleWorkers.decrementAndGet()
        }
    }

    /** Stops the persistent service once the queue is drained and nothing runs. */
    private suspend fun superviseStop() {
        recoveryGate.await()
        while (serviceScope.isActive) {
            delay(STOP_POLL_MS)
            if (activeDownloads.get() > 0) continue
            if (DownloadGate.pauseReason(this@DownloadService) != null) continue
            if (repository.nextQueued() != null) continue
            if (idleWorkers.get() < workerCountAtStart.coerceAtLeast(1)) continue
            val startId = latestStartId
            if (stopSelfResult(startId)) {
                stopForeground(STOP_FOREGROUND_REMOVE)
                return
            }
        }
    }

    private suspend fun runDownload(queuedItem: DownloadItem) {
        val id = queuedItem.id
        activeIds += id
        syncKeepAwakeLock()
        var lastPersisted = -1
        var lastUpdateMs = 0L
        try {
            engine.prepare(id)
            ensureForeground("Preparando ${queuedItem.title}", indeterminate = true, item = queuedItem)
            QuickDownloadWidget.refresh(this, force = true)
            DownloadListWidget.refresh(this)
            val result = engine.download(queuedItem) { progress ->
                val callbackItem = repository.downloads.value.firstOrNull { it.id == id }
                    ?: queuedItem
                val now = System.currentTimeMillis()
                val shouldPersist = progress.percent != lastPersisted &&
                    (progress.percent >= lastPersisted + 1 || now - lastUpdateMs >= 750)
                if (!shouldPersist) return@download
                lastPersisted = progress.percent
                lastUpdateMs = now
                val label = if (progress.processing) {
                    "Processando ${callbackItem.title}"
                } else {
                    "Baixando ${callbackItem.title}"
                }
                ensureForeground(
                    text = label,
                    progress = progress.percent,
                    indeterminate = progress.percent <= 0,
                    item = callbackItem,
                )
                showItemProgressNotification(
                    item = callbackItem,
                    percent = progress.percent,
                    text = label,
                    indeterminate = progress.percent <= 0,
                )
                serviceScope.launch {
                    repository.markProgress(
                        id = id,
                        progress = progress.percent,
                        etaSeconds = progress.etaSeconds,
                        statusLine = progress.outputLine,
                        processing = progress.processing,
                    )
                    DownloadListWidget.refresh(this@DownloadService)
                }
                QuickDownloadWidget.refresh(this@DownloadService)
            }
            val current = repository.getDownload(id)
            if (current?.state == com.mediadownloader.mobile.data.DownloadState.CANCELLED) return
            val completed = repository.markCompleted(id, result.primaryFile) ?: queuedItem
            val completedAt = System.currentTimeMillis()
            result.files.forEach { file ->
                repository.addHistory(
                    HistoryItem.create(
                        download = completed,
                        fileUri = file.uri,
                        fileName = file.displayName,
                        mimeType = file.mimeType,
                        sizeBytes = file.sizeBytes,
                        completedAtEpochMs = completedAt,
                    ),
                )
            }
            showTerminalNotification(
                item = completed,
                text = if (result.files.size == 1) {
                    "Salvo em Downloads/MediaDownloader"
                } else {
                    "${result.files.size} arquivos salvos"
                },
                success = true,
            )
            QuickDownloadWidget.refresh(this, force = true)
            DownloadListWidget.refresh(this)
        } catch (_: DownloadCancelledException) {
            if (engine.wasPaused(id)) {
                // Paused on purpose: the partial file stays for the next attempt.
                repository.pause(id)
            } else {
                repository.cancel(id)
                showTerminalNotification(queuedItem, "Download cancelado", success = false)
            }
            QuickDownloadWidget.refresh(this, force = true)
            DownloadListWidget.refresh(this)
        } catch (_: CancellationException) {
            engine.cancel(id)
            throw CancellationException("Serviço interrompido")
        } catch (error: Throwable) {
            val message = userFacingError(error)
            repository.markFailed(id, message)
            showTerminalNotification(queuedItem, message, success = false, allowRetry = true)
            QuickDownloadWidget.refresh(this, force = true)
            DownloadListWidget.refresh(this)
        } finally {
            activeIds -= id
            if (activeIds.isEmpty()) releaseKeepAwakeLock()
        }
    }

    private fun requestCancellation(id: String) {
        if (id in activeIds) engine.cancel(id)
        serviceScope.launch {
            repository.cancel(id)
            kickWorkers()
        }
    }

    /** Stops the worker but keeps the partial file so a resume continues from it. */
    private fun requestPause(id: String) {
        if (id in activeIds) engine.pause(id)
        serviceScope.launch {
            repository.pause(id)
            notificationManager.cancel(id.hashCode())
            kickWorkers()
        }
    }

    private fun requestResume(id: String) {
        serviceScope.launch {
            repository.resume(id)
            kickWorkers()
        }
    }

    private fun kickWorkers() {
        kicks.tryEmit(Unit)
        serviceScope.launch { DownloadListWidget.refresh(this@DownloadService) }
    }

    private fun ensureForeground(
        text: String,
        progress: Int = 0,
        indeterminate: Boolean,
        item: DownloadItem? = null,
    ) {
        val builder = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle(item?.title ?: "MediaDownloader")
            .setContentText(text.take(NOTIFICATION_TEXT_LIMIT))
            .setOnlyAlertOnce(true)
            .setOngoing(true)
            .setCategory(NotificationCompat.CATEGORY_PROGRESS)
            .setProgress(100, progress.coerceIn(0, 100), indeterminate)
            .setContentIntent(appLaunchPendingIntent())
        item?.let {
            builder.addAction(
                android.R.drawable.ic_media_pause,
                "Pausar",
                serviceActionPendingIntent(ACTION_PAUSE, it.id),
            )
            builder.addAction(
                android.R.drawable.ic_menu_close_clear_cancel,
                "Cancelar",
                serviceActionPendingIntent(ACTION_CANCEL, it.id),
            )
        }
        synchronized(foregroundLock) {
            startForeground(FOREGROUND_NOTIFICATION_ID, builder.build())
        }
    }

    /**
     * Posts one independent notification per running item so the user can pause or
     * cancel it without opening the app, keeping the shared foreground summary untouched.
     */
    private fun showItemProgressNotification(
        item: DownloadItem,
        percent: Int,
        text: String,
        indeterminate: Boolean,
    ) {
        val builder = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle(item.title)
            .setContentText(text)
            .setOnlyAlertOnce(true)
            .setOngoing(true)
            .setCategory(NotificationCompat.CATEGORY_PROGRESS)
            .setProgress(100, percent.coerceIn(0, 100), indeterminate)
            .setContentIntent(appLaunchPendingIntent())
            .addAction(
                android.R.drawable.ic_media_pause,
                "Pausar",
                serviceActionPendingIntent(ACTION_PAUSE, item.id),
            )
            .addAction(
                android.R.drawable.ic_menu_close_clear_cancel,
                "Cancelar",
                serviceActionPendingIntent(ACTION_CANCEL, item.id),
            )
        notificationManager.notify(item.id.hashCode(), builder.build())
    }

    private fun showPausedNotification(reason: String) {
        val builder = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
            .setContentTitle("Downloads pausados")
            .setContentText(reason)
            .setOnlyAlertOnce(true)
            .setOngoing(true)
            .setCategory(NotificationCompat.CATEGORY_PROGRESS)
            .setContentIntent(appLaunchPendingIntent())
        synchronized(foregroundLock) {
            startForeground(FOREGROUND_NOTIFICATION_ID, builder.build())
        }
    }

    private fun showTerminalNotification(
        item: DownloadItem,
        text: String,
        success: Boolean,
        allowRetry: Boolean = false,
    ) {
        val builder = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(
                if (success) android.R.drawable.stat_sys_download_done
                else android.R.drawable.stat_notify_error,
            )
            .setContentTitle(item.title)
            .setContentText(text.take(NOTIFICATION_TEXT_LIMIT))
            .setStyle(NotificationCompat.BigTextStyle().bigText(text.take(ERROR_TEXT_LIMIT)))
            .setAutoCancel(true)
            .setContentIntent(appLaunchPendingIntent())
            .setSilent(!settings.completionSound && !settings.completionVibrate)
            .setDefaults(completionDefaults())
        if (success) {
            item.outputUri?.let { uri ->
                builder.addAction(
                    android.R.drawable.ic_menu_view,
                    "Abrir",
                    openFilePendingIntent(uri),
                )
            }
        }
        if (allowRetry) {
            builder.addAction(
                android.R.drawable.ic_popup_sync,
                "Tentar novamente",
                serviceActionPendingIntent(ACTION_RETRY, item.id),
            )
        }
        notificationManager.notify(item.id.hashCode(), builder.build())
    }

    private fun completionDefaults(): Int {
        val sound = settings.completionSound
        val vibrate = settings.completionVibrate
        return when {
            sound && vibrate -> NotificationCompat.DEFAULT_ALL
            sound -> NotificationCompat.DEFAULT_SOUND
            vibrate -> NotificationCompat.DEFAULT_VIBRATE
            else -> 0
        }
    }

    private fun appLaunchPendingIntent(): PendingIntent? {
        val launchIntent = packageManager.getLaunchIntentForPackage(packageName) ?: return null
        return PendingIntent.getActivity(
            this,
            0,
            launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun openFilePendingIntent(uri: String): PendingIntent {
        val contentUri = uri.toUri()
        val view = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(contentUri, itemMime(contentUri))
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        val chooser = Intent.createChooser(view, "Abrir arquivo").apply {
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        return PendingIntent.getActivity(
            this,
            uri.hashCode(),
            chooser,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun itemMime(uri: Uri): String? {
        return runCatching { contentResolver.getType(uri) }.getOrNull()
    }

    private fun serviceActionPendingIntent(action: String, id: String): PendingIntent {
        val intent = Intent(this, DownloadService::class.java).apply {
            this.action = action
            putExtra(EXTRA_DOWNLOAD_ID, id)
        }
        return PendingIntent.getService(
            this,
            (action + id).hashCode(),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.download_channel_name),
            NotificationManager.IMPORTANCE_DEFAULT,
        ).apply {
            description = getString(R.string.download_channel_description)
            setShowBadge(false)
        }
        notificationManager.createNotificationChannel(channel)
    }

    private fun userFacingError(error: Throwable): String {
        val raw = generateSequence(error) { it.cause }
            .mapNotNull { it.message?.trim()?.takeIf(String::isNotBlank) }
            .firstOrNull()
            ?: "Falha desconhecida durante o download"
        val message = raw.lineSequence()
            .lastOrNull { it.isNotBlank() }
            ?.removePrefix("ERROR:")
            ?.trim()
            ?.take(ERROR_TEXT_LIMIT)
            ?: "Falha durante o download"
        return friendlyHttpError(message) ?: message
    }

    private fun friendlyHttpError(message: String): String? {
        val lowered = message.lowercase()
        return when {
            "403" in lowered || "forbidden" in lowered ||
                ("access denied" in lowered && "cookie" in lowered) ->
                "Acesso negado (HTTP 403). O site bloqueou o download — ajuste os " +
                    "cookies/identidade em Ajustes, verifique o login ou tente depois."

            "429" in lowered || "too many requests" in lowered ->
                "Muitas requisições (HTTP 429). O limite do site foi atingido — aguarde e tente de novo."

            "401" in lowered || "unauthorized" in lowered ->
                "Sem autorização (HTTP 401). Verifique os cookies/identidade em Ajustes e tente de novo."

            else -> null
        }
    }

    companion object {
        const val ACTION_PROCESS_QUEUE = "com.mediadownloader.mobile.action.PROCESS_QUEUE"
        const val ACTION_CANCEL = "com.mediadownloader.mobile.action.CANCEL_DOWNLOAD"
        const val ACTION_PAUSE = "com.mediadownloader.mobile.action.PAUSE_DOWNLOAD"
        const val ACTION_RESUME = "com.mediadownloader.mobile.action.RESUME_DOWNLOAD"
        const val ACTION_RETRY = "com.mediadownloader.mobile.action.RETRY_DOWNLOAD"
        const val EXTRA_DOWNLOAD_ID = "download_id"

        private const val CHANNEL_ID = "media_downloads"
        private const val FOREGROUND_NOTIFICATION_ID = 10_001
        private const val NOTIFICATION_TEXT_LIMIT = 150
        private const val ERROR_TEXT_LIMIT = 1_000
        private const val KICK_WAIT_MS = 2_000L
        private const val STOP_POLL_MS = 1_500L
        private const val MAX_PARALLEL = 3
private const val KEEP_AWAKE_TIMEOUT_MS = 6L * 60L * 60L * 1_000L

        fun processQueue(context: Context) {
            ContextCompat.startForegroundService(
                context,
                Intent(context, DownloadService::class.java).apply {
                    action = ACTION_PROCESS_QUEUE
                },
            )
        }

        fun cancel(context: Context, downloadId: String) {
            ContextCompat.startForegroundService(
                context,
                Intent(context, DownloadService::class.java).apply {
                    action = ACTION_CANCEL
                    putExtra(EXTRA_DOWNLOAD_ID, downloadId)
                },
            )
        }

        fun retry(context: Context, downloadId: String) {
            ContextCompat.startForegroundService(
                context,
                Intent(context, DownloadService::class.java).apply {
                    action = ACTION_RETRY
                    putExtra(EXTRA_DOWNLOAD_ID, downloadId)
                },
            )
        }

        fun pause(context: Context, downloadId: String) {
            ContextCompat.startForegroundService(
                context,
                Intent(context, DownloadService::class.java).apply {
                    action = ACTION_PAUSE
                    putExtra(EXTRA_DOWNLOAD_ID, downloadId)
                },
            )
        }

        fun resume(context: Context, downloadId: String) {
            ContextCompat.startForegroundService(
                context,
                Intent(context, DownloadService::class.java).apply {
                    action = ACTION_RESUME
                    putExtra(EXTRA_DOWNLOAD_ID, downloadId)
                },
            )
        }
    }
}