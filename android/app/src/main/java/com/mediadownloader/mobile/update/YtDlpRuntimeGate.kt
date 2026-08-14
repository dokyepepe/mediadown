package com.mediadownloader.mobile.update

import java.util.concurrent.locks.ReentrantReadWriteLock
import kotlin.concurrent.read
import kotlin.concurrent.write

/**
 * Process-wide coordination for the yt-dlp runtime.
 *
 * Executions may run together under a read lock. Anything that replaces the runtime on disk
 * must use the write lock, which waits for active analyses/downloads to finish first.
 */
object YtDlpRuntimeGate {
    private val lock = ReentrantReadWriteLock(true)

    fun <T> withReadLock(block: () -> T): T = lock.read(block)

    @Throws(InterruptedException::class)
    fun <T> withInterruptibleReadLock(block: () -> T): T {
        val readLock = lock.readLock()
        readLock.lockInterruptibly()
        return try {
            block()
        } finally {
            readLock.unlock()
        }
    }

    fun <T> withWriteLock(block: () -> T): T = lock.write(block)
}
