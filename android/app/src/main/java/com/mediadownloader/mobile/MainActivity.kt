package com.mediadownloader.mobile

import android.Manifest
import android.app.PictureInPictureParams
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.graphics.Rect
import android.util.Rational
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.core.content.ContextCompat
import com.mediadownloader.mobile.ui.MediaDownloaderApp
import com.mediadownloader.mobile.ui.MobileUiAction

class MainActivity : ComponentActivity() {
    private val viewModel: MediaDownloaderViewModel by viewModels()

    private val notificationPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { }

    private val storagePermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        viewModel.onStoragePermissionResult(granted)
    }

    private val downloadLocation = registerForActivityResult(
        ActivityResultContracts.OpenDocumentTree(),
    ) { uri ->
        val persistedLocation = uri?.let { selected ->
            runCatching {
                contentResolver.takePersistableUriPermission(
                    selected,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
                )
                selected.toString()
            }.getOrElse {
                viewModel.onDownloadLocationSelectionFailed()
                null
            }
        }
        viewModel.onDownloadLocationSelected(persistedLocation)
    }

    private val cookieFile = registerForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri ->
        viewModel.onCookieFileSelected(uri)
    }

    private val settingsImport = registerForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri ->
        uri?.let { viewModel.onAction(MobileUiAction.ImportSettings(it)) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestNotificationPermissionIfNeeded()
        viewModel.setStoragePermissionRequester(::requestStoragePermissionIfNeeded)
        viewModel.setDownloadLocationRequester { downloadLocation.launch(null) }
        viewModel.setCookieFileRequester {
            cookieFile.launch(arrayOf("text/plain", "application/octet-stream", "text/*"))
        }
        if (savedInstanceState == null && !handleSpotifyRedirect(intent)) {
            viewModel.receiveIntent(intent)
        }
        setContent {
            MediaDownloaderApp(
                controller = viewModel,
                onImportSettings = {
                    settingsImport.launch(arrayOf("application/json", "application/octet-stream"))
                },
            )
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (!handleSpotifyRedirect(intent)) {
            viewModel.receiveIntent(intent)
        }
    }

    /**
     * Enters picture-in-picture while a preview clip is playing so the user can keep
     * listening when they leave the app. The aspect ratio is fixed at 16:9, which is
     * what the preview player renders.
     */
    override fun onUserLeaveHint() {
        super.onUserLeaveHint()
        if (!viewModel.isPreviewPlaying) return
        val params = PictureInPictureParams.Builder()
            .setAspectRatio(Rational(PIP_WIDTH, PIP_HEIGHT))
            .setSourceRectHint(pipSourceRect())
            .apply {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                    setAutoEnterEnabled(true)
                    setSeamlessResizeEnabled(true)
                }
            }
            .build()
        runCatching { enterPictureInPictureMode(params) }
    }

    /** The window area the system animates from, so entering PiP is not jarring. */
    @Suppress("DEPRECATION")
    private fun pipSourceRect(): Rect {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val metrics = windowManager.currentWindowMetrics.bounds
            val width = metrics.width().coerceAtLeast(1)
            val height = (width * PIP_HEIGHT / PIP_WIDTH).coerceAtLeast(1)
            val left = metrics.left + (metrics.width() - width) / 2
            val top = metrics.top + (metrics.height() - height) / 2
            Rect(left, top, left + width, top + height)
        } else {
            val display = windowManager.defaultDisplay
            val metrics = android.util.DisplayMetrics()
            display.getMetrics(metrics)
            val width = metrics.widthPixels.coerceAtLeast(1)
            val height = (width * PIP_HEIGHT / PIP_WIDTH).coerceAtLeast(1)
            val left = (metrics.widthPixels - width) / 2
            val top = (metrics.heightPixels - height) / 2
            Rect(left, top, left + width, top + height)
        }
    }

    private companion object {
        const val PIP_WIDTH = 16
        const val PIP_HEIGHT = 9
    }

    /** Returns true when the intent is the Spotify OAuth deep link. */
    private fun handleSpotifyRedirect(intent: Intent?): Boolean {
        val data = intent?.dataString ?: return false
        if (intent.action != Intent.ACTION_VIEW ||
            !data.startsWith("mediadownloader://spotify/callback")
        ) {
            return false
        }
        viewModel.onSpotifyAuthUri(data)
        return true
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    private fun requestStoragePermissionIfNeeded(onGranted: () -> Unit) {
        if (Build.VERSION.SDK_INT > Build.VERSION_CODES.P ||
            ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE) ==
            PackageManager.PERMISSION_GRANTED
        ) {
            onGranted()
            return
        }
        viewModel.setPendingStorageAction(onGranted)
        storagePermission.launch(Manifest.permission.WRITE_EXTERNAL_STORAGE)
    }
}
