package com.mediadownloader.mobile

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
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

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        requestNotificationPermissionIfNeeded()
        viewModel.setStoragePermissionRequester(::requestStoragePermissionIfNeeded)
        viewModel.setDownloadLocationRequester { downloadLocation.launch(null) }
        viewModel.receiveIntent(intent)
        setContent {
            MediaDownloaderApp(controller = viewModel)
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        viewModel.receiveIntent(intent)
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
