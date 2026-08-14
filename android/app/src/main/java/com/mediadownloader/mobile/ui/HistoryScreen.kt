package com.mediadownloader.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.DeleteSweep
import androidx.compose.material.icons.rounded.FolderOpen
import androidx.compose.material.icons.rounded.History
import androidx.compose.material.icons.rounded.Inventory2
import androidx.compose.material.icons.rounded.OpenInNew
import androidx.compose.material.icons.rounded.Share
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
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
import androidx.compose.ui.text.style.TextAlign
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
            icon = {
                Icon(
                    imageVector = Icons.Rounded.DeleteSweep,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.error,
                )
            },
            title = { Text("Limpar histórico?", fontWeight = FontWeight.Bold) },
            text = {
                Text("Os registros serão removidos, mas os arquivos baixados continuarão no aparelho.")
            },
            confirmButton = {
                Button(
                    onClick = {
                        showClearConfirmation = false
                        onAction(MobileUiAction.ClearHistory)
                    },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error,
                        contentColor = MaterialTheme.colorScheme.onError,
                    ),
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
            contentPadding = PaddingValues(horizontal = 20.dp, vertical = 24.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item {
                ScreenHeading(
                    eyebrow = "Sua biblioteca",
                    title = "Histórico",
                    supportingText = "Encontre, abra e compartilhe tudo o que já foi concluído.",
                    icon = Icons.Rounded.History,
                )
            }

            if (state.items.isEmpty()) {
                item {
                    EmptyState(
                        icon = Icons.Rounded.FolderOpen,
                        title = "Sua biblioteca está pronta",
                        supportingText = "Quando um download for concluído, o arquivo ficará organizado aqui.",
                    )
                }
            } else {
                item {
                    InfoBanner(
                        text = "${state.items.size} ${if (state.items.size == 1) "arquivo disponível" else "arquivos disponíveis"} neste aparelho.",
                        icon = Icons.Rounded.Inventory2,
                        containerColor = MaterialTheme.colorScheme.tertiaryContainer,
                        contentColor = MaterialTheme.colorScheme.onTertiaryContainer,
                    )
                }
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
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 50.dp),
                        colors = ButtonDefaults.outlinedButtonColors(
                            contentColor = MaterialTheme.colorScheme.error,
                        ),
                    ) {
                        Icon(
                            imageVector = Icons.Rounded.DeleteSweep,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                        )
                        Text("Limpar histórico", modifier = Modifier.padding(start = 9.dp))
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
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(13.dp),
                verticalAlignment = Alignment.Top,
            ) {
                thumbnail(
                    item.thumbnailUrl,
                    "Miniatura de ${item.title}",
                    Modifier
                        .width(112.dp)
                        .aspectRatio(16f / 9f),
                )
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    StatusPill(
                        label = "Concluído",
                        containerColor = MaterialTheme.colorScheme.tertiaryContainer,
                        contentColor = MaterialTheme.colorScheme.onTertiaryContainer,
                        icon = Icons.Rounded.CheckCircle,
                    )
                    Text(
                        text = item.title,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
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
                }
            }

            Text(
                text = listOfNotNull(item.completedAtText, item.fileSizeText)
                    .joinToString("  •  "),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End),
            ) {
                TextButton(
                    onClick = { onAction(MobileUiAction.ShareHistoryItem(item.id)) },
                    enabled = item.canShare,
                    modifier = Modifier.weight(1.35f),
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 6.dp),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.Share,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                    Text(
                        "Compartilhar",
                        modifier = Modifier.padding(start = 7.dp),
                        maxLines = 2,
                        textAlign = TextAlign.Center,
                    )
                }
                FilledTonalButton(
                    onClick = { onAction(MobileUiAction.OpenHistoryItem(item.id)) },
                    enabled = item.canOpen,
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.OpenInNew,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                    Text("Abrir", modifier = Modifier.padding(start = 7.dp))
                }
            }
        }
    }
}
