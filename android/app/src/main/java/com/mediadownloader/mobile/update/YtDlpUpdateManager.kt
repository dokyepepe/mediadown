package com.mediadownloader.mobile.update

import android.content.Context
import com.yausername.youtubedl_android.YoutubeDL
import com.yausername.youtubedl_android.YoutubeDLRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.net.URL
import java.util.Properties
import java.util.UUID
import javax.net.ssl.HttpsURLConnection

data class YtDlpRuntimeStatus(
    val currentVersion: String?,
    val previousVersion: String?,
    val rejectedVersion: String?,
    val canRollback: Boolean,
)

enum class YtDlpCheckOutcome {
    AVAILABLE,
    UP_TO_DATE,
    REJECTED,
}

data class YtDlpCheckResult(
    val outcome: YtDlpCheckOutcome,
    val latestVersion: String,
    val status: YtDlpRuntimeStatus,
)

enum class YtDlpInstallOutcome {
    UPDATED,
    UP_TO_DATE,
    REJECTED,
    FAILED,
    RESTORED_AFTER_FAILURE,
}

data class YtDlpInstallResult(
    val outcome: YtDlpInstallOutcome,
    val status: YtDlpRuntimeStatus,
    val failedVersion: String? = null,
)

data class YtDlpRecoveryResult(
    val status: YtDlpRuntimeStatus,
    val recoveredInterruptedTransaction: Boolean,
    val restoredPreviousVersion: Boolean,
)

/**
 * Checks, updates and rolls back the yt-dlp runtime without using private library APIs.
 *
 * The library's own updater is intentionally kept as the installer. This class surrounds that
 * public API with a persistent snapshot, a crash journal and an offline smoke test. The actual
 * `--version` output is the source of truth because the library's version getters are metadata.
 */
class YtDlpUpdateManager private constructor(context: Context) {
    private val appContext = context.applicationContext
    private val preferences = appContext.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)
    private val runtimeRoot = File(appContext.noBackupFilesDir, YoutubeDL.baseName)
    private val activeDirectory = File(runtimeRoot, YoutubeDL.ytdlpDirName)
    private val activeBinary = File(activeDirectory, YoutubeDL.ytdlpBin)
    private val managerDirectory = File(runtimeRoot, MANAGER_DIRECTORY_NAME)
    private val previousBinary = File(managerDirectory, PREVIOUS_BINARY_NAME)
    private val pendingBackup = File(managerDirectory, PENDING_BACKUP_NAME)
    private val journalFile = File(managerDirectory, JOURNAL_FILE_NAME)

    @Volatile
    private var cachedRelease: StableRelease? = null

    @Volatile
    private var runtimePrepared = false

    fun snapshot(): YtDlpRuntimeStatus = statusFromMetadata()

    fun shouldCheckAutomatically(nowEpochMs: Long = System.currentTimeMillis()): Boolean =
        YtDlpUpdatePolicy.isAutomaticCheckDue(
            lastCheckEpochMs = preferences.getLong(KEY_LAST_CHECK_EPOCH_MS, 0L),
            nowEpochMs = nowEpochMs,
        )

    fun consumeRecoveryNotice(): String? {
        val notice = preferences.getString(KEY_RECOVERY_NOTICE, null)
        if (notice != null) preferences.edit().remove(KEY_RECOVERY_NOTICE).commit()
        return notice
    }

    suspend fun initializeAndRecover(): YtDlpRecoveryResult = withContext(Dispatchers.IO) {
        YtDlpRuntimeGate.withWriteLock {
            ensureInitializedLocked()
            recoverInterruptedTransactionLocked().also { runtimePrepared = true }
        }
    }

    suspend fun refreshStatus(): YtDlpRuntimeStatus = withContext(Dispatchers.IO) {
        prepareRuntimeBlocking()
        YtDlpRuntimeGate.withReadLock {
            val current = smokeTestLocked()
            persistCurrentVersion(current)
            statusFromMetadata(current)
        }
    }

    suspend fun checkForUpdate(): YtDlpCheckResult = withContext(Dispatchers.IO) {
        preferences.edit()
            .putLong(KEY_LAST_CHECK_EPOCH_MS, System.currentTimeMillis())
            .commit()
        val release = fetchStableRelease()
        cachedRelease = release
        val status = refreshStatusBlocking()
        val outcome = when (
            YtDlpUpdatePolicy.availability(
                currentVersion = status.currentVersion,
                latestVersion = release.version,
                rejectedVersion = status.rejectedVersion,
            )
        ) {
            YtDlpAvailability.AVAILABLE -> YtDlpCheckOutcome.AVAILABLE
            YtDlpAvailability.UP_TO_DATE -> YtDlpCheckOutcome.UP_TO_DATE
            YtDlpAvailability.REJECTED -> YtDlpCheckOutcome.REJECTED
            YtDlpAvailability.INVALID -> throw IOException("A origem retornou uma versão inválida do yt-dlp")
        }
        YtDlpCheckResult(outcome, release.version, status)
    }

    suspend fun installAvailableUpdate(): YtDlpInstallResult = withContext(Dispatchers.IO) {
        val release = cachedRelease ?: fetchStableRelease().also { cachedRelease = it }
        YtDlpRuntimeGate.withWriteLock {
            ensureInitializedLocked()
            recoverInterruptedTransactionLocked()
            runtimePrepared = true
            installLocked(release)
        }
    }

    suspend fun rollbackToPrevious(): YtDlpInstallResult = withContext(Dispatchers.IO) {
        YtDlpRuntimeGate.withWriteLock {
            ensureInitializedLocked()
            recoverInterruptedTransactionLocked()
            runtimePrepared = true
            rollbackLocked()
        }
    }

    private fun refreshStatusBlocking(): YtDlpRuntimeStatus {
        prepareRuntimeBlocking()
        return YtDlpRuntimeGate.withReadLock {
            val current = smokeTestLocked()
            persistCurrentVersion(current)
            statusFromMetadata(current)
        }
    }

    private fun prepareRuntimeBlocking() {
        if (runtimePrepared) return
        YtDlpRuntimeGate.withWriteLock {
            if (runtimePrepared) return@withWriteLock
            ensureInitializedLocked()
            recoverInterruptedTransactionLocked()
            runtimePrepared = true
        }
    }

    private fun installLocked(release: StableRelease): YtDlpInstallResult {
        val currentVersion = smokeTestLocked()
        val status = statusFromMetadata(currentVersion)
        return when (
            YtDlpUpdatePolicy.availability(
                currentVersion = currentVersion,
                latestVersion = release.version,
                rejectedVersion = status.rejectedVersion,
            )
        ) {
            YtDlpAvailability.UP_TO_DATE -> YtDlpInstallResult(
                outcome = YtDlpInstallOutcome.UP_TO_DATE,
                status = status,
            )

            YtDlpAvailability.REJECTED -> YtDlpInstallResult(
                outcome = YtDlpInstallOutcome.REJECTED,
                status = status,
                failedVersion = release.version,
            )

            YtDlpAvailability.INVALID -> throw IOException("A atualização disponível não tem uma versão válida")
            YtDlpAvailability.AVAILABLE -> performUpdateLocked(currentVersion, release)
        }
    }

    private fun performUpdateLocked(
        currentVersion: String,
        release: StableRelease,
    ): YtDlpInstallResult {
        requireActiveBinary()
        prepareManagerDirectory()
        YtDlpArtifactIntegrity.copyVerified(activeBinary, pendingBackup)
        val prepared = YtDlpTransactionJournal(
            kind = YtDlpTransactionKind.UPDATE,
            phase = YtDlpTransactionPhase.PREPARED,
            originalVersion = currentVersion,
            targetVersion = release.version,
        )
        writeJournal(prepared)
        var transaction = prepared

        try {
            val updateStatus = YoutubeDL.getInstance().updateYoutubeDL(
                appContext,
                YoutubeDL.UpdateChannel.STABLE,
            )
            if (updateStatus != YoutubeDL.UpdateStatus.DONE) {
                throw IOException("O instalador não aplicou a versão ${release.version}")
            }
            writeJournal(prepared.copy(phase = YtDlpTransactionPhase.SWAPPED))
            val installedVersion = smokeTestLocked()
            if (
                YtDlpUpdatePolicy.compareVersions(installedVersion, release.version)
                    ?.let { it >= 0 } != true
            ) {
                throw IOException(
                    "A versão instalada ($installedVersion) é anterior à esperada (${release.version})",
                )
            }
            transaction = prepared.copy(targetVersion = installedVersion)
            writeJournal(transaction.copy(phase = YtDlpTransactionPhase.SWAPPED))
            finalizeTargetLocked(transaction, installedVersion)
            return YtDlpInstallResult(
                outcome = YtDlpInstallOutcome.UPDATED,
                status = statusFromMetadata(installedVersion),
            )
        } catch (error: Throwable) {
            if (error is InterruptedException) Thread.currentThread().interrupt()
            val (restored, didRestore) = settleFailedTransactionLocked(transaction)
            return YtDlpInstallResult(
                outcome = if (didRestore) {
                    YtDlpInstallOutcome.RESTORED_AFTER_FAILURE
                } else {
                    YtDlpInstallOutcome.FAILED
                },
                status = statusFromMetadata(restored),
                failedVersion = transaction.targetVersion,
            )
        }
    }

    private fun rollbackLocked(): YtDlpInstallResult {
        val previousVersion = preferences.getString(KEY_PREVIOUS_VERSION, null)
            ?.let(YtDlpUpdatePolicy::normalizeVersion)
        if (!previousBinary.isFile || previousVersion.isNullOrBlank()) {
            throw IOException("Não há uma versão anterior disponível para restaurar")
        }
        val currentVersion = smokeTestLocked()
        if (YtDlpUpdatePolicy.normalizeVersion(currentVersion) == previousVersion) {
            return YtDlpInstallResult(
                outcome = YtDlpInstallOutcome.UP_TO_DATE,
                status = statusFromMetadata(currentVersion),
            )
        }

        prepareManagerDirectory()
        YtDlpArtifactIntegrity.copyVerified(activeBinary, pendingBackup)
        val prepared = YtDlpTransactionJournal(
            kind = YtDlpTransactionKind.MANUAL_ROLLBACK,
            phase = YtDlpTransactionPhase.PREPARED,
            originalVersion = currentVersion,
            targetVersion = previousVersion,
        )
        writeJournal(prepared)

        try {
            val stagedPrevious = File(managerDirectory, STAGED_PREVIOUS_NAME)
            YtDlpArtifactIntegrity.copyVerified(previousBinary, stagedPrevious)
            YtDlpArtifactIntegrity.atomicReplace(stagedPrevious, activeBinary)
            writeJournal(prepared.copy(phase = YtDlpTransactionPhase.SWAPPED))
            val restoredVersion = smokeTestLocked(expectedVersion = previousVersion)
            finalizeTargetLocked(prepared, restoredVersion)
            return YtDlpInstallResult(
                outcome = YtDlpInstallOutcome.UPDATED,
                status = statusFromMetadata(restoredVersion),
            )
        } catch (error: Throwable) {
            if (error is InterruptedException) Thread.currentThread().interrupt()
            val (restored, didRestore) = settleFailedTransactionLocked(prepared)
            if (didRestore) {
                previousBinary.delete()
                preferences.edit().remove(KEY_PREVIOUS_VERSION).commit()
            }
            return YtDlpInstallResult(
                outcome = if (didRestore) {
                    YtDlpInstallOutcome.RESTORED_AFTER_FAILURE
                } else {
                    YtDlpInstallOutcome.FAILED
                },
                status = statusFromMetadata(restored),
                failedVersion = previousVersion,
            )
        }
    }

    private fun settleFailedTransactionLocked(
        journal: YtDlpTransactionJournal,
    ): Pair<String, Boolean> {
        val stillOriginal = runCatching { smokeTestLocked(expectedVersion = journal.originalVersion) }
            .getOrNull()
        if (stillOriginal != null) {
            clearTransactionFiles()
            persistCurrentVersion(stillOriginal)
            return stillOriginal to false
        }
        return restoreOriginalLocked(journal) to true
    }

    private fun recoverInterruptedTransactionLocked(): YtDlpRecoveryResult {
        val journal = readJournal()
            ?: return YtDlpRecoveryResult(
                status = statusFromMetadata(),
                recoveredInterruptedTransaction = false,
                restoredPreviousVersion = false,
            )
        val smoke = runCatching { smokeTestLocked() }
        val action = recoveryAction(
            journal = journal,
            observedVersion = smoke.getOrNull(),
            smokePassed = smoke.isSuccess,
        )
        return when (action) {
            YtDlpRecoveryAction.FINALIZE_TARGET -> {
                val target = smoke.getOrThrow()
                finalizeTargetLocked(journal, target)
                saveRecoveryNotice(
                    "Concluímos com segurança uma alteração interrompida do yt-dlp. Versão ativa: $target.",
                )
                YtDlpRecoveryResult(
                    status = statusFromMetadata(target),
                    recoveredInterruptedTransaction = true,
                    restoredPreviousVersion = false,
                )
            }

            YtDlpRecoveryAction.KEEP_ORIGINAL -> {
                val original = smoke.getOrThrow()
                clearTransactionFiles()
                persistCurrentVersion(original)
                saveRecoveryNotice(
                    "Uma alteração do yt-dlp foi interrompida antes da instalação. A versão $original continua ativa.",
                )
                YtDlpRecoveryResult(
                    status = statusFromMetadata(original),
                    recoveredInterruptedTransaction = true,
                    restoredPreviousVersion = false,
                )
            }

            YtDlpRecoveryAction.RESTORE_ORIGINAL -> {
                val restored = restoreOriginalLocked(journal)
                saveRecoveryNotice(
                    "Uma alteração interrompida foi desfeita. Restauramos a versão $restored do yt-dlp.",
                )
                YtDlpRecoveryResult(
                    status = statusFromMetadata(restored),
                    recoveredInterruptedTransaction = true,
                    restoredPreviousVersion = true,
                )
            }
        }
    }

    private fun restoreOriginalLocked(journal: YtDlpTransactionJournal): String {
        if (!pendingBackup.isFile) {
            val current = runCatching { smokeTestLocked(expectedVersion = journal.originalVersion) }
                .getOrElse {
                    throw IOException(
                        "A atualização foi interrompida e o backup da versão anterior não está disponível",
                        it,
                    )
                }
            clearTransactionFiles()
            persistCurrentVersion(current)
            return current
        }
        writeJournal(journal.copy(phase = YtDlpTransactionPhase.RESTORING))
        prepareActiveDirectory()
        YtDlpArtifactIntegrity.atomicReplace(pendingBackup, activeBinary)
        val restored = smokeTestLocked(expectedVersion = journal.originalVersion)
        preferences.edit()
            .putString(KEY_CURRENT_VERSION, restored)
            .putString(KEY_REJECTED_VERSION, journal.targetVersion)
            .commit()
        clearTransactionFiles()
        return restored
    }

    private fun finalizeTargetLocked(journal: YtDlpTransactionJournal, installedVersion: String) {
        if (pendingBackup.isFile) {
            YtDlpArtifactIntegrity.atomicReplace(pendingBackup, previousBinary)
        }
        val editor = preferences.edit()
            .putString(KEY_CURRENT_VERSION, installedVersion)
            .putString(KEY_PREVIOUS_VERSION, journal.originalVersion)
        if (journal.kind == YtDlpTransactionKind.MANUAL_ROLLBACK) {
            editor.putString(KEY_REJECTED_VERSION, journal.originalVersion)
        } else if (
            YtDlpUpdatePolicy.normalizeVersion(preferences.getString(KEY_REJECTED_VERSION, null)) ==
            YtDlpUpdatePolicy.normalizeVersion(installedVersion)
        ) {
            editor.remove(KEY_REJECTED_VERSION)
        }
        editor.commit()
        clearTransactionFiles()
    }

    private fun smokeTestLocked(expectedVersion: String? = null): String {
        val request = YoutubeDLRequest(emptyList()).apply { addOption("--version") }
        val response = YoutubeDL.getInstance().execute(
            request,
            "yt-dlp-smoke-${UUID.randomUUID()}",
            null,
        )
        val actual = YtDlpUpdatePolicy.normalizeVersion(response.out)
            ?: throw IOException("O yt-dlp não respondeu ao teste local")
        val expected = YtDlpUpdatePolicy.normalizeVersion(expectedVersion)
        if (expected != null && actual != expected) {
            throw IOException("A versão instalada ($actual) difere da esperada ($expected)")
        }
        return actual
    }

    private fun ensureInitializedLocked() {
        YoutubeDL.getInstance().init(appContext)
        requireActiveBinary()
        prepareManagerDirectory()
    }

    private fun requireActiveBinary() {
        if (!activeBinary.isFile || activeBinary.length() <= 0L) {
            throw IOException("O executável do yt-dlp não está disponível")
        }
    }

    private fun statusFromMetadata(currentOverride: String? = null): YtDlpRuntimeStatus {
        val current = YtDlpUpdatePolicy.normalizeVersion(currentOverride)
            ?: YtDlpUpdatePolicy.normalizeVersion(preferences.getString(KEY_CURRENT_VERSION, null))
            ?: YtDlpUpdatePolicy.normalizeVersion(YoutubeDL.getInstance().versionName(appContext))
            ?: YtDlpUpdatePolicy.normalizeVersion(YoutubeDL.getInstance().version(appContext))
        val previous = preferences.getString(KEY_PREVIOUS_VERSION, null)
            ?.let(YtDlpUpdatePolicy::normalizeVersion)
            ?.takeIf { previousBinary.isFile && previousBinary.length() > 0L }
        return YtDlpRuntimeStatus(
            currentVersion = current,
            previousVersion = previous,
            rejectedVersion = preferences.getString(KEY_REJECTED_VERSION, null)
                ?.let(YtDlpUpdatePolicy::normalizeVersion),
            canRollback = previous != null,
        )
    }

    private fun persistCurrentVersion(version: String) {
        preferences.edit().putString(KEY_CURRENT_VERSION, version).commit()
    }

    private fun saveRecoveryNotice(message: String) {
        preferences.edit().putString(KEY_RECOVERY_NOTICE, message).commit()
    }

    private fun fetchStableRelease(): StableRelease {
        val connection = (URL(YoutubeDL.UpdateChannel.STABLE.apiUrl).openConnection() as HttpsURLConnection)
            .apply {
                requestMethod = "GET"
                connectTimeout = NETWORK_CONNECT_TIMEOUT_MS
                readTimeout = NETWORK_READ_TIMEOUT_MS
                instanceFollowRedirects = true
                setRequestProperty("Accept", "application/vnd.github+json")
                setRequestProperty("User-Agent", "MediaDownloader-Android")
            }
        try {
            val responseCode = connection.responseCode
            if (responseCode !in 200..299) {
                throw IOException("A verificação de atualização respondeu com HTTP $responseCode")
            }
            val body = connection.inputStream.bufferedReader(Charsets.UTF_8).use { reader ->
                val text = reader.readText()
                if (text.length > MAX_RELEASE_RESPONSE_CHARS) {
                    throw IOException("A resposta de atualização é maior que o esperado")
                }
                text
            }
            val json = JSONObject(body)
            val version = YtDlpUpdatePolicy.normalizeVersion(json.optString("tag_name"))
                ?: throw IOException("A origem não informou a versão estável do yt-dlp")
            return StableRelease(version)
        } finally {
            connection.disconnect()
        }
    }

    private fun prepareManagerDirectory() {
        if (!managerDirectory.exists() && !managerDirectory.mkdirs()) {
            throw IOException("Não foi possível preparar o diretório de atualização")
        }
    }

    private fun prepareActiveDirectory() {
        if (!activeDirectory.exists() && !activeDirectory.mkdirs()) {
            throw IOException("Não foi possível preparar o diretório do yt-dlp")
        }
    }

    private fun writeJournal(journal: YtDlpTransactionJournal) {
        runtimePrepared = false
        prepareManagerDirectory()
        val properties = Properties().apply {
            setProperty(JOURNAL_KIND, journal.kind.name)
            setProperty(JOURNAL_PHASE, journal.phase.name)
            setProperty(JOURNAL_ORIGINAL, journal.originalVersion)
            setProperty(JOURNAL_TARGET, journal.targetVersion)
        }
        val temporary = File(managerDirectory, "$JOURNAL_FILE_NAME.tmp")
        FileOutputStream(temporary).use { output ->
            properties.store(output, null)
            output.fd.sync()
        }
        YtDlpArtifactIntegrity.atomicReplace(temporary, journalFile)
    }

    private fun readJournal(): YtDlpTransactionJournal? {
        if (!journalFile.isFile) return null
        return try {
            val properties = Properties().apply {
                FileInputStream(journalFile).use(::load)
            }
            YtDlpTransactionJournal(
                kind = YtDlpTransactionKind.valueOf(properties.getProperty(JOURNAL_KIND)),
                phase = YtDlpTransactionPhase.valueOf(properties.getProperty(JOURNAL_PHASE)),
                originalVersion = properties.getProperty(JOURNAL_ORIGINAL)
                    ?: throw IOException("Journal sem versão original"),
                targetVersion = properties.getProperty(JOURNAL_TARGET)
                    ?: throw IOException("Journal sem versão de destino"),
            )
        } catch (error: Throwable) {
            throw IOException("O journal da atualização está corrompido", error)
        }
    }

    private fun clearTransactionFiles() {
        journalFile.delete()
        pendingBackup.delete()
        File(managerDirectory, STAGED_PREVIOUS_NAME).delete()
        runtimePrepared = true
    }

    private data class StableRelease(val version: String)

    companion object {
        private const val PREFERENCES_NAME = "yt_dlp_update_manager"
        private const val KEY_CURRENT_VERSION = "current_version"
        private const val KEY_PREVIOUS_VERSION = "previous_version"
        private const val KEY_REJECTED_VERSION = "rejected_version"
        private const val KEY_LAST_CHECK_EPOCH_MS = "last_check_epoch_ms"
        private const val KEY_RECOVERY_NOTICE = "recovery_notice"

        private const val MANAGER_DIRECTORY_NAME = "mediadownloader-update"
        private const val PREVIOUS_BINARY_NAME = "yt-dlp.previous"
        private const val PENDING_BACKUP_NAME = "yt-dlp.backup.pending"
        private const val STAGED_PREVIOUS_NAME = "yt-dlp.rollback.pending"
        private const val JOURNAL_FILE_NAME = "transaction.properties"
        private const val JOURNAL_KIND = "kind"
        private const val JOURNAL_PHASE = "phase"
        private const val JOURNAL_ORIGINAL = "original_version"
        private const val JOURNAL_TARGET = "target_version"

        private const val NETWORK_CONNECT_TIMEOUT_MS = 8_000
        private const val NETWORK_READ_TIMEOUT_MS = 12_000
        private const val MAX_RELEASE_RESPONSE_CHARS = 1_000_000

        @Volatile
        private var instance: YtDlpUpdateManager? = null

        fun getInstance(context: Context): YtDlpUpdateManager = instance ?: synchronized(this) {
            instance ?: YtDlpUpdateManager(context).also { instance = it }
        }
    }
}
