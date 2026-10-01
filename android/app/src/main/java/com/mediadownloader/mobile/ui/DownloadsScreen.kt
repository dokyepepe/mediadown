package com.mediadownloader.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Autorenew
import androidx.compose.material.icons.rounded.Cancel
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.CloudDownload
import androidx.compose.material.icons.rounded.ContentCopy
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material.icons.rounded.DeleteSweep
import androidx.compose.material.icons.rounded.Download
import androidx.compose.material.icons.rounded.ErrorOutline
import androidx.compose.material.icons.rounded.KeyboardArrowDown
import androidx.compose.material.icons.rounded.KeyboardArrowUp
import androidx.compose.material.icons.automirrored.rounded.List
import androidx.compose.material.icons.automirrored.rounded.OpenInNew
import androidx.compose.material.icons.rounded.Pause
import androidx.compose.material.icons.rounded.PlayArrow
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Schedule
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Tune
import androidx.compose.material3.Button
import androidx.compose.material3.ElevatedFilterChip
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.mediadownloader.mobile.R

@Composable
fun DownloadsScreen(
    state: DownloadsUiState,
    onAction: (MobileUiAction) -> Unit,
    thumbnail: ThumbnailRenderer,
    modifier: Modifier = Modifier,
) {
    val query = state.searchQuery.trim().lowercase()
    val visibleItems = state.items.filter { item ->
        when (state.selectedFilter) {
            DownloadFilter.ALL -> true
            DownloadFilter.ACTIVE -> item.status.isActive
            DownloadFilter.COMPLETED -> item.status == DownloadStatus.COMPLETED
            DownloadFilter.FAILED -> item.status == DownloadStatus.FAILED ||
                item.status == DownloadStatus.CANCELLED
        } && (query.isEmpty() ||
            item.title.contains(query, ignoreCase = true) ||
            item.detail.contains(query, ignoreCase = true))
    }
    val activeCount = state.items.count { it.status.isActive }
    val completedCount = state.items.count { it.status == DownloadStatus.COMPLETED }
    val failedCount = state.items.count {
        it.status == DownloadStatus.FAILED || it.status == DownloadStatus.CANCELLED
    }
    val hasFinishedItems = state.items.any { !it.status.isActive }

    ScreenContainer(modifier) {
        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 20.dp, vertical = 24.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item {
                ScreenHeading(
                    eyebrow = stringResource(R.string.downloads_heading_eyebrow),
                    title = stringResource(R.string.downloads_heading_title),
                    supportingText = when (activeCount) {
                        0 -> stringResource(R.string.downloads_heading_supporting_idle)
                        else -> pluralStringResource(
                            R.plurals.downloads_heading_active,
                            activeCount,
                            activeCount,
                        )
                    },
                    icon = Icons.Rounded.Download,
                )
            }

            if (state.items.isNotEmpty()) {
                item {
                    DownloadSummary(
                        activeCount = activeCount,
                        completedCount = completedCount,
                        failedCount = failedCount,
                    )
                }
            }

            item {
                OutlinedTextField(
                    value = state.searchQuery,
                    onValueChange = { onAction(MobileUiAction.DownloadsSearchQueryChanged(it)) },
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text(stringResource(R.string.downloads_search_placeholder)) },
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
                                    onAction(MobileUiAction.DownloadsSearchQueryChanged(""))
                                },
                            ) {
                                Icon(
                                    imageVector = Icons.Rounded.Close,
                                    contentDescription = stringResource(
                                        R.string.downloads_search_clear,
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

            item {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(DownloadFilter.entries, key = { it.name }) { filter ->
                        val count = state.items.countFor(filter)
                        ElevatedFilterChip(
                            selected = state.selectedFilter == filter,
                            onClick = { onAction(MobileUiAction.SelectDownloadFilter(filter)) },
                            leadingIcon = {
                                Icon(
                                    imageVector = filter.icon,
                                    contentDescription = null,
                                    modifier = Modifier.size(17.dp),
                                )
                            },
                            label = { Text("${stringResource(filter.labelRes)} · $count") },
                        )
                    }
                }
            }

            if (visibleItems.isEmpty()) {
                item {
                    EmptyState(
                        icon = Icons.Rounded.CloudDownload,
                        title = if (state.items.isEmpty()) {
                            stringResource(R.string.downloads_empty_title)
                        } else {
                            stringResource(R.string.downloads_no_results_title)
                        },
                        supportingText = if (state.items.isEmpty()) {
                            stringResource(R.string.downloads_empty_supporting)
                        } else if (query.isNotEmpty()) {
                            stringResource(
                                R.string.downloads_no_results_query,
                                state.searchQuery.trim(),
                            )
                        } else {
                            stringResource(R.string.downloads_no_results_filter)
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
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 50.dp),
                    ) {
                        Icon(
                            imageVector = Icons.Rounded.DeleteSweep,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                        )
                        Text(
                            text = stringResource(R.string.downloads_remove_finished),
                            modifier = Modifier.padding(start = 9.dp),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun DownloadSummary(
    activeCount: Int,
    completedCount: Int,
    failedCount: Int,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        DownloadMetric(
            value = activeCount,
            label = stringResource(R.string.filter_active),
            icon = Icons.Rounded.Download,
            containerColor = MaterialTheme.colorScheme.primaryContainer,
            contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
            modifier = Modifier.weight(1f),
        )
        DownloadMetric(
            value = completedCount,
            label = stringResource(R.string.filter_completed),
            icon = Icons.Rounded.CheckCircle,
            containerColor = MaterialTheme.colorScheme.tertiaryContainer,
            contentColor = MaterialTheme.colorScheme.onTertiaryContainer,
            modifier = Modifier.weight(1f),
        )
        DownloadMetric(
            value = failedCount,
            label = stringResource(R.string.downloads_metric_attention),
            icon = Icons.Rounded.ErrorOutline,
            containerColor = if (failedCount > 0) {
                MaterialTheme.colorScheme.errorContainer
            } else {
                MaterialTheme.colorScheme.surfaceContainer
            },
            contentColor = if (failedCount > 0) {
                MaterialTheme.colorScheme.onErrorContainer
            } else {
                MaterialTheme.colorScheme.onSurfaceVariant
            },
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun DownloadMetric(
    value: Int,
    label: String,
    icon: ImageVector,
    containerColor: Color,
    contentColor: Color,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.semantics(mergeDescendants = true) { },
        shape = MaterialTheme.shapes.medium,
        color = containerColor,
        contentColor = contentColor,
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(3.dp),
        ) {
            Icon(imageVector = icon, contentDescription = null, modifier = Modifier.size(19.dp))
            Text(
                text = value.toString(),
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = label,
                style = MaterialTheme.typography.labelSmall,
                textAlign = TextAlign.Center,
                maxLines = 2,
            )
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
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(13.dp),
                verticalAlignment = Alignment.Top,
            ) {
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
                    DownloadStatusPill(item.status)
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

            if (item.status.isActive) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (item.progress != null) {
                        LinearProgressIndicator(
                            progress = { item.progress.coerceIn(0f, 1f) },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(8.dp)
                                .clip(CircleShape),
                            trackColor = MaterialTheme.colorScheme.surfaceContainerHighest,
                        )
                    } else {
                        LinearProgressIndicator(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(8.dp)
                                .clip(CircleShape),
                            trackColor = MaterialTheme.colorScheme.surfaceContainerHighest,
                        )
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = item.progressText ?: stringResource(item.status.labelRes),
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        val transferDetails = listOfNotNull(item.speedText, item.etaText)
                            .joinToString("  •  ")
                        if (transferDetails.isNotEmpty()) {
                            Text(
                                text = transferDetails,
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }

            item.errorMessage?.let { error ->
                InfoBanner(
                    text = error,
                    icon = Icons.Rounded.ErrorOutline,
                    containerColor = MaterialTheme.colorScheme.errorContainer,
                    contentColor = MaterialTheme.colorScheme.onErrorContainer,
                )
            }

            if (item.status == DownloadStatus.FAILED && !item.sourceUrl.isNullOrBlank()) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    TextButton(
                        onClick = { onAction(MobileUiAction.CopyDownloadLink(item.id)) },
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 6.dp),
                    ) {
                        Icon(
                            imageVector = Icons.Rounded.ContentCopy,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp),
                        )
                        Text(
                            stringResource(R.string.action_copy_link),
                            modifier = Modifier.padding(start = 7.dp),
                        )
                    }
                    TextButton(
                        onClick = { onAction(MobileUiAction.Navigate(AppTab.SETTINGS)) },
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 6.dp),
                    ) {
                        Icon(
                            imageVector = Icons.Rounded.Tune,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp),
                        )
                        Text(
                            stringResource(R.string.downloads_adjust_cookies),
                            modifier = Modifier.padding(start = 7.dp),
                        )
                    }
                }
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
        horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (item.canMoveUp || item.canMoveDown) {
            if (item.canMoveUp) {
                IconButton(
                    onClick = { onAction(MobileUiAction.MoveDownload(item.id, up = true)) },
                    modifier = Modifier.size(38.dp),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.KeyboardArrowUp,
                        contentDescription = stringResource(R.string.action_move_up),
                        modifier = Modifier.size(20.dp),
                    )
                }
            }
            if (item.canMoveDown) {
                IconButton(
                    onClick = { onAction(MobileUiAction.MoveDownload(item.id, up = false)) },
                    modifier = Modifier.size(38.dp),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.KeyboardArrowDown,
                        contentDescription = stringResource(R.string.action_move_down),
                        modifier = Modifier.size(20.dp),
                    )
                }
            }
        }

        when (item.status) {
            DownloadStatus.QUEUED,
            DownloadStatus.PREPARING,
            DownloadStatus.DOWNLOADING,
            DownloadStatus.PROCESSING -> {
                TextButton(
                    onClick = { onAction(MobileUiAction.PauseDownload(item.id)) },
                    modifier = Modifier.weight(1f),
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 6.dp),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.Pause,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                    Text(
                        stringResource(R.string.action_pause),
                        modifier = Modifier.padding(start = 7.dp),
                    )
                }
                TextButton(
                    onClick = { onAction(MobileUiAction.CancelDownload(item.id)) },
                    modifier = Modifier.weight(1f),
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 6.dp),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.Cancel,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                    Text(
                        stringResource(R.string.action_cancel),
                        modifier = Modifier.padding(start = 7.dp),
                    )
                }
            }

            DownloadStatus.PAUSED -> {
                TextButton(
                    onClick = { onAction(MobileUiAction.RemoveDownload(item.id)) },
                    modifier = Modifier.weight(1f),
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 6.dp),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.DeleteOutline,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                    Text(
                        stringResource(R.string.action_remove),
                        modifier = Modifier.padding(start = 7.dp),
                    )
                }
                Button(
                    onClick = { onAction(MobileUiAction.ResumeDownload(item.id)) },
                    modifier = Modifier.weight(1f),
                    contentPadding = PaddingValues(horizontal = 9.dp, vertical = 8.dp),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.PlayArrow,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                    Text(
                        stringResource(R.string.action_resume),
                        modifier = Modifier.padding(start = 7.dp),
                    )
                }
            }

            DownloadStatus.FAILED,
            DownloadStatus.CANCELLED -> {
                TextButton(
                    onClick = { onAction(MobileUiAction.RemoveDownload(item.id)) },
                    modifier = Modifier.weight(1f),
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 6.dp),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.DeleteOutline,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                    Text(
                        stringResource(R.string.action_remove),
                        modifier = Modifier.padding(start = 7.dp),
                    )
                }
                Button(
                    onClick = { onAction(MobileUiAction.RetryDownload(item.id)) },
                    modifier = Modifier.weight(1.45f),
                    contentPadding = PaddingValues(horizontal = 9.dp, vertical = 8.dp),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.Refresh,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                    Text(
                        stringResource(R.string.action_retry),
                        modifier = Modifier.padding(start = 7.dp),
                        maxLines = 2,
                        textAlign = TextAlign.Center,
                    )
                }
            }

            DownloadStatus.COMPLETED -> {
                if (item.canSetAsSound) {
                    SoundRoleMenu(
                        onRoleSelected = { role ->
                            onAction(MobileUiAction.SetDownloadSound(item.id, role))
                        },
                    )
                }
                TextButton(
                    onClick = { onAction(MobileUiAction.RemoveDownload(item.id)) },
                    modifier = Modifier.weight(1f),
                    contentPadding = PaddingValues(horizontal = 8.dp, vertical = 6.dp),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.DeleteOutline,
                        contentDescription = null,
                        modifier = Modifier.size(18.dp),
                    )
                    Text(
                        stringResource(R.string.action_remove),
                        modifier = Modifier.padding(start = 7.dp),
                    )
                }
                FilledTonalButton(
                    onClick = { onAction(MobileUiAction.OpenDownload(item.id)) },
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
        }
    }
}

@Composable
private fun DownloadStatusPill(status: DownloadStatus) {
    val colors = MaterialTheme.colorScheme
    val (container, content) = when (status) {
        DownloadStatus.QUEUED -> colors.secondaryContainer to colors.onSecondaryContainer
        DownloadStatus.PREPARING,
        DownloadStatus.DOWNLOADING,
        DownloadStatus.PROCESSING -> colors.primaryContainer to colors.onPrimaryContainer
        DownloadStatus.COMPLETED -> colors.tertiaryContainer to colors.onTertiaryContainer
        DownloadStatus.FAILED -> colors.errorContainer to colors.onErrorContainer
        DownloadStatus.PAUSED -> colors.secondaryContainer to colors.onSecondaryContainer
        DownloadStatus.CANCELLED -> colors.surfaceVariant to colors.onSurfaceVariant
    }
    StatusPill(
        label = stringResource(status.labelRes),
        containerColor = container,
        contentColor = content,
        icon = status.icon,
    )
}

private val DownloadStatus.icon: ImageVector
    get() = when (this) {
        DownloadStatus.QUEUED -> Icons.Rounded.Schedule
        DownloadStatus.PREPARING -> Icons.Rounded.Autorenew
        DownloadStatus.DOWNLOADING -> Icons.Rounded.Download
        DownloadStatus.PROCESSING -> Icons.Rounded.Autorenew
        DownloadStatus.COMPLETED -> Icons.Rounded.CheckCircle
        DownloadStatus.FAILED -> Icons.Rounded.ErrorOutline
        DownloadStatus.PAUSED -> Icons.Rounded.Pause
        DownloadStatus.CANCELLED -> Icons.Rounded.Cancel
    }

private val DownloadFilter.icon: ImageVector
    get() = when (this) {
        DownloadFilter.ALL -> Icons.AutoMirrored.Rounded.List
        DownloadFilter.ACTIVE -> Icons.Rounded.Download
        DownloadFilter.COMPLETED -> Icons.Rounded.CheckCircle
        DownloadFilter.FAILED -> Icons.Rounded.ErrorOutline
    }

private val DownloadStatus.isActive: Boolean
    get() = this == DownloadStatus.QUEUED ||
        this == DownloadStatus.PREPARING ||
        this == DownloadStatus.DOWNLOADING ||
        this == DownloadStatus.PROCESSING ||
        this == DownloadStatus.PAUSED

private fun List<DownloadItemUi>.countFor(filter: DownloadFilter): Int = count { item ->
    when (filter) {
        DownloadFilter.ALL -> true
        DownloadFilter.ACTIVE -> item.status.isActive
        DownloadFilter.COMPLETED -> item.status == DownloadStatus.COMPLETED
        DownloadFilter.FAILED -> item.status == DownloadStatus.FAILED ||
            item.status == DownloadStatus.CANCELLED
    }
}
