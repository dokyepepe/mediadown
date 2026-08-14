package com.mediadownloader.mobile.update

import java.util.concurrent.TimeUnit

internal object YtDlpUpdatePolicy {
    val automaticCheckIntervalMs: Long = TimeUnit.DAYS.toMillis(1)

    private val releaseVersionPattern =
        Regex("^(\\d{4})\\.(\\d{1,2})\\.(\\d{1,2})(?:[.-](\\d+))?$")

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
        val latest = normalizeVersion(latestVersion)
        val rejected = normalizeVersion(rejectedVersion)
        return when {
            latest == null || versionParts(latest) == null -> YtDlpAvailability.INVALID
            current != null && compareVersions(current, latest)?.let { it >= 0 } == true ->
                YtDlpAvailability.UP_TO_DATE
            latest == rejected -> YtDlpAvailability.REJECTED
            else -> YtDlpAvailability.AVAILABLE
        }
    }

    /** Compara versões de release do yt-dlp sem transformar uma versão mais nova em downgrade. */
    fun compareVersions(left: String?, right: String?): Int? {
        val leftParts = normalizeVersion(left)?.let(::versionParts) ?: return null
        val rightParts = normalizeVersion(right)?.let(::versionParts) ?: return null
        return leftParts.zip(rightParts)
            .firstOrNull { (leftPart, rightPart) -> leftPart != rightPart }
            ?.let { (leftPart, rightPart) -> leftPart.compareTo(rightPart) }
            ?: 0
    }

    private fun versionParts(version: String): List<Long>? {
        val match = releaseVersionPattern.matchEntire(version) ?: return null
        return match.groupValues.drop(1).map { part ->
            if (part.isBlank()) 0L else part.toLongOrNull() ?: return null
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
        smokePassed &&
            journal.kind == YtDlpTransactionKind.UPDATE &&
            YtDlpUpdatePolicy.compareVersions(observed, target)?.let { it > 0 } == true ->
            YtDlpRecoveryAction.FINALIZE_TARGET
        else -> YtDlpRecoveryAction.RESTORE_ORIGINAL
    }
}
