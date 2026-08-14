package com.mediadownloader.mobile.update

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.TimeUnit

class YtDlpUpdatePolicyTest {
    @Test
    fun automaticCheckRunsAtMostOncePerInterval() {
        val now = TimeUnit.DAYS.toMillis(20)

        assertTrue(YtDlpUpdatePolicy.isAutomaticCheckDue(0L, now))
        assertFalse(YtDlpUpdatePolicy.isAutomaticCheckDue(now - 1_000L, now))
        assertTrue(
            YtDlpUpdatePolicy.isAutomaticCheckDue(
                now - YtDlpUpdatePolicy.automaticCheckIntervalMs,
                now,
            ),
        )
    }

    @Test
    fun automaticCheckRecoversFromClockMovingBackwards() {
        assertTrue(YtDlpUpdatePolicy.isAutomaticCheckDue(lastCheckEpochMs = 2_000L, nowEpochMs = 1_000L))
    }

    @Test
    fun versionsAreNormalizedFromRuntimeAndReleaseFormats() {
        assertEquals("2026.08.12", YtDlpUpdatePolicy.normalizeVersion("stable@2026.08.12\n"))
        assertEquals("2026.08.12", YtDlpUpdatePolicy.normalizeVersion("v2026.08.12"))
        assertEquals("2026.08.12", YtDlpUpdatePolicy.normalizeVersion("yt-dlp 2026.08.12"))
    }

    @Test
    fun rejectedLatestVersionIsNotOfferedAgain() {
        assertEquals(
            YtDlpAvailability.REJECTED,
            YtDlpUpdatePolicy.availability(
                currentVersion = "2026.07.01",
                latestVersion = "2026.08.12",
                rejectedVersion = "2026.08.12",
            ),
        )
        assertEquals(
            YtDlpAvailability.AVAILABLE,
            YtDlpUpdatePolicy.availability(
                currentVersion = "2026.07.01",
                latestVersion = "2026.09.01",
                rejectedVersion = "2026.08.12",
            ),
        )
    }

    @Test
    fun aNewerInstalledVersionIsNeverOfferedAsADowngrade() {
        assertEquals(
            YtDlpAvailability.UP_TO_DATE,
            YtDlpUpdatePolicy.availability(
                currentVersion = "2026.09.01",
                latestVersion = "2026.08.12",
                rejectedVersion = null,
            ),
        )
        assertEquals(1, YtDlpUpdatePolicy.compareVersions("2026.08.12.1", "2026.08.12"))
        assertEquals(
            YtDlpAvailability.INVALID,
            YtDlpUpdatePolicy.availability(
                currentVersion = "2026.08.01",
                latestVersion = "not-a-release",
                rejectedVersion = null,
            ),
        )
    }

    @Test
    fun interruptedSwapFinalizesOnlyAHealthyExpectedTarget() {
        val journal = journal()

        assertEquals(
            YtDlpRecoveryAction.FINALIZE_TARGET,
            recoveryAction(journal, observedVersion = "2026.08.12", smokePassed = true),
        )
        assertEquals(
            YtDlpRecoveryAction.KEEP_ORIGINAL,
            recoveryAction(journal, observedVersion = "2026.07.01", smokePassed = true),
        )
        assertEquals(
            YtDlpRecoveryAction.RESTORE_ORIGINAL,
            recoveryAction(journal, observedVersion = "2026.08.12", smokePassed = false),
        )
        assertEquals(
            YtDlpRecoveryAction.RESTORE_ORIGINAL,
            recoveryAction(journal, observedVersion = "unexpected", smokePassed = true),
        )
        assertEquals(
            YtDlpRecoveryAction.FINALIZE_TARGET,
            recoveryAction(journal, observedVersion = "2026.08.13", smokePassed = true),
        )
        val legacyDowngradeJournal = journal.copy(
            originalVersion = "2026.08.13",
            targetVersion = "2026.08.12",
        )
        assertEquals(
            YtDlpRecoveryAction.KEEP_ORIGINAL,
            recoveryAction(
                legacyDowngradeJournal,
                observedVersion = legacyDowngradeJournal.originalVersion,
                smokePassed = true,
            ),
        )
        assertEquals(
            YtDlpRecoveryAction.RESTORE_ORIGINAL,
            recoveryAction(
                journal.copy(kind = YtDlpTransactionKind.MANUAL_ROLLBACK),
                observedVersion = "2026.08.13",
                smokePassed = true,
            ),
        )
    }

    private fun journal() = YtDlpTransactionJournal(
        kind = YtDlpTransactionKind.UPDATE,
        phase = YtDlpTransactionPhase.SWAPPED,
        originalVersion = "2026.07.01",
        targetVersion = "2026.08.12",
    )
}
