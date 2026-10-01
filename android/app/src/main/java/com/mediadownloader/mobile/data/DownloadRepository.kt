package com.mediadownloader.mobile.data

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/**
 * Process-wide source of truth for the persistent queue and history.
 *
 * Every mutation is committed to SQLite before its corresponding StateFlow is refreshed.
 */
class DownloadRepository private constructor(context: Context) {
    private val database = DownloadDatabase(context)
    private val writeMutex = Mutex()
    private val _downloads = MutableStateFlow(database.loadDownloads())
    private val _history = MutableStateFlow(database.loadHistory())

    val downloads: StateFlow<List<DownloadItem>> = _downloads.asStateFlow()
    val history: StateFlow<List<HistoryItem>> = _history.asStateFlow()

    suspend fun enqueue(
        sourceUrl: String,
        title: String = sourceUrl,
        sourceName: String? = null,
        thumbnailUrl: String? = null,
        options: DownloadOptions = DownloadOptions(),
    ): DownloadItem = write {
        DownloadItem
            .create(sourceUrl, title, sourceName, thumbnailUrl, options)
            .copy(sortOrder = database.maxSortOrder() + 1)
            .also {
                database.upsertDownload(it)
            }
    }

    suspend fun enqueue(item: DownloadItem): DownloadItem = write {
        val now = System.currentTimeMillis()
        item.copy(
            state = DownloadState.QUEUED,
            progress = 0,
            etaSeconds = null,
            errorMessage = null,
            keepPartialFiles = false,
            sortOrder = database.maxSortOrder() + 1,
            updatedAtEpochMs = now,
            completedAtEpochMs = null,
        ).also(database::upsertDownload)
    }

    suspend fun getDownload(id: String): DownloadItem? = withContext(Dispatchers.IO) {
        database.getDownload(id)
    }

    suspend fun nextQueued(): DownloadItem? = withContext(Dispatchers.IO) {
        database.getNextQueuedDownload()
    }

    /**
     * Atomically claims the next queued item (marks it INITIALIZING under the
     * write lock). Safe to call from N concurrent workers: each item is handed
     * to exactly one worker.
     */
    suspend fun claimNextQueued(): DownloadItem? = write {
        database.getNextQueuedDownload()?.let { next ->
            database.upsertDownload(
                next.copy(
                    state = DownloadState.INITIALIZING,
                    progress = 0,
                    etaSeconds = null,
                    statusLine = "Preparando o mecanismo de download",
                    errorMessage = null,
                    updatedAtEpochMs = System.currentTimeMillis(),
                    completedAtEpochMs = null,
                ),
            )
            next
        }
    }

    suspend fun markInitializing(id: String): DownloadItem? = mutate(id) {
        if (it.state != DownloadState.QUEUED) return@mutate it
        it.copy(
            state = DownloadState.INITIALIZING,
            progress = 0,
            etaSeconds = null,
            statusLine = "Preparando o mecanismo de download",
            errorMessage = null,
            updatedAtEpochMs = System.currentTimeMillis(),
        )
    }

    suspend fun markProgress(
        id: String,
        progress: Int,
        etaSeconds: Long?,
        statusLine: String?,
        processing: Boolean = false,
    ): DownloadItem? = mutate(id) {
        if (it.state in TERMINAL_STATES) {
            it
        } else {
            it.copy(
                state = if (processing) DownloadState.PROCESSING else DownloadState.DOWNLOADING,
                progress = progress.coerceIn(0, 99),
                etaSeconds = etaSeconds?.takeIf { value -> value >= 0 },
                statusLine = statusLine?.takeLast(MAX_STATUS_LENGTH),
                updatedAtEpochMs = System.currentTimeMillis(),
            )
        }
    }

    suspend fun markCompleted(id: String, file: PublishedFile): DownloadItem? = mutate(id) {
        if (it.state == DownloadState.CANCELLED) return@mutate it
        val now = System.currentTimeMillis()
        it.copy(
            state = DownloadState.COMPLETED,
            progress = 100,
            etaSeconds = 0,
            statusLine = "Concluído",
            errorMessage = null,
            outputUri = file.uri,
            outputFileName = file.displayName,
            outputMimeType = file.mimeType,
            outputSizeBytes = file.sizeBytes,
            keepPartialFiles = false,
            updatedAtEpochMs = now,
            completedAtEpochMs = now,
        )
    }

    suspend fun markFailed(id: String, message: String): DownloadItem? = mutate(id) {
        if (it.state == DownloadState.CANCELLED) return@mutate it
        it.copy(
            state = DownloadState.FAILED,
            etaSeconds = null,
            statusLine = "Falha no download",
            errorMessage = message.take(MAX_ERROR_LENGTH),
            updatedAtEpochMs = System.currentTimeMillis(),
        )
    }

    suspend fun cancel(id: String): DownloadItem? = mutate(id) {
        if (it.state == DownloadState.COMPLETED) {
            it
        } else {
            it.copy(
                state = DownloadState.CANCELLED,
                etaSeconds = null,
                statusLine = "Cancelado",
                errorMessage = null,
                keepPartialFiles = false,
                updatedAtEpochMs = System.currentTimeMillis(),
            )
        }
    }

    /**
     * Freezes the item where it is. The already downloaded part is kept so
     * [resume] continues from it instead of starting over.
     */
    suspend fun pause(id: String): DownloadItem? = mutate(id) {
        if (it.state in PAUSABLE_STATES) {
            it.copy(
                state = DownloadState.PAUSED,
                etaSeconds = null,
                statusLine = "Pausado",
                errorMessage = null,
                keepPartialFiles = true,
                updatedAtEpochMs = System.currentTimeMillis(),
            )
        } else {
            it
        }
    }

    /** Puts a paused item back in the queue, keeping its manual position. */
    suspend fun resume(id: String): DownloadItem? = mutate(id) {
        if (it.state == DownloadState.PAUSED) {
            it.copy(
                state = DownloadState.QUEUED,
                progress = 0,
                etaSeconds = null,
                statusLine = "Na fila novamente",
                errorMessage = null,
                updatedAtEpochMs = System.currentTimeMillis(),
            )
        } else {
            it
        }
    }

    /**
     * Swaps a queued item with its neighbour so the user controls the run order.
     * Returns the id when the move happened, `null` when there is no neighbour.
     */
    suspend fun moveQueued(id: String, up: Boolean): String? = write {
        val current = database.getDownload(id)
            ?.takeIf { it.state == DownloadState.QUEUED }
            ?: return@write null
        val queued = database.loadDownloads()
            .filter { it.state == DownloadState.QUEUED }
            .sortedWith(compareBy({ it.sortOrder }, { it.createdAtEpochMs }, { it.id }))
        val index = queued.indexOfFirst { it.id == id }
        val neighbourIndex = if (up) index - 1 else index + 1
        val neighbour = queued.getOrNull(neighbourIndex) ?: return@write null
        database.updateSortOrder(id, neighbour.sortOrder)
        database.updateSortOrder(neighbour.id, current.sortOrder)
        id
    }

    suspend fun retry(id: String): DownloadItem? = mutate(id) {
        if (it.state != DownloadState.FAILED && it.state != DownloadState.CANCELLED) {
            it
        } else {
            it.copy(
                state = DownloadState.QUEUED,
                progress = 0,
                etaSeconds = null,
                statusLine = "Na fila novamente",
                errorMessage = null,
                outputUri = null,
                outputFileName = null,
                outputMimeType = null,
                outputSizeBytes = null,
                keepPartialFiles = false,
                retryCount = it.retryCount + 1,
                updatedAtEpochMs = System.currentTimeMillis(),
                completedAtEpochMs = null,
            )
        }
    }

    /** Makes work interrupted by an OS/process stop eligible to run again. */
    suspend fun recoverInterrupted(): Int = write {
        val activeStates = setOf(
            DownloadState.INITIALIZING,
            DownloadState.DOWNLOADING,
            DownloadState.PROCESSING,
        )
        val interrupted = database.loadDownloads().filter { it.state in activeStates }
        interrupted.forEach { item ->
            database.upsertDownload(
                item.copy(
                    state = DownloadState.QUEUED,
                    progress = 0,
                    etaSeconds = null,
                    statusLine = "Retomando após reinício",
                    errorMessage = null,
                    updatedAtEpochMs = System.currentTimeMillis(),
                ),
            )
        }
        interrupted.size
    }

    suspend fun addHistory(item: HistoryItem) = write {
        database.upsertHistory(item)
    }

    suspend fun deleteDownload(id: String) = write {
        database.deleteDownload(id)
    }

    suspend fun clearFinishedDownloads() = write {
        database.deleteFinishedDownloads()
    }

    suspend fun deleteHistory(id: String) = write {
        database.deleteHistory(id)
    }

    /** Bulk removal used by the history multi-selection; keeps the write mutex for all rows. */
    suspend fun deleteHistory(ids: Collection<String>) = write {
        if (ids.isEmpty()) return@write
        database.deleteHistory(ids.toSet())
    }

    suspend fun clearHistory() = write {
        database.clearHistory()
    }

    /** Persists a re-name applied to a history row (the stored URI keeps its id). */
    suspend fun renameHistoryFileName(id: String, newFileName: String): HistoryItem? = write {
        val current = database.loadHistory().firstOrNull { it.id == id } ?: return@write null
        val updated = current.copy(fileName = newFileName)
        database.upsertHistory(updated)
        updated
    }

    suspend fun stats(): DownloadStats = withContext(Dispatchers.IO) {
        val items = database.loadHistory()
        DownloadStats(
            completedCount = items.size,
            totalDownloadedBytes = items.sumOf { it.sizeBytes.coerceAtLeast(0) },
        )
    }

    private suspend fun mutate(
        id: String,
        transform: (DownloadItem) -> DownloadItem,
    ): DownloadItem? = write {
        database.getDownload(id)?.let(transform)?.also(database::upsertDownload)
    }

    private suspend fun <T> write(block: () -> T): T = writeMutex.withLock {
        withContext(Dispatchers.IO) {
            block().also {
                _downloads.value = database.loadDownloads()
                _history.value = database.loadHistory()
            }
        }
    }

    companion object {
        private const val MAX_STATUS_LENGTH = 500
        private const val MAX_ERROR_LENGTH = 2_000
        private val TERMINAL_STATES = setOf(
            DownloadState.COMPLETED,
            DownloadState.FAILED,
            DownloadState.CANCELLED,
        )
        private val PAUSABLE_STATES = setOf(
            DownloadState.QUEUED,
            DownloadState.INITIALIZING,
            DownloadState.DOWNLOADING,
            DownloadState.PROCESSING,
        )

        @Volatile
        private var instance: DownloadRepository? = null

        fun getInstance(context: Context): DownloadRepository =
            instance ?: synchronized(this) {
                instance ?: DownloadRepository(context.applicationContext).also { instance = it }
            }
    }
}
