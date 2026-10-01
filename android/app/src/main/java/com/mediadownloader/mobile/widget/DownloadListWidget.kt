package com.mediadownloader.mobile.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import android.widget.RemoteViewsService
import com.mediadownloader.mobile.MainActivity
import com.mediadownloader.mobile.R
import com.mediadownloader.mobile.data.DownloadItem
import com.mediadownloader.mobile.data.DownloadRepository
import com.mediadownloader.mobile.data.DownloadState
import java.util.concurrent.Executors

/**
 * Home-screen list widget: shows the live queue (active + queued items) and
 * opens the downloads screen when a row is tapped.
 */
class DownloadListWidget : AppWidgetProvider() {

    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray,
    ) {
        refresh(context, force = true)
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == ACTION_OPEN_LIST) {
            val open = Intent(context, MainActivity::class.java)
                .setAction(ACTION_OPEN_LIST)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
            context.startActivity(open)
        }
        super.onReceive(context, intent)
    }

    companion object {
        // Must match MediaDownloaderViewModel.WIDGET_ACTION_OPEN_LIST.
        const val ACTION_OPEN_LIST = "com.mediadownloader.mobile.action.WIDGET_OPEN_LIST"

        private const val REFRESH_THROTTLE_MS = 1400L
        private const val REQUEST_OPEN_LIST = 31

        private val executor: java.util.concurrent.Executor = Executors.newSingleThreadExecutor { runnable ->
            Thread(runnable, "download-list-widget").apply { priority = Thread.NORM_PRIORITY }
        }

        @Volatile
        private var lastRefreshMs = 0L

        const val MAX_ROWS = 9

        fun refresh(context: Context, force: Boolean = false) {
            val now = System.currentTimeMillis()
            if (!force && now - lastRefreshMs < REFRESH_THROTTLE_MS) return
            lastRefreshMs = now
            val appContext = context.applicationContext
            executor.execute {
                runCatching { refreshBlocking(appContext) }
            }
        }

        @Suppress("DEPRECATION")
        private fun refreshBlocking(context: Context) {
            val widgetManager = AppWidgetManager.getInstance(context)
            val component = ComponentName(context, DownloadListWidget::class.java)
            val appWidgetIds = widgetManager.getAppWidgetIds(component)
            if (appWidgetIds.isEmpty()) return
            appWidgetIds.forEach { appWidgetId ->
                val views = RemoteViews(context.packageName, R.layout.widget_download_list)
                val adapter = Intent(context, DownloadListWidgetService::class.java)
                views.setRemoteAdapter(R.id.widget_list, adapter)
                views.setEmptyView(R.id.widget_list, R.id.widget_list_empty)
                views.setPendingIntentTemplate(
                    R.id.widget_list,
                    PendingIntent.getBroadcast(
                        context,
                        REQUEST_OPEN_LIST,
                        Intent(context, DownloadListWidget::class.java)
                            .setAction(ACTION_OPEN_LIST),
                        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
                    ),
                )
                widgetManager.updateAppWidget(appWidgetId, views)
            }
        }
    }
}

class DownloadListWidgetService : android.widget.RemoteViewsService() {
    override fun onGetViewFactory(intent: Intent): RemoteViewsService.RemoteViewsFactory =
        DownloadItemFactory(applicationContext)
}

class DownloadItemFactory(private val context: Context) : RemoteViewsService.RemoteViewsFactory {

    private val items: MutableList<DownloadItem> = mutableListOf()

    override fun onCreate() = Unit

    override fun onDataSetChanged() {
        val all = DownloadRepository.getInstance(context).downloads.value
            .filter { it.state !in TERMINAL_STATES }
            .sortedWith(compareByDescending<DownloadItem> { it.state in ACTIVE_STATES }
                .thenByDescending { it.createdAtEpochMs })
        items.clear()
        items.addAll(all.take(DownloadListWidget.MAX_ROWS))
    }

    override fun onDestroy() = Unit

    override fun getCount(): Int = items.size

    override fun getViewAt(position: Int): RemoteViews {
        val item = items[position]
        val views = RemoteViews(context.packageName, R.layout.widget_download_list_item)
        views.setTextViewText(R.id.widget_list_item_title, item.title)
        val (status, progress, indeterminate) = statusOf(item)
        views.setTextViewText(R.id.widget_list_item_status, status)
        views.setProgressBar(R.id.widget_list_item_progress, 100, progress, indeterminate)
        views.setTextViewText(R.id.widget_list_pos, (position + 1).toString())
        return views
    }

    override fun getLoadingView(): RemoteViews? = null

    override fun getViewTypeCount(): Int = 1

    override fun hasStableIds(): Boolean = true

    override fun getItemId(position: Int): Long = items[position].id.hashCode().toLong()

    private fun statusOf(item: DownloadItem): Triple<String, Int, Boolean> = when (item.state) {
        DownloadState.DOWNLOADING -> Triple("Baixando ${item.progress}%", item.progress, false)
        DownloadState.PROCESSING -> Triple("Processando", item.progress, false)
        DownloadState.INITIALIZING -> Triple("Iniciando", 0, true)
        else -> Triple("Na fila", 0, true)
    }

    private companion object {
        val ACTIVE_STATES = setOf(
            DownloadState.INITIALIZING,
            DownloadState.DOWNLOADING,
            DownloadState.PROCESSING,
        )
        val TERMINAL_STATES = setOf(
            DownloadState.COMPLETED,
            DownloadState.FAILED,
            DownloadState.CANCELLED,
        )
    }
}