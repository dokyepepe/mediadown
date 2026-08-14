package com.mediadownloader.mobile.update

import java.util.concurrent.TimeUnit

internal object YtDlpUpdatePolicy {
    val automaticCheckIntervalMs: Long = TimeUnit.DAYS.toMillis(1)

    fun isAutomaticCheckDue(
        lastCheckEpochMs: Long,
        nowEpochMs: Long,
        intervalMs: Long = automaticCheckIntervalMs,
    ): Boolean {
        if (lastCheckEpochMs <= 0L) return true
        if (nowEpochMs < lastCheckEpochMs) return true
        return nowEpochMs - lastCheckEpochMs >= intervalMs
    }

    fun normalizeVersion(value: String?): String? = value
        ?.trim()
        ?.lineSequence()
        ?.firstOrNull { it.isNotBlank() }
        ?.trim()
        ?.removePrefix("yt-dlp")
        ?.removePrefix("stable@")
        ?.removePrefix("nightly@")
        ?.removePrefix("master@")
        ?.removePrefix("v")
        ?.trim()
        ?.takeIf(String::isNotBlank)

    fun availability(
        currentVersion: String?,
        latestVersion: String,
        rejectedVersion: String?,
    ): YtDlpAvailability {
        val current = normalizeVersion(currentVersion)
        val latest = normalizeVersion(latestVersion).orEmpty()
        val rejected = normalizeVersion(rejectedVersion)
        return when {
            latest.isBlank() -> YtDlpAvailability.INVALID
            latest == current -> YtDlpAvailability.UP_TO_DATE
            latest == rejected -> YtDlpAvailability.REJECTED
            else -> YtDlpAvailability.AVAILABLE
        }
    }
}

internal enum class YtDlpAvailability {
    AVAILABLE,
    UP_TO_DATE,
    REJECTED,
    INVALID,
}

internal enum class YtDlpTransactionKind {
    UPDATE,
    MANUAL_ROLLBACK,
}

internal enum class YtDlpTransactionPhase {
    PREPARED,
    SWAPPED,
    RESTORING,
}

internal data class YtDlpTransactionJournal(
    val kind: YtDlpTransactionKind,
    val phase: YtDlpTransactionPhase,
    val originalVersion: String,
    val targetVersion: String,
)

internal enum class YtDlpRecoveryAction {
    FINALIZE_TARGET,
    KEEP_ORIGINAL,
    RESTORE_ORIGINAL,
}

internal fun recoveryAction(
    journal: YtDlpTransactionJournal,
    observedVersion: String?,
    smokePassed: Boolean,
): YtDlpRecoveryAction {
    val observed = YtDlpUpdatePolicy.normalizeVersion(observedVersion)
    val original = YtDlpUpdatePolicy.normalizeVersion(journal.originalVersion)
    val target = YtDlpUpdatePolicy.normalizeVersion(journal.targetVersion)
    return when {
        smokePassed && observed == target -> YtDlpRecoveryAction.FINALIZE_TARGET
        smokePassed && observed == original -> YtDlpRecoveryAction.KEEP_ORIGINAL
        else -> YtDlpRecoveryAction.RESTORE_ORIGINAL
    }
}
