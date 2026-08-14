package com.mediadownloader.mobile.update

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class YtDlpRuntimeGateTest {
    @Test
    fun writerWaitsUntilActiveReaderFinishes() {
        val readerEntered = CountDownLatch(1)
        val releaseReader = CountDownLatch(1)
        val writerEntered = CountDownLatch(1)
        val executor = Executors.newFixedThreadPool(2)
        try {
            executor.submit {
                YtDlpRuntimeGate.withReadLock {
                    readerEntered.countDown()
                    releaseReader.await()
                }
            }
            assertTrue(readerEntered.await(1, TimeUnit.SECONDS))
            executor.submit {
                YtDlpRuntimeGate.withWriteLock { writerEntered.countDown() }
            }

            assertFalse(writerEntered.await(100, TimeUnit.MILLISECONDS))
            releaseReader.countDown()
            assertTrue(writerEntered.await(1, TimeUnit.SECONDS))
        } finally {
            releaseReader.countDown()
            executor.shutdownNow()
        }
    }

    @Test
    fun readerWaitsWhileRuntimeIsBeingReplaced() {
        val writerEntered = CountDownLatch(1)
        val releaseWriter = CountDownLatch(1)
        val readerEntered = CountDownLatch(1)
        val executor = Executors.newFixedThreadPool(2)
        try {
            executor.submit {
                YtDlpRuntimeGate.withWriteLock {
                    writerEntered.countDown()
                    releaseWriter.await()
                }
            }
            assertTrue(writerEntered.await(1, TimeUnit.SECONDS))
            executor.submit {
                YtDlpRuntimeGate.withReadLock { readerEntered.countDown() }
            }

            assertFalse(readerEntered.await(100, TimeUnit.MILLISECONDS))
            releaseWriter.countDown()
            assertTrue(readerEntered.await(1, TimeUnit.SECONDS))
        } finally {
            releaseWriter.countDown()
            executor.shutdownNow()
        }
    }

    @Test
    fun exceptionDoesNotLeaveWriteLockHeld() {
        runCatching {
            YtDlpRuntimeGate.withWriteLock { error("expected") }
        }

        var entered = false
        YtDlpRuntimeGate.withReadLock { entered = true }
        assertTrue(entered)
    }
}
