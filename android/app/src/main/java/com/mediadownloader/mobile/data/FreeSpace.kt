package com.mediadownloader.mobile.data

import android.annotation.SuppressLint
import android.os.Environment
import android.os.StatFs

/** Usable bytes on the primary external storage, where completed files are saved. */
object FreeSpace {

    /** Below this much free space the queue refuses to start new downloads. */
    const val MIN_SAFE_BYTES = 32L * 1024 * 1024

    @SuppressLint("UsableSpace")
    fun availableBytesOnPrimary(): Long = runCatching {
        StatFs(Environment.getExternalStorageDirectory().absolutePath).availableBytes
    }.getOrDefault(Long.MAX_VALUE)
}