package com.mediadownloader.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

@Composable
fun HistoryScreen(
    state: HistoryUiState,
    onAction: (MobileUiAction) -> Unit,
    thumbnail: ThumbnailRenderer,
    modifier: Modifier = Modifier,
) {
    var showClearConfirmation by rememberSaveable { mutableStateOf(false) }

    if (showClearConfirmation) {
        AlertDialog(
            onDismissRequest = { showClearConfirmation = false },
            title = { Text("Limpar histórico?") },
            text = {
                Text("Os registros serão removidos, mas os arquivos baixados continuarão no aparelho.")
            },
            confirmButton = {
                Button(
                    onClick = {
                        showClearConfirmation = false
                        onAction(MobileUiAction.ClearHistory)
                    },
                ) {
                    Text("Limpar")
                }
            },
            dismissButton = {
                TextButton(onClick = { showClearConfirmation = false }) {
                    Text("Cancelar")
                }
            },
        )
    }

    ScreenContainer(modifier) {
        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                ScreenHeading(
                    title = "Histórico",
                    supportingText = "Abra ou compartilhe os arquivos que você já baixou.",
                )
            }

            if (state.items.isEmpty()) {
                item {
                    EmptyState(
                        glyph = "↶",
                        title = "Nenhum download concluído",
                        supportingText = "Depois de concluir um download, ele ficará registrado aqui.",
                    )
                }
            } else {
                items(state.items, key = { it.id }) { item ->
                    HistoryCard(
                        item = item,
                        onAction = onAction,
                        thumbnail = thumbnail,
                    )
                }
                item {
                    OutlinedButton(
                        onClick = { showClearConfirmation = true },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Limpar histórico")
                    }
                }
            }
        }
    }
}

@Composable
private fun HistoryCard(
    item: HistoryItemUi,
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
                    verticalArrangement = Arrangement.spacedBy(5.dp),
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
                    Text(
                        text = listOfNotNull(item.completedAtText, item.fileSizeText)
                            .joinToString(" • "),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
            ) {
                TextButton(
                    onClick = { onAction(MobileUiAction.ShareHistoryItem(item.id)) },
                    enabled = item.canShare,
                ) {
                    Text("Compartilhar")
                }
                Button(
                    onClick = { onAction(MobileUiAction.OpenHistoryItem(item.id)) },
                    enabled = item.canOpen,
                ) {
                    Text("Abrir")
                }
            }
        }
    }
}
