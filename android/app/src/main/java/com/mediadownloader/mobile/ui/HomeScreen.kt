package com.mediadownloader.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

@Composable
fun HomeScreen(
    state: HomeUiState,
    onAction: (MobileUiAction) -> Unit,
    thumbnail: ThumbnailRenderer,
    modifier: Modifier = Modifier,
) {
    ScreenContainer(modifier) {
        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item {
                ScreenHeading(
                    title = "Baixe sua mídia",
                    supportingText = "Cole um link para analisar os formatos disponíveis.",
                )
            }

            item {
                UrlInputCard(state = state, onAction = onAction)
            }

            state.analysisHint?.let { hint ->
                item {
                    Text(
                        text = hint,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
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
                            .height(52.dp),
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
                            Text(if (preview.isPlaylist && state.downloadPlaylist) "Baixar playlist" else "Baixar agora")
                        }
                    }
                }
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
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            SectionTitle(
                title = "Link da mídia",
                supportingText = "Links recebidos pelo menu Compartilhar aparecem aqui.",
            )
            OutlinedTextField(
                value = state.url,
                onValueChange = { onAction(MobileUiAction.UrlChanged(it)) },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("URL") },
                placeholder = { Text("https://…") },
                supportingText = state.urlError?.let { error ->
                    { Text(error) }
                },
                isError = state.urlError != null,
                enabled = !state.isAnalyzing && !state.isStartingDownload,
                minLines = 1,
                maxLines = 3,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Uri,
                    imeAction = ImeAction.Done,
                ),
                keyboardActions = KeyboardActions(
                    onDone = {
                        if (state.canAnalyze) onAction(MobileUiAction.AnalyzeUrl)
                    },
                ),
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                OutlinedButton(
                    onClick = { onAction(MobileUiAction.PasteUrl) },
                    enabled = state.canPaste && !state.isAnalyzing,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Colar")
                }
                Button(
                    onClick = { onAction(MobileUiAction.AnalyzeUrl) },
                    enabled = state.canAnalyze,
                    modifier = Modifier.weight(1.35f),
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
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                SectionTitle(
                    title = "Prévia",
                    supportingText = preview.sourceName,
                    modifier = Modifier.weight(1f),
                )
                OutlinedButton(onClick = onClear) {
                    Text("Trocar")
                }
            }
            thumbnail(
                preview.thumbnailUrl,
                "Miniatura de ${preview.title}",
                Modifier
                    .fillMaxWidth()
                    .aspectRatio(16f / 9f),
            )
            Text(
                text = preview.title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis,
            )
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
                    text = metadata.joinToString(" • "),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
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
        Column(verticalArrangement = Arrangement.spacedBy(18.dp)) {
            SectionTitle(
                title = "Opções do download",
                supportingText = "Escolha o tipo, a qualidade e o formato.",
            )

            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Tipo", style = MaterialTheme.typography.labelLarge)
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    MediaKind.entries.forEach { kind ->
                        val enabled = when (kind) {
                            MediaKind.VIDEO -> preview.supportsVideo
                            MediaKind.AUDIO -> preview.supportsAudio
                        }
                        FilterChip(
                            selected = state.selectedKind == kind,
                            onClick = { onAction(MobileUiAction.SelectMediaKind(kind)) },
                            enabled = enabled,
                            label = {
                                Column {
                                    Text(kind.label, fontWeight = FontWeight.SemiBold)
                                    Text(kind.supportingText, style = MaterialTheme.typography.labelSmall)
                                }
                            },
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
                    onCheckedChange = { onAction(MobileUiAction.SetDownloadPlaylist(it)) },
                )
            }

            if (preview.supportsSubtitles && state.selectedKind == MediaKind.VIDEO) {
                SwitchOption(
                    title = "Incluir legendas",
                    supportingText = "Quando disponíveis no idioma original",
                    checked = state.includeSubtitles,
                    onCheckedChange = { onAction(MobileUiAction.SetIncludeSubtitles(it)) },
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
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
                    FilterChip(
                        selected = selectedId == choice.id,
                        onClick = { onSelect(choice.id) },
                        label = {
                            Text(
                                if (choice.recommended) "${choice.label} · recomendado" else choice.label,
                            )
                        },
                    )
                }
            }
            choices.firstOrNull { it.id == selectedId }?.description?.let { description ->
                Text(
                    text = description,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
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
    onCheckedChange: (Boolean) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .semantics(mergeDescendants = true) { },
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            Text(text = title, style = MaterialTheme.typography.bodyLarge)
            if (supportingText != null) {
                Text(
                    text = supportingText,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}
