package com.mediadownloader.mobile.data

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import java.time.LocalTime
import java.util.Locale

/**
 * Decides whether the queue should pause right now based on the persisted
 * download rules (Wi-Fi only + daily window). Pure decision helpers live in the
 * companion so they can be unit-tested without Android.
 */
object DownloadGate {

    /** Non-null when downloads must pause; the message explains why. */
    fun pauseReason(context: Context): String? {
        val settings = MobileSettingsStore.open(context)
        if (FreeSpace.availableBytesOnPrimary() < FreeSpace.MIN_SAFE_BYTES) {
            return "Sem espaço livre suficiente no armazenamento"
        }
        if (settings.wifiOnly && !isOnWifi(context)) return "Dispositivo fora do Wi-Fi"
        if (settings.downloadWindowEnabled &&
            !windowContains(settings.downloadWindowStartMin, settings.downloadWindowEndMin, nowMinutes())
        ) {
            return windowLabel(settings.downloadWindowStartMin, settings.downloadWindowEndMin)
        }
        return null
    }

    fun isOnWifi(context: Context): Boolean {
        val manager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            ?: return false
        val capabilities = manager.getNetworkCapabilities(manager.activeNetwork) ?: return false
        return capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
    }

    /**
     * Daily window rule that wraps over midnight. Follows the ISO week pattern:
     * a start before the end is contiguous; a start after the end means
     * "from start until midnight, then from midnight until end".
     */
    fun windowContains(startMin: Int, endMin: Int, nowMinutes: Int): Boolean =
        if (startMin == endMin) {
            true
        } else if (startMin < endMin) {
            nowMinutes in startMin until endMin
        } else {
            nowMinutes >= startMin || nowMinutes < endMin
        }

    fun windowLabel(startMin: Int, endMin: Int): String =
        "Janela agendada (${hhmm(startMin)}–${hhmm(endMin)})"

    fun hhmm(minutesOfDay: Int): String {
        val clamped = minutesOfDay.coerceIn(0, 1439)
        return String.format(Locale.ROOT, "%02d:%02d", clamped / 60, clamped % 60)
    }

    private fun nowMinutes(): Int {
        val now = LocalTime.now()
        return now.hour * 60 + now.minute
    }
}