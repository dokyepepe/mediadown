package com.mediadownloader.mobile.preview

import android.content.Context
import android.net.Uri
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import java.io.File

/**
 * Plays a rendered preview clip through ExoPlayer. The same player drives both
 * audio-only clips and clips that keep a video stream; the Compose layer feeds
 * its `PlayerView` with [player].
 */
class PreviewPlayer(context: Context) {
    val player: ExoPlayer = ExoPlayer.Builder(context.applicationContext).build()

    private var onStarted: (() -> Unit)? = null
    private var onFinished: (() -> Unit)? = null
    private var onError: ((String) -> Unit)? = null

    private val listener = object : Player.Listener {
        override fun onPlaybackStateChanged(playbackState: Int) {
            when (playbackState) {
                Player.STATE_READY -> onStarted?.invoke()
                Player.STATE_ENDED -> onFinished?.invoke()
                else -> Unit
            }
        }

        override fun onPlayerError(error: PlaybackException) {
            onError?.invoke(
                "Não foi possível tocar a prévia." +
                    error.message?.trim()?.take(200)?.let { " $it" }.orEmpty(),
            )
        }
    }

    fun play(
        file: File,
        onStarted: () -> Unit,
        onFinished: () -> Unit,
        onError: (String) -> Unit,
    ) {
        stop()
        this.onStarted = onStarted
        this.onFinished = onFinished
        this.onError = onError
        player.addListener(listener)
        player.setMediaItem(MediaItem.fromUri(Uri.fromFile(file)))
        player.prepare()
        player.playWhenReady = true
    }

    fun stop() {
        player.removeListener(listener)
        player.stop()
        player.clearMediaItems()
        onStarted = null
        onFinished = null
        onError = null
    }

    fun release() {
        player.release()
    }
}