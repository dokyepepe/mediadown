package com.mediadownloader.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

@Composable
fun DownloadsScreen(
    state: DownloadsUiState,
    onAction: (MobileUiAction) -> Unit,
    thumbnail: ThumbnailRenderer,
    modifier: Modifier = Modifier,
) {
    val visibleItems = state.items.filter { item ->
        when (state.selectedFilter) {
            DownloadFilter.ALL -> true
            DownloadFilter.ACTIVE -> item.status.isActive
            DownloadFilter.COMPLETED -> item.status == DownloadStatus.COMPLETED
            DownloadFilter.FAILED -> item.status == DownloadStatus.FAILED ||
                item.status == DownloadStatus.CANCELLED
        }
    }
    val activeCount = state.items.count { it.status.isActive }
    val hasFinishedItems = state.items.any { !it.status.isActive }

    ScreenContainer(modifier) {
        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                ScreenHeading(
                    title = "Downloads",
                    supportingText = when (activeCount) {
                        0 -> "Acompanhe sua fila e os arquivos concluídos."
                        1 -> "1 download em andamento."
                        else -> "$activeCount downloads em andamento."
                    },
                )
            }

            item {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(DownloadFilter.entries, key = { it.name }) { filter ->
                        val count = state.items.countFor(filter)
                        FilterChip(
                            selected = state.selectedFilter == filter,
                            onClick = { onAction(MobileUiAction.SelectDownloadFilter(filter)) },
                            label = { Text("${filter.label} ($count)") },
                        )
                    }
                }
            }

            if (visibleItems.isEmpty()) {
                item {
                    EmptyState(
                        glyph = "⇩",
                        title = if (state.items.isEmpty()) "Sua fila está vazia" else "Nada neste filtro",
                        supportingText = if (state.items.isEmpty()) {
                            "Os downloads adicionados na tela Início aparecerão aqui."
                        } else {
                            "Selecione outro filtro para ver seus downloads."
                        },
                    )
                }
            } else {
                items(visibleItems, key = { it.id }) { item ->
                    DownloadCard(
                        item = item,
                        onAction = onAction,
                        thumbnail = thumbnail,
                    )
                }
            }

            if (hasFinishedItems) {
                item {
                    OutlinedButton(
                        onClick = { onAction(MobileUiAction.ClearFinishedDownloads) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Remover itens finalizados")
                    }
                }
            }
        }
    }
}

@Composable
private fun DownloadCard(
    item: DownloadItemUi,
    onAction: (MobileUiAction) -> Unit,
    thumbnail: ThumbnailRenderer,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.Top,
            ) {
                thumbnail(
                    item.thumbnailUrl,
                    "Miniatura de ${item.title}",
                    Modifier
                        .width(108.dp)
                        .aspectRatio(16f / 9f),
                )
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Text(
                        text = item.title,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        text = item.detail,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    DownloadStatusPill(item.status)
                }
            }

            if (item.status.isActive) {
                if (item.progress != null) {
                    LinearProgressIndicator(
                        progress = { item.progress.coerceIn(0f, 1f) },
                        modifier = Modifier.fillMaxWidth(),
                    )
                } else {
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Text(
                        text = item.progressText ?: item.status.label,
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Medium,
                    )
                    val transferDetails = listOfNotNull(item.speedText, item.etaText).joinToString(" • ")
                    if (transferDetails.isNotEmpty()) {
                        Text(
                            text = transferDetails,
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            item.errorMessage?.let { error ->
                Text(
                    text = error,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }

            DownloadActions(item = item, onAction = onAction)
        }
    }
}

@Composable
private fun DownloadActions(
    item: DownloadItemUi,
    onAction: (MobileUiAction) -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.End,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        when (item.status) {
            DownloadStatus.QUEUED,
            DownloadStatus.PREPARING,
            DownloadStatus.DOWNLOADING,
            DownloadStatus.PROCESSING -> TextButton(onClick = {
                onAction(MobileUiAction.CancelDownload(item.id))
            }) {
                Text("Cancelar")
            }

            DownloadStatus.FAILED,
            DownloadStatus.CANCELLED -> {
                TextButton(onClick = { onAction(MobileUiAction.RemoveDownload(item.id)) }) {
                    Text("Remover")
                }
                Button(onClick = { onAction(MobileUiAction.RetryDownload(item.id)) }) {
                    Text("Tentar novamente")
                }
            }

            DownloadStatus.COMPLETED -> {
                TextButton(onClick = { onAction(MobileUiAction.RemoveDownload(item.id)) }) {
                    Text("Remover")
                }
                Button(
                    onClick = { onAction(MobileUiAction.OpenDownload(item.id)) },
                    enabled = item.canOpen,
                ) {
                    Text("Abrir")
                }
            }
        }
    }
}

@Composable
private fun DownloadStatusPill(status: DownloadStatus) {
    val (container, content) = when (status) {
        DownloadStatus.QUEUED -> MaterialTheme.colorScheme.secondaryContainer to
            MaterialTheme.colorScheme.onSecondaryContainer
        DownloadStatus.PREPARING,
        DownloadStatus.DOWNLOADING,
        DownloadStatus.PROCESSING -> MaterialTheme.colorScheme.primaryContainer to
            MaterialTheme.colorScheme.onPrimaryContainer
        DownloadStatus.COMPLETED -> Color(0xFFD8F7DF) to Color(0xFF145C2B)
        DownloadStatus.FAILED -> MaterialTheme.colorScheme.errorContainer to
            MaterialTheme.colorScheme.onErrorContainer
        DownloadStatus.CANCELLED -> MaterialTheme.colorScheme.surfaceVariant to
            MaterialTheme.colorScheme.onSurfaceVariant
    }
    StatusPill(
        label = status.label,
        containerColor = container,
        contentColor = content,
    )
}

private val DownloadStatus.isActive: Boolean
    get() = this == DownloadStatus.QUEUED ||
        this == DownloadStatus.PREPARING ||
        this == DownloadStatus.DOWNLOADING ||
        this == DownloadStatus.PROCESSING

private fun List<DownloadItemUi>.countFor(filter: DownloadFilter): Int = count { item ->
    when (filter) {
        DownloadFilter.ALL -> true
        DownloadFilter.ACTIVE -> item.status.isActive
        DownloadFilter.COMPLETED -> item.status == DownloadStatus.COMPLETED
        DownloadFilter.FAILED -> item.status == DownloadStatus.FAILED ||
            item.status == DownloadStatus.CANCELLED
    }
}
