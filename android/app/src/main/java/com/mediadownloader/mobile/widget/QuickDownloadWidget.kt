package com.mediadownloader.mobile.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import com.mediadownloader.mobile.MainActivity
import com.mediadownloader.mobile.R

/**
 * Home-screen widget with a single tap action: it reads whatever media link is
 * in the clipboard and enqueues it directly. The heavy lifting happens in
 * [MainActivity]/[com.mediadownloader.mobile.MediaDownloaderViewModel], which
 * observe the [ACTION_DOWNLOAD] intent action.
 */
class QuickDownloadWidget : AppWidgetProvider() {

    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray,
    ) {
        appWidgetIds.forEach { appWidgetId ->
            appWidgetManager.updateAppWidget(appWidgetId, buildRemoteViews(context))
        }
    }

    companion object {
        // Must match MediaDownloaderViewModel.WIDGET_ACTION_DOWNLOAD.
        const val ACTION_DOWNLOAD = "com.mediadownloader.mobile.action.WIDGET_DOWNLOAD"

        fun buildRemoteViews(context: Context): RemoteViews =
            RemoteViews(context.packageName, R.layout.widget_quick_download).apply {
                setOnClickPendingIntent(R.id.widget_download, downloadIntent(context))
                setOnClickPendingIntent(R.id.widget_open, openIntent(context))
            }

        private fun downloadIntent(context: Context): PendingIntent =
            PendingIntent.getActivity(
                context,
                REQUEST_DOWNLOAD,
                Intent(context, MainActivity::class.java)
                    .setAction(ACTION_DOWNLOAD)
                    .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )

        private fun openIntent(context: Context): PendingIntent =
            PendingIntent.getActivity(
                context,
                REQUEST_OPEN,
                Intent(context, MainActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )

        private const val REQUEST_DOWNLOAD = 21
        private const val REQUEST_OPEN = 22
    }
}