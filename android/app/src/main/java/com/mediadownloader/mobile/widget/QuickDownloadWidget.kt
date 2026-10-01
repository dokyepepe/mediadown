package com.mediadownloader.mobile.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.widget.RemoteViews
import com.mediadownloader.mobile.MainActivity
import com.mediadownloader.mobile.R
import com.mediadownloader.mobile.data.DownloadRepository
import com.mediadownloader.mobile.data.DownloadState
import com.mediadownloader.mobile.data.MediaType
import com.mediadownloader.mobile.data.MobileSettingsStore
import com.mediadownloader.mobile.ui.ThemePreference
import java.util.concurrent.Executors

/**
 * Home-screen widget: reads whatever media link is in the clipboard and enqueues
 * it directly. It is reasonabily alive: refreshes itself on every meaningful
 * queue change (see [refresh]) and follows the app's theme preference.
 */
class QuickDownloadWidget : AppWidgetProvider() {

    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray,
    ) {
        refresh(context, force = true)
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == ACTION_TOGGLE_KIND) {
            val store = MobileSettingsStore.open(context)
            store.widgetDownloadKindName =
                if (store.widgetDownloadKindName == MediaType.VIDEO.name) {
                    MediaType.AUDIO.name
                } else {
                    MediaType.VIDEO.name
                }
            refresh(context, force = true)
        }
        super.onReceive(context, intent)
    }

    companion object {
        // Must match MediaDownloaderViewModel.WIDGET_ACTION_DOWNLOAD.
        const val ACTION_DOWNLOAD = "com.mediadownloader.mobile.action.WIDGET_DOWNLOAD"
        const val ACTION_TOGGLE_KIND = "com.mediadownloader.mobile.action.WIDGET_TOGGLE_KIND"

        private const val PREFERENCES_NAME = "mobile_settings"
        private const val KEY_THEME = "theme"

        private const val COLOR_TITLE_LIGHT = 0xFF1E2A24.toInt()
        private const val COLOR_MUTED_LIGHT = 0xFF56655C.toInt()
        private const val COLOR_OPEN_TEXT_LIGHT = 0xFF146B4A.toInt()
        private const val COLOR_TITLE_DARK = 0xFFF0F7F3.toInt()
        private const val COLOR_MUTED_DARK = 0xFFA9B7AF.toInt()
        private const val COLOR_OPEN_TEXT_DARK = 0xFF8CE5B9.toInt()

        private const val REFRESH_THROTTLE_MS = 1400L

        private val executor: java.util.concurrent.Executor = Executors.newSingleThreadExecutor { runnable ->
            Thread(runnable, "quick-download-widget").apply { priority = Thread.NORM_PRIORITY }
        }

        @Volatile
        private var lastRefreshMs = 0L

        fun refresh(context: Context, force: Boolean = false) {
            val now = System.currentTimeMillis()
            if (!force && now - lastRefreshMs < REFRESH_THROTTLE_MS) return
            lastRefreshMs = now
            val appContext = context.applicationContext
            executor.execute {
                runCatching { refreshBlocking(appContext) }
            }
        }

        private fun refreshBlocking(context: Context) {
            val widgetManager = AppWidgetManager.getInstance(context)
            val component = ComponentName(context, QuickDownloadWidget::class.java)
            val appWidgetIds = widgetManager.getAppWidgetIds(component)
            if (appWidgetIds.isEmpty()) return
            val dark = resolveDarkTheme(context)
            val status = currentStatusText(context)
            val kindName = MobileSettingsStore.open(context).widgetDownloadKindName
            appWidgetIds.forEach { appWidgetId ->
                widgetManager.updateAppWidget(
                    appWidgetId,
                    buildRemoteViews(context, dark, status, kindName),
                )
            }
        }

        fun buildRemoteViews(
            context: Context,
            dark: Boolean,
            statusText: String = "",
            kindName: String = MediaType.VIDEO.name,
        ): RemoteViews {
            val colorOpenText = if (dark) COLOR_OPEN_TEXT_DARK else COLOR_OPEN_TEXT_LIGHT
            val colorMuted = if (dark) COLOR_MUTED_DARK else COLOR_MUTED_LIGHT
            val colorTitle = if (dark) COLOR_TITLE_DARK else COLOR_TITLE_LIGHT
            return RemoteViews(context.packageName, R.layout.widget_quick_download).apply {
                setTextViewText(R.id.widget_status, statusText)
                val kindLabel = if (kindName == MediaType.AUDIO.name) {
                    context.getString(R.string.quick_download_widget_kind_audio)
                } else {
                    context.getString(R.string.quick_download_widget_kind_video)
                }
                setTextViewText(R.id.widget_kind, kindLabel)
                setInt(
                    R.id.widget_open,
                    "setBackgroundResource",
                    if (dark) R.drawable.widget_card_background_dark else R.drawable.widget_card_background,
                )
                setInt(
                    R.id.widget_download,
                    "setBackgroundResource",
                    if (dark) R.drawable.widget_button_primary_dark else R.drawable.widget_button_primary,
                )
                setInt(
                    R.id.widget_secondary,
                    "setBackgroundResource",
                    if (dark) R.drawable.widget_button_secondary_dark else R.drawable.widget_button_secondary,
                )
                setInt(
                    R.id.widget_kind,
                    "setBackgroundResource",
                    if (dark) R.drawable.widget_button_secondary_dark else R.drawable.widget_button_secondary,
                )
                setTextColor(R.id.widget_title, colorTitle)
                setTextColor(R.id.widget_subtitle, colorMuted)
                setTextColor(R.id.widget_status, colorMuted)
                setTextColor(R.id.widget_download, 0xFFFFFFFF.toInt())
                setTextColor(R.id.widget_secondary, colorOpenText)
                setTextColor(R.id.widget_kind, colorOpenText)
                setOnClickPendingIntent(R.id.widget_download, downloadIntent(context))
                setOnClickPendingIntent(R.id.widget_open, openIntent(context))
                setOnClickPendingIntent(R.id.widget_secondary, openIntent(context))
                setOnClickPendingIntent(R.id.widget_kind, toggleKindIntent(context))
            }
        }

        private fun toggleKindIntent(context: Context): PendingIntent =
            PendingIntent.getBroadcast(
                context,
                REQUEST_TOGGLE_KIND,
                Intent(context, QuickDownloadWidget::class.java).setAction(ACTION_TOGGLE_KIND),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )

        fun openIntent(context: Context): PendingIntent =
            PendingIntent.getActivity(
                context,
                REQUEST_OPEN,
                Intent(context, MainActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )

        private fun downloadIntent(context: Context): PendingIntent =
            PendingIntent.getActivity(
                context,
                REQUEST_DOWNLOAD,
                Intent(context, MainActivity::class.java)
                    .setAction(ACTION_DOWNLOAD)
                    .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )

        private fun resolveDarkTheme(context: Context): Boolean {
            val preferences = context.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)
            val preference = runCatching {
                ThemePreference.valueOf(
                    preferences.getString(KEY_THEME, ThemePreference.SYSTEM.name).orEmpty(),
                )
            }.getOrDefault(ThemePreference.SYSTEM)
            return when (preference) {
                ThemePreference.LIGHT -> false
                ThemePreference.DARK -> true
                ThemePreference.AMOLED -> true
                ThemePreference.SYSTEM ->
                    (context.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) ==
                        Configuration.UI_MODE_NIGHT_YES
            }
        }

        private fun currentStatusText(context: Context): String {
            val items = DownloadRepository.getInstance(context).downloads.value
            val active = items.firstOrNull { item -> item.state in ACTIVE_STATES }
            return when {
                active != null -> when (active.state) {
                    DownloadState.PROCESSING -> context.getString(
                        R.string.quick_download_widget_status_processing,
                        active.title,
                    )
                    else -> context.getString(
                        R.string.quick_download_widget_status_downloading,
                        active.title,
                        active.progress,
                    )
                }
                else -> {
                    val queued = items.count { it.state == DownloadState.QUEUED }
                    if (queued > 0) {
                        context.resources.getQuantityString(
                            R.plurals.quick_download_widget_status_queued,
                            queued,
                            queued,
                        )
                    } else {
                        context.getString(R.string.quick_download_widget_status_idle)
                    }
                }
            }
        }

        private val ACTIVE_STATES = setOf(
            DownloadState.INITIALIZING,
            DownloadState.DOWNLOADING,
            DownloadState.PROCESSING,
        )

        private const val REQUEST_DOWNLOAD = 21
        private const val REQUEST_OPEN = 22
        private const val REQUEST_TOGGLE_KIND = 23
    }
}