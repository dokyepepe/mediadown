package com.mediadownloader.mobile.download

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.mediadownloader.mobile.data.DownloadItem
import com.mediadownloader.mobile.data.DownloadRepository
import com.mediadownloader.mobile.data.HistoryItem
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Persistent, serial download worker. Add this service to the manifest with foregroundServiceType
 * "dataSync" and declare FOREGROUND_SERVICE plus FOREGROUND_SERVICE_DATA_SYNC where applicable.
 */
class DownloadService : Service() {
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val workSignals = Channel<Unit>(Channel.CONFLATED)
    private val workerStarted = AtomicBoolean(false)
    private lateinit var repository: DownloadRepository
    private lateinit var engine: AndroidDownloadEngine
    private lateinit var notificationManager: NotificationManager

    @Volatile
    private var currentDownloadId: String? = null

    private var lastProgressPersisted = -1
    private var lastProgressUpdateMs = 0L

    override fun onCreate() {
        super.onCreate()
        repository = DownloadRepository.getInstance(applicationContext)
        engine = AndroidDownloadEngine(applicationContext)
        notificationManager = getSystemService(NotificationManager::class.java)
        createNotificationChannel()
        ensureForeground("Preparando a fila", indeterminate = true)
        startWorker()
        serviceScope.launch {
            repository.recoverInterrupted()
            workSignals.trySend(Unit)
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        ensureForeground("Verificando a fila", indeterminate = true)
        when (intent?.action) {
            ACTION_CANCEL -> intent.getStringExtra(EXTRA_DOWNLOAD_ID)?.let(::requestCancellation)
            ACTION_RETRY -> intent.getStringExtra(EXTRA_DOWNLOAD_ID)?.let { id ->
                serviceScope.launch {
                    repository.retry(id)
                    workSignals.trySend(Unit)
                }
            }
            ACTION_PROCESS_QUEUE, null -> workSignals.trySend(Unit)
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        currentDownloadId?.let(engine::cancel)
        workSignals.close()
        serviceScope.cancel()
        super.onDestroy()
    }

    private fun startWorker() {
        if (!workerStarted.compareAndSet(false, true)) return
        serviceScope.launch {
            for (ignored in workSignals) {
                drainQueue()
            }
        }
    }

    private suspend fun drainQueue() {
        while (true) {
            val next = repository.nextQueued() ?: break
            runDownload(next)
        }
        currentDownloadId = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private suspend fun runDownload(queuedItem: DownloadItem) {
        currentDownloadId = queuedItem.id
        lastProgressPersisted = -1
        lastProgressUpdateMs = 0L
        val starting = repository.markInitializing(queuedItem.id)
        if (starting?.state != com.mediadownloader.mobile.data.DownloadState.INITIALIZING) return
        ensureForeground("Preparando ${queuedItem.title}", indeterminate = true, item = queuedItem)
        try {
            val result = engine.download(queuedItem) { progress ->
                updateProgressFromCallback(queuedItem, progress)
            }
            val current = repository.getDownload(queuedItem.id)
            if (current?.state == com.mediadownloader.mobile.data.DownloadState.CANCELLED) {
                return
            }
            val completed = repository.markCompleted(queuedItem.id, result.primaryFile)
                ?: queuedItem
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
        } catch (_: DownloadCancelledException) {
            repository.cancel(queuedItem.id)
            showTerminalNotification(queuedItem, "Download cancelado", success = false)
        } catch (_: CancellationException) {
            engine.cancel(queuedItem.id)
            throw CancellationException("Serviço interrompido")
        } catch (error: Throwable) {
            val message = userFacingError(error)
            repository.markFailed(queuedItem.id, message)
            showTerminalNotification(queuedItem, message, success = false, allowRetry = true)
        } finally {
            currentDownloadId = null
        }
    }

    private fun updateProgressFromCallback(item: DownloadItem, progress: EngineProgress) {
        val now = System.currentTimeMillis()
        val shouldPersist = progress.percent != lastProgressPersisted &&
            (progress.percent >= lastProgressPersisted + 1 || now - lastProgressUpdateMs >= 750)
        if (!shouldPersist) return
        lastProgressPersisted = progress.percent
        lastProgressUpdateMs = now
        val label = if (progress.processing) {
            "Processando ${item.title}"
        } else {
            "Baixando ${item.title}"
        }
        ensureForeground(
            text = label,
            progress = progress.percent,
            indeterminate = progress.percent <= 0,
            item = item,
        )
        serviceScope.launch {
            repository.markProgress(
                id = item.id,
                progress = progress.percent,
                etaSeconds = progress.etaSeconds,
                statusLine = progress.outputLine,
                processing = progress.processing,
            )
        }
    }

    private fun requestCancellation(id: String) {
        if (id == currentDownloadId) engine.cancel(id)
        serviceScope.launch {
            repository.cancel(id)
            workSignals.trySend(Unit)
        }
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
                android.R.drawable.ic_menu_close_clear_cancel,
                "Cancelar",
                serviceActionPendingIntent(ACTION_CANCEL, it.id),
            )
        }
        startForeground(FOREGROUND_NOTIFICATION_ID, builder.build())
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
        if (allowRetry) {
            builder.addAction(
                android.R.drawable.ic_popup_sync,
                "Tentar novamente",
                serviceActionPendingIntent(ACTION_RETRY, item.id),
            )
        }
        notificationManager.notify(item.id.hashCode(), builder.build())
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
            "Downloads",
            NotificationManager.IMPORTANCE_LOW,
        ).apply {
            description = "Progresso dos downloads de mídia"
            setShowBadge(false)
        }
        notificationManager.createNotificationChannel(channel)
    }

    private fun userFacingError(error: Throwable): String {
        val raw = generateSequence(error) { it.cause }
            .mapNotNull { it.message?.trim()?.takeIf(String::isNotBlank) }
            .firstOrNull()
            ?: "Falha desconhecida durante o download"
        return raw.lineSequence()
            .lastOrNull { it.isNotBlank() }
            ?.removePrefix("ERROR:")
            ?.trim()
            ?.take(ERROR_TEXT_LIMIT)
            ?: "Falha durante o download"
    }

    companion object {
        const val ACTION_PROCESS_QUEUE = "com.mediadownloader.mobile.action.PROCESS_QUEUE"
        const val ACTION_CANCEL = "com.mediadownloader.mobile.action.CANCEL_DOWNLOAD"
        const val ACTION_RETRY = "com.mediadownloader.mobile.action.RETRY_DOWNLOAD"
        const val EXTRA_DOWNLOAD_ID = "download_id"

        private const val CHANNEL_ID = "media_downloads"
        private const val FOREGROUND_NOTIFICATION_ID = 10_001
        private const val NOTIFICATION_TEXT_LIMIT = 150
        private const val ERROR_TEXT_LIMIT = 1_000

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
    }
}
