package com.mediadownloader.mobile.ui

import androidx.compose.foundation.combinedClickable
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
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Delete
import androidx.compose.material.icons.rounded.DeleteSweep
import androidx.compose.material.icons.rounded.DoneAll
import androidx.compose.material.icons.rounded.Edit
import androidx.compose.material.icons.rounded.FileUpload
import androidx.compose.material.icons.rounded.FolderOpen
import androidx.compose.material.icons.rounded.History
import androidx.compose.material.icons.rounded.Inventory2
import androidx.compose.material.icons.automirrored.rounded.OpenInNew
import androidx.compose.material.icons.automirrored.rounded.Redo
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Share
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.mediadownloader.mobile.R

@Composable
fun HistoryScreen(
    state: HistoryUiState,
    onAction: (MobileUiAction) -> Unit,
    thumbnail: ThumbnailRenderer,
    modifier: Modifier = Modifier,
) {
    var showClearConfirmation by rememberSaveable { mutableStateOf(false) }
    var renameTarget by rememberSaveable { mutableStateOf<String?>(null) }
    var renameValue by rememberSaveable { mutableStateOf("") }
    var confirmDeleteSelection by rememberSaveable { mutableStateOf(false) }

    val selectedIds = state.selectedIds
    val selectionMode = selectedIds.isNotEmpty()

    val query = state.searchQuery.trim().lowercase()
    val visibleItems = if (query.isEmpty()) {
        state.items
    } else {
        state.items.filter { item ->
            item.title.contains(query, ignoreCase = true) ||
                item.detail.contains(query, ignoreCase = true)
        }
    }

    if (confirmDeleteSelection) {
        AlertDialog(
            onDismissRequest = { confirmDeleteSelection = false },
            icon = {
                Icon(
                    imageVector = Icons.Rounded.Delete,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.error,
                )
            },
            title = {
                Text(
                    pluralStringResource(
                        R.plurals.history_delete_selection_title,
                        selectedIds.size,
                        selectedIds.size,
                    ),
                    fontWeight = FontWeight.Bold,
                )
            },
            text = { Text(stringResource(R.string.history_delete_selection_message)) },
            confirmButton = {
                Button(
                    onClick = {
                        confirmDeleteSelection = false
                        onAction(MobileUiAction.DeleteSelectedHistoryItems)
                    },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error,
                        contentColor = MaterialTheme.colorScheme.onError,
                    ),
                ) {
                    Text(stringResource(R.string.history_delete_selection_confirm))
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmDeleteSelection = false }) {
                    Text(stringResource(R.string.action_cancel))
                }
            },
        )
    }

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
            title = {
                Text(
                    stringResource(R.string.history_clear_title),
                    fontWeight = FontWeight.Bold,
                )
            },
            text = {
                Text(stringResource(R.string.history_clear_message))
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
                    Text(stringResource(R.string.history_clear_confirm))
                }
            },
            dismissButton = {
                TextButton(onClick = { showClearConfirmation = false }) {
                    Text(stringResource(R.string.action_cancel))
                }
            },
        )
    }

    if (renameTarget != null) {
        AlertDialog(
            onDismissRequest = { renameTarget = null },
            icon = {
                Icon(
                    imageVector = Icons.Rounded.Edit,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                )
            },
            title = {
                Text(
                    stringResource(R.string.history_rename_dialog),
                    fontWeight = FontWeight.Bold,
                )
            },
            text = {
                OutlinedTextField(
                    value = renameValue,
                    onValueChange = { renameValue = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text(stringResource(R.string.history_rename_hint)) },
                    singleLine = true,
                    shape = MaterialTheme.shapes.medium,
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        renameTarget?.let { id ->
                            onAction(MobileUiAction.RenameHistoryItem(id, renameValue))
                        }
                        renameTarget = null
                    },
                ) {
                    Text(stringResource(R.string.history_rename_action))
                }
            },
            dismissButton = {
                TextButton(onClick = { renameTarget = null }) {
                    Text(stringResource(R.string.action_cancel))
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
                    eyebrow = stringResource(R.string.history_heading_eyebrow),
                    title = stringResource(R.string.history_heading_title),
                    supportingText = stringResource(R.string.history_heading_supporting),
                    icon = Icons.Rounded.History,
                )
            }

            if (selectionMode) {
                item {
                    HistorySelectionBar(
                        selectedCount = selectedIds.size,
                        visibleCount = visibleItems.size,
                        allVisibleSelected = visibleItems.isNotEmpty() &&
                            visibleItems.all { it.id in selectedIds },
                        onToggleAll = {
                            onAction(MobileUiAction.ToggleSelectAllHistoryItems(true))
                        },
                        onDelete = { confirmDeleteSelection = true },
                        onClose = { onAction(MobileUiAction.ClearHistorySelection) },
                    )
                }
            }

            if (state.items.isEmpty()) {
                item {
                    EmptyState(
                        icon = Icons.Rounded.FolderOpen,
                        title = stringResource(R.string.history_empty_title),
                        supportingText = stringResource(R.string.history_empty_supporting),
                    )
                }
            } else {
                item {
                    OutlinedTextField(
                        value = state.searchQuery,
                        onValueChange = { onAction(MobileUiAction.HistorySearchQueryChanged(it)) },
                        modifier = Modifier.fillMaxWidth(),
                        placeholder = { Text(stringResource(R.string.history_search_placeholder)) },
                        leadingIcon = {
                            Icon(
                                imageVector = Icons.Rounded.Search,
                                contentDescription = null,
                            )
                        },
                        trailingIcon = if (state.searchQuery.isNotEmpty()) {
                            {
                                IconButton(
                                    onClick = {
                                        onAction(MobileUiAction.HistorySearchQueryChanged(""))
                                    },
                                ) {
                                    Icon(
                                        imageVector = Icons.Rounded.Close,
                                        contentDescription = stringResource(
                                            R.string.history_search_clear,
                                        ),
                                    )
                                }
                            }
                        } else {
                            null
                        },
                        singleLine = true,
                        shape = MaterialTheme.shapes.medium,
                    )
                }
                if (visibleItems.isEmpty()) {
                    item {
                        EmptyState(
                            icon = Icons.Rounded.Search,
                            title = stringResource(R.string.history_no_results_title),
                            supportingText = stringResource(
                                R.string.history_no_results_query,
                                state.searchQuery.trim(),
                            ),
                        )
                    }
                } else {
                    item {
                        InfoBanner(
                            text = pluralStringResource(
                                R.plurals.history_items_found,
                                visibleItems.size,
                                visibleItems.size,
                            ),
                            icon = Icons.Rounded.Inventory2,
                            containerColor = MaterialTheme.colorScheme.tertiaryContainer,
                            contentColor = MaterialTheme.colorScheme.onTertiaryContainer,
                        )
                    }
                    items(visibleItems, key = { it.id }) { item ->
                        HistoryCard(
                            item = item,
                            onAction = onAction,
                            thumbnail = thumbnail,
                            selectionMode = selectionMode,
                            selected = item.id in selectedIds,
                            onClick = {
                                if (selectionMode) {
                                    onAction(MobileUiAction.ToggleHistorySelection(item.id))
                                } else {
                                    onAction(MobileUiAction.OpenHistoryItem(item.id))
                                }
                            },
                            onLongClick = {
                                onAction(MobileUiAction.BeginHistorySelection(item.id))
                            },
                            onRequestRename = { id, currentName ->
                                renameTarget = id
                                renameValue = currentName
                            },
                        )
                    }
                    item {
                        OutlinedButton(
                            onClick = { onAction(MobileUiAction.ExportHistory) },
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 50.dp),
                        ) {
                            Icon(
                                imageVector = Icons.Rounded.FileUpload,
                                contentDescription = null,
                                modifier = Modifier.size(20.dp),
                            )
                            Text(
                                stringResource(R.string.history_export),
                                modifier = Modifier.padding(start = 9.dp),
                            )
                        }
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
                            Text(
                                stringResource(R.string.history_clear_button),
                                modifier = Modifier.padding(start = 9.dp),
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun HistorySelectionBar(
    selectedCount: Int,
    visibleCount: Int,
    allVisibleSelected: Boolean,
    onToggleAll: () -> Unit,
    onDelete: () -> Unit,
    onClose: () -> Unit,
) {
    SectionCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = pluralStringResource(
                    R.plurals.history_selected_count,
                    selectedCount,
                    selectedCount,
                ),
                modifier = Modifier.weight(1f),
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
            )
            IconButton(
                onClick = onToggleAll,
                enabled = visibleCount > 0,
            ) {
                Icon(
                    imageVector = Icons.Rounded.DoneAll,
                    contentDescription = stringResource(
                        if (allVisibleSelected) {
                            R.string.history_selection_clear_all
                        } else {
                            R.string.history_selection_select_all
                        },
                    ),
                )
            }
            IconButton(onClick = onDelete) {
                Icon(
                    imageVector = Icons.Rounded.Delete,
                    contentDescription = stringResource(R.string.history_selection_delete),
                    tint = MaterialTheme.colorScheme.error,
                )
            }
            IconButton(onClick = onClose) {
                Icon(
                    imageVector = Icons.Rounded.Close,
                    contentDescription = stringResource(R.string.history_selection_close),
                )
            }
        }
    }
}

@Composable
private fun HistoryCard(
    item: HistoryItemUi,
    onAction: (MobileUiAction) -> Unit,
    thumbnail: ThumbnailRenderer,
    selectionMode: Boolean,
    selected: Boolean,
    onClick: () -> Unit,
    onLongClick: () -> Unit,
    onRequestRename: (String, String) -> Unit,
) {
    SectionCard {
        Column(
            modifier = Modifier.combinedClickable(onClick = onClick, onLongClick = onLongClick),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(13.dp),
                verticalAlignment = Alignment.Top,
            ) {
                if (selectionMode) {
                    Checkbox(checked = selected, onCheckedChange = { onClick() })
                }
                thumbnail(
                    item.thumbnailUrl,
                    null,
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
                        label = stringResource(R.string.status_completed),
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
                if (item.canSetAsSound) {
                    SoundRoleMenu(
                        onRoleSelected = { role ->
                            onAction(MobileUiAction.SetHistorySound(item.id, role))
                        },
                    )
                }
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
                        stringResource(R.string.action_share),
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
                        imageVector = Icons.AutoMirrored.Rounded.OpenInNew,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                    Text(
                        stringResource(R.string.action_open),
                        modifier = Modifier.padding(start = 7.dp),
                    )
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End),
            ) {
                TextButton(
                    onClick = { onRequestRename(item.id, item.detail) },
                    modifier = Modifier.weight(1f),
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 6.dp),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.Edit,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                    Text(
                        stringResource(R.string.history_rename_action),
                        modifier = Modifier.padding(start = 7.dp),
                        maxLines = 2,
                        textAlign = TextAlign.Center,
                    )
                }
                TextButton(
                    onClick = { onAction(MobileUiAction.RedownloadHistoryItem(item.id)) },
                    modifier = Modifier.weight(1f),
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 6.dp),
                ) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Rounded.Redo,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                    Text(
                        stringResource(R.string.history_redownload),
                        modifier = Modifier.padding(start = 7.dp),
                        maxLines = 2,
                        textAlign = TextAlign.Center,
                    )
                }
            }
        }
    }
}
