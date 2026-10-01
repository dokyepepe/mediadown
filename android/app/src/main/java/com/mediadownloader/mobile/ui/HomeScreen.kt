package com.mediadownloader.mobile.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.OpenInNew
import androidx.compose.material.icons.automirrored.rounded.VolumeUp
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.CloudDownload
import androidx.compose.material.icons.rounded.ClosedCaption
import androidx.compose.material.icons.rounded.ContentCut
import androidx.compose.material.icons.rounded.ContentPaste
import androidx.compose.material.icons.rounded.GraphicEq
import androidx.compose.material.icons.rounded.Headphones
import androidx.compose.material.icons.rounded.HighlightOff
import androidx.compose.material.icons.automirrored.rounded.Label
import androidx.compose.material.icons.rounded.Image
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.Link
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.MusicNote
import androidx.compose.material.icons.automirrored.rounded.PlaylistPlay
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.automirrored.rounded.PlaylistAdd
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Repeat
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Star
import androidx.compose.material.icons.rounded.Stop
import androidx.compose.material.icons.rounded.Tune
import androidx.compose.material.icons.rounded.Videocam
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ElevatedFilterChip
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.mediadownloader.mobile.R
import kotlin.math.abs
import java.util.Locale

@Composable
fun HomeScreen(
    state: HomeUiState,
    onAction: (MobileUiAction) -> Unit,
    thumbnail: ThumbnailRenderer,
    modifier: Modifier = Modifier,
    previewPlayer: ExoPlayer? = null,
) {
    ScreenContainer(modifier) {
        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 20.dp, vertical = 24.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            item {
                ScreenHeading(
                    eyebrow = stringResource(R.string.home_heading_eyebrow),
                    title = stringResource(R.string.home_heading_title),
                    supportingText = stringResource(R.string.home_heading_supporting),
                    icon = Icons.Rounded.CloudDownload,
                )
            }

            item {
                UrlInputCard(state = state, onAction = onAction)
            }

            state.analysisHint?.let { hint ->
                item {
                    InfoBanner(
                        text = hint,
                        icon = Icons.Rounded.Info,
                    )
                }
            }

            val analyzedPreview = state.preview
            if (analyzedPreview != null) {
                val preview = analyzedPreview
                item {
                    PreviewCard(
                        preview = preview,
                        thumbnail = thumbnail,
                        onClear = { onAction(MobileUiAction.ClearAnalysis) },
                    )
                }

                item {
                    AudioEffectsCard(
                        state = state,
                        onAction = onAction,
                        previewPlayer = previewPlayer,
                    )
                }

                item {
                    TrimAndFadeCard(
                        state = state,
                        onAction = onAction,
                    )
                }

                item {
                    DownloadOptionsCard(
                        state = state,
                        preview = preview,
                        onAction = onAction,
                    )
                }

                if (preview.isPlaylist && preview.playlistItems.isNotEmpty()) {
                    item {
                        PlaylistSelectionCard(
                            state = state,
                            preview = preview,
                            onAction = onAction,
                        )
                    }
                }

                item {
                    Button(
                        onClick = { onAction(MobileUiAction.StartDownload) },
                        enabled = state.canDownload,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 56.dp),
                        shape = MaterialTheme.shapes.medium,
                    ) {
                        if (state.isStartingDownload) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(20.dp),
                                strokeWidth = 2.dp,
                                color = MaterialTheme.colorScheme.onPrimary,
                            )
                            Spacer(Modifier.size(10.dp))
                            Text(stringResource(R.string.home_action_queued))
                        } else {
                            Icon(
                                imageVector = Icons.Rounded.CloudDownload,
                                contentDescription = null,
                                modifier = Modifier.size(21.dp),
                            )
                            Spacer(Modifier.size(9.dp))
                            val selectedItems = state.selectedPlaylistItems.size
                            Text(
                                when {
                                    preview.isPlaylist && state.downloadPlaylist ->
                                        stringResource(R.string.home_action_download_playlist)
                                    preview.isPlaylist -> pluralStringResource(
                                        R.plurals.home_download_items,
                                        selectedItems,
                                        selectedItems,
                                    )
                                    else -> stringResource(R.string.home_action_download_now)
                                },
                            )
                        }
                    }
                }
            } else if (state.spotify != null) {
                item {
                    SpotifyCard(
                        media = state.spotify,
                        isDownloading = state.isSpotifyDownloading,
                        onAction = onAction,
                    )
                }
            } else {
                item {
                    InfoBanner(
                        text = stringResource(R.string.home_privacy_banner),
                        icon = Icons.Rounded.Lock,
                        containerColor = MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.72f),
                        contentColor = MaterialTheme.colorScheme.onTertiaryContainer,
                    )
                }
            }

            item { Spacer(Modifier.height(4.dp)) }
        }
    }
}

@Composable
private fun SpotifyCard(
    media: SpotifyMediaUi,
    isDownloading: Boolean,
    onAction: (MobileUiAction) -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            SectionTitle(
                title = stringResource(R.string.home_spotify_title),
                supportingText = stringResource(R.string.home_spotify_supporting),
                icon = Icons.Rounded.MusicNote,
            )

            Surface(
                shape = MaterialTheme.shapes.medium,
                color = MaterialTheme.colorScheme.surfaceContainer,
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(14.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Text(
                        text = media.resourceLabel.uppercase(),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        text = media.title,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                    )
                    media.subtitle?.takeIf(String::isNotBlank)?.let { subtitle ->
                        Text(
                            text = subtitle,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    val count = media.itemCount ?: media.tracks.size.takeIf { it > 0 }
                    if (count != null) {
                        Text(
                            text = pluralStringResource(R.plurals.home_spotify_tracks, count, count),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            if (media.requiresAuth && !media.authenticated) {
                InfoBanner(
                    text = stringResource(R.string.home_spotify_auth_hint),
                    icon = Icons.Rounded.Lock,
                )
            }
            media.notice?.takeIf(String::isNotBlank)?.let { notice ->
                InfoBanner(text = notice, icon = Icons.Rounded.Info)
            }

            if (media.tracks.isNotEmpty()) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    media.tracks.take(SPOTIFY_TRACK_PREVIEW_LIMIT).forEach { track ->
                        SpotifyTrackRow(track)
                    }
                    if (media.tracks.size > SPOTIFY_TRACK_PREVIEW_LIMIT) {
                        val hiddenTracks = media.tracks.size - SPOTIFY_TRACK_PREVIEW_LIMIT
                        Text(
                            text = pluralStringResource(
                                R.plurals.home_spotify_more_tracks,
                                hiddenTracks,
                                hiddenTracks,
                            ),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            Button(
                onClick = { onAction(MobileUiAction.DownloadSpotifyOnYouTube) },
                enabled = !isDownloading,
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 56.dp),
                shape = MaterialTheme.shapes.medium,
            ) {
                if (isDownloading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                    Spacer(Modifier.size(10.dp))
                    Text(stringResource(R.string.home_action_queued))
                } else {
                    Icon(
                        imageVector = Icons.Rounded.CloudDownload,
                        contentDescription = null,
                        modifier = Modifier.size(21.dp),
                    )
                    Spacer(Modifier.size(9.dp))
                    Text(
                        if (media.tracks.size > 1) {
                            stringResource(R.string.home_spotify_download_tracks)
                        } else {
                            stringResource(R.string.home_spotify_download_audio)
                        },
                    )
                }
            }

            Text(
                text = stringResource(R.string.home_spotify_notice),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun SpotifyTrackRow(track: SpotifyTrackUi) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = track.index.toString(),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.width(22.dp),
        )
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(
                text = track.title,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (track.artist.isNotBlank()) {
                Text(
                    text = track.artist,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        track.durationText?.let { duration ->
            Text(
                text = duration,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private const val SPOTIFY_TRACK_PREVIEW_LIMIT = 20

@Composable
private fun UrlInputCard(
    state: HomeUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            SectionTitle(
                title = stringResource(R.string.home_url_title),
                supportingText = stringResource(R.string.home_url_supporting),
                icon = Icons.Rounded.Link,
            )
            OutlinedTextField(
                value = state.url,
                onValueChange = { onAction(MobileUiAction.UrlChanged(it)) },
                modifier = Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.home_url_label)) },
                placeholder = { Text("https://â€¦") },
                leadingIcon = {
                    Icon(imageVector = Icons.Rounded.Link, contentDescription = null)
                },
                supportingText = state.urlError?.let { error ->
                    { Text(error) }
                },
                isError = state.urlError != null,
                enabled = !state.isAnalyzing && !state.isStartingDownload,
                minLines = 1,
                maxLines = 3,
                shape = MaterialTheme.shapes.medium,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Uri,
                    imeAction = ImeAction.Go,
                ),
                keyboardActions = KeyboardActions(
                    onGo = {
                        if (state.canAnalyze) onAction(MobileUiAction.AnalyzeUrl)
                    },
                ),
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                FilledTonalButton(
                    onClick = { onAction(MobileUiAction.PasteUrl) },
                    enabled = state.canPaste && !state.isAnalyzing,
                    modifier = Modifier
                        .weight(1f)
                        .heightIn(min = 50.dp),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.ContentPaste,
                        contentDescription = null,
                        modifier = Modifier.size(19.dp),
                    )
                    Spacer(Modifier.size(8.dp))
                    Text(stringResource(R.string.action_paste))
                }
                Button(
                    onClick = { onAction(MobileUiAction.AnalyzeUrl) },
                    enabled = state.canAnalyze,
                    modifier = Modifier
                        .weight(1.35f)
                        .heightIn(min = 50.dp),
                ) {
                    if (state.isAnalyzing) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp,
                            color = MaterialTheme.colorScheme.onPrimary,
                        )
                        Spacer(Modifier.size(8.dp))
                        Text(stringResource(R.string.home_action_analyzing))
                    } else {
                        Icon(
                            imageVector = Icons.Rounded.Search,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                        )
                        Spacer(Modifier.size(8.dp))
                        Text(stringResource(R.string.home_action_analyze))
                    }
                }
            }

            if (state.batchCount > 1) {
                InfoBanner(
                    text = pluralStringResource(
                        R.plurals.home_batch_hint,
                        state.batchCount,
                        state.batchCount,
                    ),
                    icon = Icons.AutoMirrored.Rounded.PlaylistAdd,
                    containerColor = MaterialTheme.colorScheme.secondaryContainer,
                    contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
                )
                Button(
                    onClick = { onAction(MobileUiAction.EnqueueUrlBatch) },
                    enabled = state.canEnqueueBatch,
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 50.dp),
                ) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Rounded.PlaylistAdd,
                        contentDescription = null,
                        modifier = Modifier.size(20.dp),
                    )
                    Spacer(Modifier.size(8.dp))
                    Text(
                        pluralStringResource(
                            R.plurals.home_action_enqueue_batch,
                            state.batchCount,
                            state.batchCount,
                        ),
                    )
                }
            }
        }
    }
}

@Composable
private fun PreviewCard(
    preview: MediaPreviewUi,
    thumbnail: ThumbnailRenderer,
    onClear: () -> Unit,
) {
    SectionCard(contentPadding = PaddingValues(0.dp)) {
        Column {
            Box(modifier = Modifier.fillMaxWidth()) {
                thumbnail(
                    preview.thumbnailUrl,
                    preview.sourceUrl,
                    "Miniatura de ${preview.title}",
                    Modifier
                        .fillMaxWidth()
                        .aspectRatio(16f / 9f),
                )
                StatusPill(
                    label = preview.sourceName,
                    containerColor = MaterialTheme.colorScheme.inverseSurface.copy(alpha = 0.88f),
                    contentColor = MaterialTheme.colorScheme.inverseOnSurface,
                    modifier = Modifier
                        .align(Alignment.BottomStart)
                        .padding(14.dp),
                )
            }

            Column(
                modifier = Modifier.padding(18.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalAlignment = Alignment.Top,
                ) {
                    Column(
                        modifier = Modifier.weight(1f),
                        verticalArrangement = Arrangement.spacedBy(5.dp),
                    ) {
                        Text(
                            text = stringResource(R.string.home_preview_found),
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        Text(
                            text = preview.title,
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Bold,
                            maxLines = 3,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    TextButton(onClick = onClear) {
                        Text(stringResource(R.string.home_action_switch))
                    }
                }
                val playlistMetadata = if (preview.isPlaylist) {
                    preview.playlistItemCount?.let { count ->
                        pluralStringResource(R.plurals.home_preview_items, count, count)
                    } ?: stringResource(R.string.home_preview_playlist)
                } else {
                    null
                }
                val metadata = buildList {
                    preview.creator?.takeIf { it.isNotBlank() }?.let(::add)
                    preview.durationText?.takeIf { it.isNotBlank() }?.let(::add)
                    playlistMetadata?.let(::add)
                }
                if (metadata.isNotEmpty()) {
                    Text(
                        text = metadata.joinToString("  â€¢  "),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun AudioEffectsCard(
    state: HomeUiState,
    onAction: (MobileUiAction) -> Unit,
    previewPlayer: ExoPlayer?,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(18.dp)) {
            SectionTitle(
                title = stringResource(R.string.home_audio_title),
                supportingText = if (state.canTogglePreviewVideo) {
                    stringResource(R.string.home_audio_supporting_video)
                } else {
                    stringResource(R.string.home_audio_supporting_audio)
                },
                icon = Icons.Rounded.Tune,
            )

            EffectSlider(
                title = stringResource(R.string.home_audio_speed),
                valueText = formatSpeed(state.audioSpeed),
                value = state.audioSpeed,
                valueRange = 0.5f..2.0f,
                steps = 29,
                enabled = !state.audioPreviewActive,
                onValueChange = { onAction(MobileUiAction.SetAudioSpeed(it)) },
            )

            EffectSlider(
                title = stringResource(R.string.home_audio_pitch),
                valueText = formatSemitones(state.audioPitchSemitones),
                value = state.audioPitchSemitones,
                valueRange = -12f..12f,
                steps = 23,
                enabled = !state.audioPreviewActive,
                onValueChange = { onAction(MobileUiAction.SetAudioPitch(it)) },
            )

            EffectSlider(
                title = stringResource(R.string.home_audio_volume),
                valueText = formatVolume(state.audioVolumePercent),
                value = state.audioVolumePercent.toFloat(),
                valueRange = 5f..200f,
                steps = 38,
                enabled = !state.audioPreviewActive,
                onValueChange = { onAction(MobileUiAction.SetAudioVolume(it.toInt())) },
            )

            EffectToggle(
                title = stringResource(R.string.home_audio_bass),
                supportingText = stringResource(R.string.home_audio_bass_supporting),
                checked = state.audioBass,
                enabled = !state.audioPreviewActive,
                icon = Icons.Rounded.GraphicEq,
                onCheckedChange = { onAction(MobileUiAction.SetAudioBass(it)) },
            )

            EffectToggle(
                title = stringResource(R.string.home_audio_echo),
                supportingText = stringResource(R.string.home_audio_echo_supporting),
                checked = state.audioEcho,
                enabled = !state.audioPreviewActive,
                icon = Icons.Rounded.Repeat,
                onCheckedChange = { onAction(MobileUiAction.SetAudioEcho(it)) },
            )

            EffectToggle(
                title = stringResource(R.string.home_audio_tremolo),
                supportingText = stringResource(R.string.home_audio_tremolo_supporting),
                checked = state.audioTremolo,
                enabled = !state.audioPreviewActive,
                icon = Icons.Rounded.GraphicEq,
                onCheckedChange = { onAction(MobileUiAction.SetAudioTremolo(it)) },
            )

            EffectToggle(
                title = stringResource(R.string.home_audio_normalize),
                supportingText = stringResource(R.string.home_audio_normalize_supporting),
                checked = state.audioNormalize,
                enabled = !state.audioPreviewActive,
                icon = Icons.AutoMirrored.Rounded.VolumeUp,
                onCheckedChange = { onAction(MobileUiAction.SetAudioNormalize(it)) },
            )

            if (state.canTogglePreviewVideo) {
                PreviewVideoModeSelector(
                    usesVideo = state.previewUsesVideo,
                    enabled = !state.audioPreviewActive,
                    onSelect = { usesVideo ->
                        onAction(MobileUiAction.SelectPreviewUsesVideo(usesVideo))
                    },
                )
            }

            if (!state.audioEffectsDefault || !state.audioTrimDefault) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                ) {
                    TextButton(
                        onClick = { onAction(MobileUiAction.ResetAudioEffects) },
                    ) {
                        Icon(
                            imageVector = Icons.Rounded.Refresh,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp),
                        )
                        Spacer(Modifier.size(6.dp))
                        Text(stringResource(R.string.action_restore_default))
                    }
                }
            }

            when {
                state.isAudioPreviewRendering -> {
                    FilledTonalButton(
                        onClick = {},
                        enabled = false,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 50.dp),
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp,
                        )
                        Spacer(Modifier.size(8.dp))
                        Text(stringResource(R.string.home_audio_rendering_preview))
                    }
                }

                state.isAudioPreviewPlaying -> {
                    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        if (state.previewUsesVideo && state.canTogglePreviewVideo && previewPlayer != null) {
                            AndroidView(
                                factory = { context ->
                                    PlayerView(context).apply {
                                        useController = true
                                        player = previewPlayer
                                    }
                                },
                                update = { view ->
                                    view.player = previewPlayer
                                },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .aspectRatio(16f / 9f),
                            )
                        }
                        TextButton(
                            onClick = { onAction(MobileUiAction.StopAudioPreview) },
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 50.dp),
                        ) {
                            Icon(
                                imageVector = Icons.Rounded.Stop,
                                contentDescription = null,
                                modifier = Modifier.size(20.dp),
                            )
                            Spacer(Modifier.size(8.dp))
                            Text(stringResource(R.string.home_audio_stop_preview))
                        }
                    }
                }

                else -> {
                    FilledTonalButton(
                        onClick = { onAction(MobileUiAction.PreviewAudio) },
                        enabled = state.canPreviewAudio,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 50.dp),
                    ) {
                        Icon(
                            imageVector = Icons.Rounded.PlayArrow,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                        )
                        Spacer(Modifier.size(8.dp))
                        Text(
                            if (state.canTogglePreviewVideo && state.previewUsesVideo) {
                                stringResource(R.string.home_audio_preview)
                            } else {
                                stringResource(R.string.home_audio_preview_audio)
                            },
                        )
                    }
                }
            }

            state.audioPreviewError?.let { error ->
                InfoBanner(
                    text = error,
                    icon = Icons.Rounded.Info,
                    containerColor = MaterialTheme.colorScheme.errorContainer,
                    contentColor = MaterialTheme.colorScheme.onErrorContainer,
                )
            }
        }
    }
}

@Composable
private fun TrimAndFadeCard(
    state: HomeUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    val maxSeconds = (
        state.preview?.durationSeconds
            ?.takeIf { it >= MIN_SEGMENT_SECONDS }
            ?: MAX_TRIM_SLIDER_SECONDS
        ).coerceAtMost(MAX_TRIM_SLIDER_SECONDS)
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(18.dp)) {
            SectionTitle(
                title = stringResource(R.string.home_trim_title),
                supportingText = stringResource(R.string.home_trim_supporting),
                icon = Icons.Rounded.ContentCut,
            )

            EffectSlider(
                title = stringResource(R.string.home_trim_start),
                valueText = formatTrimSeconds(state.trimStartSeconds),
                value = state.trimStartSeconds.coerceIn(0f, maxSeconds),
                valueRange = 0f..maxSeconds,
                steps = 0,
                enabled = !state.audioPreviewActive,
                onValueChange = { onAction(MobileUiAction.SetTrimStartSeconds(it)) },
            )

            SwitchOption(
                title = stringResource(R.string.home_trim_until_end),
                supportingText = when (state.trimDurationSeconds) {
                    null -> stringResource(R.string.home_trim_until_end_supporting)
                    else -> stringResource(R.string.home_trim_duration_supporting)
                },
                checked = state.trimDurationSeconds == null,
                icon = Icons.Rounded.HighlightOff,
                onCheckedChange = { untilEnd ->
                    if (untilEnd) {
                        onAction(MobileUiAction.SetTrimDurationSeconds(null))
                    } else {
                        onAction(
                            MobileUiAction.SetTrimDurationSeconds(
                                state.trimDurationSeconds ?: DEFAULT_TRIM_DURATION,
                            ),
                        )
                    }
                },
            )

            state.trimDurationSeconds?.let { duration ->
                EffectSlider(
                    title = stringResource(R.string.home_trim_duration),
                    valueText = formatTrimSeconds(duration),
                    value = duration.coerceIn(MIN_SEGMENT_SECONDS, maxSeconds),
                    valueRange = MIN_SEGMENT_SECONDS..maxSeconds,
                    steps = 0,
                    enabled = !state.audioPreviewActive,
                    onValueChange = { onAction(MobileUiAction.SetTrimDurationSeconds(it)) },
                )
            }

            EffectSlider(
                title = stringResource(R.string.home_trim_fade_in),
                valueText = formatTrimSeconds(state.fadeInSeconds),
                value = state.fadeInSeconds.coerceIn(0f, MAX_FADE_SLIDER_SECONDS),
                valueRange = 0f..MAX_FADE_SLIDER_SECONDS,
                steps = 0,
                enabled = !state.audioPreviewActive,
                onValueChange = { onAction(MobileUiAction.SetFadeInSeconds(it)) },
            )

            EffectSlider(
                title = stringResource(R.string.home_trim_fade_out),
                valueText = formatTrimSeconds(state.fadeOutSeconds),
                value = state.fadeOutSeconds.coerceIn(0f, MAX_FADE_SLIDER_SECONDS),
                valueRange = 0f..MAX_FADE_SLIDER_SECONDS,
                steps = 0,
                enabled = !state.audioPreviewActive,
                onValueChange = { onAction(MobileUiAction.SetFadeOutSeconds(it)) },
            )
        }
    }
}

@Composable
private fun EffectSlider(
    title: String,
    valueText: String,
    value: Float,
    valueRange: ClosedFloatingPointRange<Float>,
    steps: Int,
    enabled: Boolean,
    onValueChange: (Float) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(title, style = MaterialTheme.typography.labelLarge)
            Text(
                text = valueText,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary,
            )
        }
        Slider(
            value = value,
            onValueChange = onValueChange,
            valueRange = valueRange,
            steps = steps,
            enabled = enabled,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
private fun PlaylistSelectionCard(
    state: HomeUiState,
    preview: MediaPreviewUi,
    onAction: (MobileUiAction) -> Unit,
) {
    if (!preview.isPlaylist || preview.playlistItems.isEmpty()) return
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            SectionTitle(
                title = stringResource(R.string.home_playlist_title),
                supportingText = stringResource(R.string.home_playlist_supporting),
                icon = Icons.AutoMirrored.Rounded.PlaylistPlay,
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                FilledTonalButton(
                    onClick = { onAction(MobileUiAction.SelectAllPlaylistItems(true)) },
                    enabled = state.playlistSelection.size < preview.playlistItems.size,
                    modifier = Modifier
                        .weight(1f)
                        .heightIn(min = 44.dp),
                ) {
                    Text(stringResource(R.string.home_playlist_select_all))
                }
                FilledTonalButton(
                    onClick = { onAction(MobileUiAction.SelectAllPlaylistItems(false)) },
                    enabled = state.playlistSelection.isNotEmpty(),
                    modifier = Modifier
                        .weight(1f)
                        .heightIn(min = 44.dp),
                ) {
                    Text(stringResource(R.string.home_playlist_clear_selection))
                }
            }

            LazyColumn(
                modifier = Modifier.heightIn(max = 320.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                items(preview.playlistItems, key = { "item-${it.index}" }) { item ->
                    val selected = item.index in state.playlistSelection
                    Surface(
                        modifier = Modifier
                            .fillMaxWidth()
                            .toggleable(
                                value = selected,
                                role = Role.Checkbox,
                                onValueChange = { onAction(MobileUiAction.TogglePlaylistItem(item.index)) },
                            ),
                        shape = MaterialTheme.shapes.medium,
                        color = if (selected) {
                            MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.5f)
                        } else {
                            MaterialTheme.colorScheme.surfaceContainer
                        },
                    ) {
                        Row(
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(20.dp)
                                    .clip(RoundedCornerShape(4.dp))
                                    .background(if (selected) {
                                        MaterialTheme.colorScheme.primary
                                    } else {
                                        Color.Transparent
                                    }),
                                contentAlignment = Alignment.Center,
                            ) {
                                if (selected) {
                                    Icon(
                                        imageVector = Icons.Rounded.Check,
                                        contentDescription = null,
                                        modifier = Modifier.size(16.dp),
                                        tint = MaterialTheme.colorScheme.onPrimary,
                                    )
                                }
                            }
                            Text(
                                text = item.index.toString(),
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.width(28.dp),
                            )
                            Text(
                                text = item.title,
                                style = MaterialTheme.typography.bodyMedium,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.weight(1f),
                            )
                        }
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun DownloadOptionsCard(
    state: HomeUiState,
    preview: MediaPreviewUi,
    onAction: (MobileUiAction) -> Unit,
) {
    val qualities = when (state.selectedKind) {
        MediaKind.VIDEO -> preview.videoQualities
        MediaKind.AUDIO -> preview.audioQualities
    }
    val formats = when (state.selectedKind) {
        MediaKind.VIDEO -> preview.videoFormats
        MediaKind.AUDIO -> preview.audioFormats
    }

    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(20.dp)) {
            SectionTitle(
                title = stringResource(R.string.home_options_title),
                supportingText = stringResource(R.string.home_options_supporting),
                icon = Icons.Rounded.Tune,
            )

            Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
                Text(
                    stringResource(R.string.home_options_media_type),
                    style = MaterialTheme.typography.labelLarge,
                )
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .selectableGroup(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    MediaKind.entries.forEach { kind ->
                        val enabled = when (kind) {
                            MediaKind.VIDEO -> preview.supportsVideo
                            MediaKind.AUDIO -> preview.supportsAudio
                        }
                        MediaKindOption(
                            kind = kind,
                            selected = state.selectedKind == kind,
                            enabled = enabled,
                            onClick = { onAction(MobileUiAction.SelectMediaKind(kind)) },
                            modifier = Modifier.weight(1f),
                        )
                    }
                }
            }

            ChoiceSelector(
                title = stringResource(R.string.home_options_quality),
                choices = qualities,
                selectedId = state.selectedQualityId,
                onSelect = { onAction(MobileUiAction.SelectQuality(it)) },
            )

            ChoiceSelector(
                title = stringResource(R.string.home_options_format),
                choices = formats,
                selectedId = state.selectedFormatId,
                onSelect = { onAction(MobileUiAction.SelectFormat(it)) },
            )

            if (preview.supportsSubtitles && state.selectedKind == MediaKind.VIDEO) {
                SwitchOption(
                    title = stringResource(R.string.home_options_subtitles),
                    supportingText = if (state.subtitleLanguages.isEmpty()) {
                        stringResource(R.string.home_options_subtitles_supporting)
                    } else {
                        pluralStringResource(
                            R.plurals.home_options_subtitles_languages,
                            state.subtitleLanguages.size,
                            state.subtitleLanguages.size,
                        )
                    },
                    checked = state.includeSubtitles,
                    icon = Icons.Rounded.ClosedCaption,
                    onCheckedChange = { onAction(MobileUiAction.SetIncludeSubtitles(it)) },
                )
                if (state.subtitleLanguages.isNotEmpty()) {
                    FlowRow(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        state.subtitleLanguages.forEach { language ->
                            FilterChip(
                                selected = language in state.selectedSubtitleLanguages,
                                onClick = { onAction(MobileUiAction.ToggleSubtitleLanguage(language)) },
                                label = { Text(language) },
                                leadingIcon = {
                                    Icon(
                                        imageVector = Icons.Rounded.ClosedCaption,
                                        contentDescription = null,
                                        modifier = Modifier.size(17.dp),
                                    )
                                },
                            )
                        }
                    }
                }
            }

            if (state.selectedKind == MediaKind.VIDEO) {
                SwitchOption(
                    title = stringResource(R.string.home_options_editor_compatible),
                    supportingText = stringResource(R.string.home_options_editor_compatible_supporting),
                    checked = state.editorCompatible,
                    icon = Icons.Rounded.Videocam,
                    onCheckedChange = { onAction(MobileUiAction.ToggleEditorCompatibility(it)) },
                )
            }

            if (state.embedMetadataSupported) {
                SwitchOption(
                    title = stringResource(R.string.home_options_metadata),
                    supportingText = stringResource(R.string.home_options_metadata_supporting),
                    checked = state.embedMetadata,
                    icon = Icons.AutoMirrored.Rounded.Label,
                    onCheckedChange = { onAction(MobileUiAction.SetEmbedMetadata(it)) },
                )
            }

            if (state.selectedKind == MediaKind.AUDIO) {
                SwitchOption(
                    title = stringResource(R.string.home_options_thumbnail),
                    supportingText = stringResource(R.string.home_options_thumbnail_supporting),
                    checked = state.embedThumbnail,
                    icon = Icons.Rounded.Image,
                    onCheckedChange = { onAction(MobileUiAction.SetEmbedThumbnail(it)) },
                )
            }

            OutlinedTextField(
                value = state.itemRateLimitText,
                onValueChange = { onAction(MobileUiAction.SetItemRateLimitText(it)) },
                modifier = Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.home_options_rate_limit_label)) },
                placeholder = { Text(stringResource(R.string.home_options_rate_limit_placeholder)) },
                supportingText = {
                    Text(stringResource(R.string.home_options_rate_limit_supporting))
                },
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Number,
                    imeAction = ImeAction.Next,
                ),
                singleLine = true,
                shape = MaterialTheme.shapes.medium,
            )
        }
    }
}

@Composable
private fun MediaKindOption(
    kind: MediaKind,
    selected: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val container = if (selected) {
        MaterialTheme.colorScheme.primaryContainer
    } else {
        MaterialTheme.colorScheme.surfaceContainer
    }
    val content = if (selected) {
        MaterialTheme.colorScheme.onPrimaryContainer
    } else {
        MaterialTheme.colorScheme.onSurface
    }
    Surface(
        modifier = modifier
            .alpha(if (enabled) 1f else 0.45f)
            .selectable(
                selected = selected,
                enabled = enabled,
                role = Role.RadioButton,
                onClick = onClick,
            ),
        color = container,
        contentColor = content,
        shape = MaterialTheme.shapes.medium,
        border = BorderStroke(
            1.dp,
            if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant,
        ),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 76.dp)
                .padding(horizontal = 12.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = kind.icon,
                contentDescription = null,
                modifier = Modifier.size(24.dp),
            )
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = stringResource(kind.labelRes),
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = stringResource(kind.supportingTextRes),
                    style = MaterialTheme.typography.labelSmall,
                    color = content.copy(alpha = 0.76f),
                )
            }
        }
    }
}

@Composable
private fun PreviewVideoModeSelector(
    usesVideo: Boolean,
    enabled: Boolean,
    onSelect: (Boolean) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
        Text(stringResource(R.string.home_preview_content), style = MaterialTheme.typography.labelLarge)
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .selectableGroup(),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            PreviewVideoModeOption(
                label = stringResource(R.string.home_preview_with_video),
                supportingText = stringResource(R.string.home_preview_with_video_supporting),
                icon = Icons.Rounded.Videocam,
                selected = usesVideo,
                enabled = enabled,
                onClick = { onSelect(true) },
                modifier = Modifier.weight(1f),
            )
            PreviewVideoModeOption(
                label = stringResource(R.string.home_preview_audio_only),
                supportingText = stringResource(R.string.home_preview_audio_only_supporting),
                icon = Icons.Rounded.Headphones,
                selected = !usesVideo,
                enabled = enabled,
                onClick = { onSelect(false) },
                modifier = Modifier.weight(1f),
            )
        }
    }
}

@Composable
private fun PreviewVideoModeOption(
    label: String,
    supportingText: String,
    icon: ImageVector,
    selected: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val container = if (selected) {
        MaterialTheme.colorScheme.primaryContainer
    } else {
        MaterialTheme.colorScheme.surfaceContainer
    }
    val content = if (selected) {
        MaterialTheme.colorScheme.onPrimaryContainer
    } else {
        MaterialTheme.colorScheme.onSurface
    }
    Surface(
        modifier = modifier
            .alpha(if (enabled) 1f else 0.45f)
            .selectable(
                selected = selected,
                enabled = enabled,
                role = Role.RadioButton,
                onClick = onClick,
            ),
        color = container,
        contentColor = content,
        shape = MaterialTheme.shapes.medium,
        border = BorderStroke(
            1.dp,
            if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant,
        ),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 72.dp)
                .padding(horizontal = 12.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                modifier = Modifier.size(22.dp),
            )
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = label,
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = supportingText,
                    style = MaterialTheme.typography.labelSmall,
                    color = content.copy(alpha = 0.76f),
                )
            }
        }
    }
}

@Composable
private fun ChoiceSelector(
    title: String,
    choices: List<ChoiceUi>,
    selectedId: String?,
    onSelect: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
        Text(title, style = MaterialTheme.typography.labelLarge)
        if (choices.isEmpty()) {
            Text(
                text = stringResource(R.string.home_options_no_choices),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(choices, key = { it.id }) { choice ->
                    ElevatedFilterChip(
                        selected = selectedId == choice.id,
                        onClick = { onSelect(choice.id) },
                        leadingIcon = if (choice.recommended) {
                            {
                                Icon(
                                    imageVector = Icons.Rounded.Star,
                                    contentDescription = null,
                                    modifier = Modifier.size(17.dp),
                                )
                            }
                        } else {
                            null
                        },
                        label = {
                            Text(
                                if (choice.recommended) {
                                    stringResource(R.string.home_options_recommended, choice.label)
                                } else {
                                    choice.label
                                },
                            )
                        },
                    )
                }
            }
            choices.firstOrNull { it.id == selectedId }?.description?.let { description ->
                InfoBanner(
                    text = description,
                    icon = Icons.Rounded.Info,
                    containerColor = MaterialTheme.colorScheme.surfaceContainer,
                    contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun EffectToggle(
    title: String,
    supportingText: String,
    checked: Boolean,
    enabled: Boolean,
    icon: ImageVector,
    onCheckedChange: (Boolean) -> Unit,
) {
    Surface(
        modifier = Modifier.toggleable(
            value = checked,
            enabled = enabled,
            role = Role.Switch,
            onValueChange = onCheckedChange,
        ),
        shape = MaterialTheme.shapes.medium,
        color = if (checked) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surfaceContainer,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = if (enabled) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(23.dp),
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = supportingText,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Switch(
                checked = checked,
                enabled = enabled,
                onCheckedChange = null,
            )
        }
    }
}

@Composable
private fun SwitchOption(
    title: String,
    supportingText: String?,
    checked: Boolean,
    icon: ImageVector,
    onCheckedChange: (Boolean) -> Unit,
) {
    Surface(
        modifier = Modifier.toggleable(
            value = checked,
            role = Role.Switch,
            onValueChange = onCheckedChange,
        ),
        shape = MaterialTheme.shapes.medium,
        color = MaterialTheme.colorScheme.surfaceContainer,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(23.dp),
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                if (supportingText != null) {
                    Text(
                        text = supportingText,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Switch(checked = checked, onCheckedChange = null)
        }
    }
}

@Composable
private fun formatSpeed(value: Float): String {
    val text = String.format(Locale.US, "%.2f", value)
        .trimEnd('0')
        .trimEnd('.')
        .replace('.', ',')
    return stringResource(R.string.home_audio_speed_value, text)
}

@Composable
private fun formatSemitones(value: Float): String =
    if (value == 0f) {
        stringResource(R.string.home_audio_pitch_normal)
    } else {
        val signed = String.format(Locale.US, "%+.0f", value)
        pluralStringResource(
            R.plurals.home_audio_semitones,
            abs(value.toInt()),
            signed,
        )
    }

@Composable
private fun formatVolume(percent: Int): String =
    stringResource(R.string.home_audio_volume_value, percent)

@Composable
private fun formatTrimSeconds(value: Float): String {
    val seconds = when {
        value <= 0.05f -> "0"
        value < 10f -> String.format(Locale.US, "%.1f", value).replace('.', ',')
        else -> String.format(Locale.US, "%.0f", value).replace('.', ',')
    }
    return stringResource(R.string.home_seconds_value, seconds)
}

private const val MIN_SEGMENT_SECONDS = 1f
private const val MAX_TRIM_SLIDER_SECONDS = 600f
private const val MAX_FADE_SLIDER_SECONDS = 30f
private const val DEFAULT_TRIM_DURATION = 5f

private val MediaKind.icon: ImageVector
    get() = when (this) {
        MediaKind.VIDEO -> Icons.Rounded.Videocam
        MediaKind.AUDIO -> Icons.Rounded.Headphones
    }
