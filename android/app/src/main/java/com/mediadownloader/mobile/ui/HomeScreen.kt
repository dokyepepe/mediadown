package com.mediadownloader.mobile.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.CloudDownload
import androidx.compose.material.icons.rounded.ClosedCaption
import androidx.compose.material.icons.rounded.ContentPaste
import androidx.compose.material.icons.rounded.Headphones
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.Link
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material.icons.rounded.PlaylistPlay
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Star
import androidx.compose.material.icons.rounded.Stop
import androidx.compose.material.icons.rounded.Tune
import androidx.compose.material.icons.rounded.Videocam
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ElevatedFilterChip
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import java.util.Locale

@Composable
fun HomeScreen(
    state: HomeUiState,
    onAction: (MobileUiAction) -> Unit,
    thumbnail: ThumbnailRenderer,
    previewPlayer: ExoPlayer? = null,
    modifier: Modifier = Modifier,
) {
    ScreenContainer(modifier) {
        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 20.dp, vertical = 24.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            item {
                ScreenHeading(
                    eyebrow = "Novo download",
                    title = "Baixe sua mídia",
                    supportingText = "Cole um link, confira a prévia e escolha exatamente como salvar.",
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

            state.preview?.let { preview ->
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
                    DownloadOptionsCard(
                        state = state,
                        preview = preview,
                        onAction = onAction,
                    )
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
                            Text("Adicionando à fila…")
                        } else {
                            Icon(
                                imageVector = Icons.Rounded.CloudDownload,
                                contentDescription = null,
                                modifier = Modifier.size(21.dp),
                            )
                            Spacer(Modifier.size(9.dp))
                            Text(
                                if (preview.isPlaylist && state.downloadPlaylist) {
                                    "Baixar playlist"
                                } else {
                                    "Baixar agora"
                                },
                            )
                        }
                    }
                }
            } ?: item {
                InfoBanner(
                    text = "Seus links e downloads permanecem neste aparelho — sem conta e sem telemetria.",
                    icon = Icons.Rounded.Lock,
                    containerColor = MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.72f),
                    contentColor = MaterialTheme.colorScheme.onTertiaryContainer,
                )
            }

            item { Spacer(Modifier.height(4.dp)) }
        }
    }
}

@Composable
private fun UrlInputCard(
    state: HomeUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            SectionTitle(
                title = "Link da mídia",
                supportingText = "Links recebidos pelo menu Compartilhar aparecem aqui.",
                icon = Icons.Rounded.Link,
            )
            OutlinedTextField(
                value = state.url,
                onValueChange = { onAction(MobileUiAction.UrlChanged(it)) },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("URL do vídeo, áudio ou playlist") },
                placeholder = { Text("https://…") },
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
                    Text("Colar")
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
                        Text("Analisando…")
                    } else {
                        Icon(
                            imageVector = Icons.Rounded.Search,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                        )
                        Spacer(Modifier.size(8.dp))
                        Text("Analisar")
                    }
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
                            text = "PRÉVIA ENCONTRADA",
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
                        Text("Trocar")
                    }
                }
                val metadata = buildList {
                    preview.creator?.takeIf { it.isNotBlank() }?.let(::add)
                    preview.durationText?.takeIf { it.isNotBlank() }?.let(::add)
                    if (preview.isPlaylist) {
                        add(
                            preview.playlistItemCount?.let { count ->
                                "$count ${if (count == 1) "item" else "itens"}"
                            } ?: "Playlist",
                        )
                    }
                }
                if (metadata.isNotEmpty()) {
                    Text(
                        text = metadata.joinToString("  •  "),
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
                title = "Ouça com efeitos",
                supportingText = if (state.canTogglePreviewVideo) {
                    "Ajuste tom, velocidade e volume, e toque as prévias antes de baixar."
                } else {
                    "Ajuste tom, velocidade e volume, e toque até 30 s antes de baixar."
                },
                icon = Icons.Rounded.Tune,
            )

            EffectSlider(
                title = "Velocidade",
                valueText = formatSpeed(state.audioSpeed),
                value = state.audioSpeed,
                valueRange = 0.5f..2.0f,
                steps = 29,
                enabled = !state.audioPreviewActive,
                onValueChange = { onAction(MobileUiAction.SetAudioSpeed(it)) },
            )

            EffectSlider(
                title = "Tom",
                valueText = formatSemitones(state.audioPitchSemitones),
                value = state.audioPitchSemitones,
                valueRange = -12f..12f,
                steps = 23,
                enabled = !state.audioPreviewActive,
                onValueChange = { onAction(MobileUiAction.SetAudioPitch(it)) },
            )

            EffectSlider(
                title = "Volume",
                valueText = formatVolume(state.audioVolumePercent),
                value = state.audioVolumePercent.toFloat(),
                valueRange = 5f..200f,
                steps = 38,
                enabled = !state.audioPreviewActive,
                onValueChange = { onAction(MobileUiAction.SetAudioVolume(it.toInt())) },
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

            if (!state.audioEffectsDefault) {
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
                        Text("Restaurar padrão")
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
                        Text("Gerando prévia…")
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
                            Text("Parar prévia")
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
                                "Pré-visualizar"
                            } else {
                                "Pré-visualizar áudio"
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
                title = "Personalize o arquivo",
                supportingText = "Escolha tipo, qualidade e formato antes de baixar.",
                icon = Icons.Rounded.Tune,
            )

            Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
                Text("Tipo de mídia", style = MaterialTheme.typography.labelLarge)
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
                title = "Qualidade",
                choices = qualities,
                selectedId = state.selectedQualityId,
                onSelect = { onAction(MobileUiAction.SelectQuality(it)) },
            )

            ChoiceSelector(
                title = "Formato",
                choices = formats,
                selectedId = state.selectedFormatId,
                onSelect = { onAction(MobileUiAction.SelectFormat(it)) },
            )

            if (preview.isPlaylist) {
                SwitchOption(
                    title = "Baixar a playlist inteira",
                    supportingText = preview.playlistItemCount?.let { "$it itens encontrados" },
                    checked = state.downloadPlaylist,
                    icon = Icons.Rounded.PlaylistPlay,
                    onCheckedChange = { onAction(MobileUiAction.SetDownloadPlaylist(it)) },
                )
            }

            if (preview.supportsSubtitles && state.selectedKind == MediaKind.VIDEO) {
                SwitchOption(
                    title = "Incluir legendas",
                    supportingText = "Quando disponíveis no idioma original",
                    checked = state.includeSubtitles,
                    icon = Icons.Rounded.ClosedCaption,
                    onCheckedChange = { onAction(MobileUiAction.SetIncludeSubtitles(it)) },
                )
            }
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
                    text = kind.label,
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = kind.supportingText,
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
        Text("Conteúdo da prévia", style = MaterialTheme.typography.labelLarge)
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .selectableGroup(),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            PreviewVideoModeOption(
                label = "Com vídeo",
                supportingText = "Trecho curto com imagem",
                icon = Icons.Rounded.Videocam,
                selected = usesVideo,
                enabled = enabled,
                onClick = { onSelect(true) },
                modifier = Modifier.weight(1f),
            )
            PreviewVideoModeOption(
                label = "Somente áudio",
                supportingText = "Uma captura do som",
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
                text = "Nenhuma opção disponível.",
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
                                    "${choice.label} · recomendado"
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

private fun formatSpeed(value: Float): String {
    val text = String.format(Locale.US, "%.2f", value)
        .trimEnd('0')
        .trimEnd('.')
        .replace('.', ',')
    return "${text}x"
}

private fun formatSemitones(value: Float): String =
    if (value == 0f) {
        "0 st (normal)"
    } else {
        String.format(Locale.US, "%+.0f st", value)
    }

private fun formatVolume(percent: Int): String = "$percent%"

private val MediaKind.icon: ImageVector
    get() = when (this) {
        MediaKind.VIDEO -> Icons.Rounded.Videocam
        MediaKind.AUDIO -> Icons.Rounded.Headphones
    }
