package com.mediadownloader.mobile

import android.app.Application
import com.mediadownloader.mobile.update.YtDlpUpdateManager
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class MediaDownloaderApplication : Application() {
    lateinit var ytDlpUpdateManager: YtDlpUpdateManager
        private set

    private val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val ytDlpStartup = CompletableDeferred<Throwable?>()

    override fun onCreate() {
        super.onCreate()
        ytDlpUpdateManager = YtDlpUpdateManager.getInstance(this)
        applicationScope.launch {
            val failure = runCatching { ytDlpUpdateManager.initializeAndRecover() }.exceptionOrNull()
            ytDlpStartup.complete(failure)
        }
    }

    suspend fun awaitYtDlpStartup() {
        ytDlpStartup.await()?.let { throw it }
    }
}
