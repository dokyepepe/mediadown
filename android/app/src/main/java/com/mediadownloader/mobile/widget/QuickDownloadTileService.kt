package com.mediadownloader.mobile.widget

import android.annotation.SuppressLint
import android.app.PendingIntent
import android.content.Intent
import android.os.Build
import android.service.quicksettings.TileService
import com.mediadownloader.mobile.MainActivity

/**
 * Quick Settings tile that behaves like the widget's "Colar e baixar":
 * enqueues the current clipboard link using the widget's preferred media type.
 */
class QuickDownloadTileService : TileService() {

    @SuppressLint("StartActivityAndCollapseDeprecated")
    @Suppress("DEPRECATION")
    override fun onClick() {
        val launch = Intent(this, MainActivity::class.java)
            .setAction(QuickDownloadWidget.ACTION_DOWNLOAD)
            .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            val pending = PendingIntent.getActivity(
                this,
                REQUEST_TILE_DOWNLOAD,
                launch,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
            startActivityAndCollapse(pending)
        } else {
            // Deprecated e removido em upgrades do sistema, mas a única opção em 26-33.
            startActivityAndCollapse(launch)
        }
    }

    companion object {
        private const val REQUEST_TILE_DOWNLOAD = 401
    }
}