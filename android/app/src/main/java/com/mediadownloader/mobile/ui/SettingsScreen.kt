package com.mediadownloader.mobile.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Autorenew
import androidx.compose.material.icons.rounded.Block
import androidx.compose.material.icons.rounded.BrightnessAuto
import androidx.compose.material.icons.rounded.Backup
import androidx.compose.material.icons.rounded.BugReport
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.ChevronRight
import androidx.compose.material.icons.rounded.CleaningServices
import androidx.compose.material.icons.rounded.Code
import androidx.compose.material.icons.rounded.ContentCopy
import androidx.compose.material.icons.rounded.Cookie
import androidx.compose.material.icons.rounded.DarkMode
import androidx.compose.material.icons.rounded.Delete
import androidx.compose.material.icons.rounded.Description
import androidx.compose.material.icons.rounded.Download
import androidx.compose.material.icons.rounded.ErrorOutline
import androidx.compose.material.icons.rounded.Favorite
import androidx.compose.material.icons.rounded.FileUpload
import androidx.compose.material.icons.rounded.Folder
import androidx.compose.material.icons.rounded.FolderOpen
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.Insights
import androidx.compose.material.icons.rounded.Language
import androidx.compose.material.icons.rounded.RemoveCircleOutline
import androidx.compose.material.icons.rounded.LightMode
import androidx.compose.material.icons.rounded.MusicNote
import androidx.compose.material.icons.rounded.Notifications
import androidx.compose.material.icons.rounded.Palette
import androidx.compose.material.icons.rounded.PrivacyTip
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.material.icons.rounded.Public
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.SettingsBackupRestore
import androidx.compose.material.icons.rounded.SettingsPower
import androidx.compose.material.icons.rounded.Restore
import androidx.compose.material.icons.rounded.RocketLaunch
import androidx.compose.material.icons.rounded.Schedule
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Security
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material.icons.rounded.Speed
import androidx.compose.material.icons.rounded.SystemUpdate
import androidx.compose.material.icons.rounded.Tune
import androidx.compose.material.icons.rounded.Vibration
import androidx.compose.material.icons.automirrored.rounded.VolumeUp
import androidx.compose.material.icons.rounded.Wifi
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.mediadownloader.mobile.R
import com.mediadownloader.mobile.data.StorageCategory
import com.mediadownloader.mobile.support.SupportConfig

@Composable
fun SettingsScreen(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
    modifier: Modifier = Modifier,
    onImportSettings: () -> Unit = {},
) {
    if (state.showYtDlpRollbackConfirmation) {
        YtDlpRollbackConfirmationDialog(state = state, onAction = onAction)
    }
    ScreenContainer(modifier) {
        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 20.dp, vertical = 24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item {
                ScreenHeading(
                    eyebrow = stringResource(R.string.settings_eyebrow),
                    title = stringResource(R.string.settings_title),
                    supportingText = stringResource(R.string.settings_subtitle),
                    icon = Icons.Rounded.Settings,
                )
            }

            item {
                AppearanceCard(state = state, onAction = onAction)
            }

            item {
                StorageCard(state = state, onAction = onAction)
            }

            item {
                NetworkCard(state = state, onAction = onAction)
            }

            item {
                FilesCard(state = state, onAction = onAction)
            }

            item {
                DefaultsCard(state = state, onAction = onAction)
            }

            item {
                DownloadsCard(state = state, onAction = onAction)
            }

            item {
                StatsCard(state = state, onAction = onAction)
            }

            item {
                CookiesCard(state = state, onAction = onAction)
            }

            item {
                SiteCompatibilityCard(state = state, onAction = onAction)
            }

            item {
                SpotifyCard(state = state, onAction = onAction)
            }

            item {
                YtDlpUpdateCard(state = state, onAction = onAction)
            }

            item {
                AppInfoCard(state = state, onAction = onAction, onImportSettings = onImportSettings)
            }
        }
    }
}

@Composable
private fun AppearanceCard(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
            SectionTitle(
                title = stringResource(R.string.settings_appearance),
                supportingText = stringResource(R.string.settings_appearance_support),
                icon = Icons.Rounded.Palette,
            )
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .selectableGroup(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                ThemePreference.entries.forEach { theme ->
                    ThemeOption(
                        theme = theme,
                        selected = state.theme == theme,
                        onClick = { onAction(MobileUiAction.SetTheme(theme)) },
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        }
    }
}

@Composable
private fun ThemeOption(
    theme: ThemePreference,
    selected: Boolean,
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
        MaterialTheme.colorScheme.onSurfaceVariant
    }
    Surface(
        modifier = modifier.selectable(
            selected = selected,
            role = Role.RadioButton,
            onClick = onClick,
        ),
        shape = MaterialTheme.shapes.medium,
        color = container,
        contentColor = content,
        border = BorderStroke(
            width = 1.dp,
            color = if (selected) {
                MaterialTheme.colorScheme.primary
            } else {
                MaterialTheme.colorScheme.outlineVariant
            },
        ),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 6.dp, vertical = 12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            Icon(
                imageVector = theme.icon,
                contentDescription = null,
                modifier = Modifier.size(24.dp),
            )
            Text(
                text = stringResource(theme.labelRes),
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
            )
            RadioButton(
                selected = selected,
                onClick = null,
                modifier = Modifier.clearAndSetSemantics { },
            )
        }
    }
}

@Composable
private fun StorageCard(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(15.dp)) {
            SectionTitle(
                title = stringResource(R.string.settings_storage),
                supportingText = stringResource(R.string.settings_storage_support),
                icon = Icons.Rounded.Folder,
            )
            state.storageLocations.forEach { location ->
                val categoryRes = when (location.category) {
                    StorageCategory.VIDEO -> R.string.settings_category_videos
                    StorageCategory.AUDIO -> R.string.settings_category_audio
                    StorageCategory.SITE_FILES -> R.string.settings_category_site_files
                }
                Surface(
                    shape = MaterialTheme.shapes.medium,
                    color = MaterialTheme.colorScheme.surfaceContainer,
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(14.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        Row(
                            horizontalArrangement = Arrangement.spacedBy(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Surface(
                                modifier = Modifier.size(42.dp),
                                shape = MaterialTheme.shapes.small,
                                color = MaterialTheme.colorScheme.tertiaryContainer,
                                contentColor = MaterialTheme.colorScheme.onTertiaryContainer,
                            ) {
                                Box(contentAlignment = Alignment.Center) {
                                    Icon(
                                        imageVector = Icons.Rounded.FolderOpen,
                                        contentDescription = null,
                                        modifier = Modifier.size(23.dp),
                                    )
                                }
                            }
                            Column(
                                modifier = Modifier.weight(1f),
                                verticalArrangement = Arrangement.spacedBy(2.dp),
                            ) {
                                Text(
                                    text = stringResource(categoryRes),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                                Text(
                                    text = location.locationLabel,
                                    style = MaterialTheme.typography.bodyMedium,
                                    fontWeight = FontWeight.SemiBold,
                                    maxLines = 2,
                                    overflow = TextOverflow.Ellipsis,
                                )
                            }
                        }
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            OutlinedButton(
                                onClick = {
                                    onAction(MobileUiAction.ChooseDownloadLocation(location.category))
                                },
                                modifier = Modifier.weight(1f),
                            ) {
                                Text(
                                    stringResource(
                                        if (location.isCustom) {
                                            R.string.settings_storage_change_folder
                                        } else {
                                            R.string.settings_storage_choose_folder
                                        },
                                    ),
                                )
                            }
                            if (location.isCustom) {
                                OutlinedButton(
                                    onClick = {
                                        onAction(MobileUiAction.ResetDownloadLocation(location.category))
                                    },
                                ) {
                                    Text(stringResource(R.string.settings_storage_use_default))
                                }
                            }
                        }
                    }
                }
            }
            Text(
                text = stringResource(R.string.settings_storage_note),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun NetworkCard(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
            SectionTitle(
                title = stringResource(R.string.settings_network),
                supportingText = stringResource(R.string.settings_network_support),
                icon = Icons.Rounded.Public,
            )
            OutlinedTextField(
                value = state.proxy,
                onValueChange = { onAction(MobileUiAction.SetProxy(it)) },
                modifier = Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.settings_proxy_label)) },
                placeholder = { Text("socks5://127.0.0.1:1080") },
                supportingText = {
                    Text(
                        state.proxyError
                            ?: stringResource(R.string.settings_proxy_support),
                    )
                },
                isError = state.proxyError != null,
                singleLine = true,
                shape = MaterialTheme.shapes.medium,
            )
            OutlinedTextField(
                value = state.rateLimitText,
                onValueChange = { onAction(MobileUiAction.SetRateLimitText(it)) },
                modifier = Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.settings_rate_limit_label)) },
                placeholder = { Text(stringResource(R.string.settings_rate_limit_placeholder)) },
                supportingText = {
                    Text(stringResource(R.string.settings_rate_limit_support))
                },
                isError = false,
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                shape = MaterialTheme.shapes.medium,
            )
        }
    }
}

@Composable
private fun FilesCard(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
            SectionTitle(
                title = stringResource(R.string.settings_filename_template),
                supportingText = stringResource(R.string.settings_filename_template_support),
                icon = Icons.Rounded.Description,
            )
            OutlinedTextField(
                value = state.filenameTemplate,
                onValueChange = { onAction(MobileUiAction.SetFilenameTemplate(it)) },
                modifier = Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.settings_template_label)) },
                placeholder = { Text("%(title).180B [%(id)s].%(ext)s") },
                supportingText = {
                    Text(
                        if (state.filenameTemplate.isBlank()) {
                            stringResource(R.string.settings_template_support_empty)
                        } else {
                            stringResource(R.string.settings_template_support_hint)
                        },
                    )
                },
                shape = MaterialTheme.shapes.medium,
            )
            OutlinedButton(
                onClick = { onAction(MobileUiAction.ResetFilenameTemplate) },
                enabled = state.filenameTemplate.isNotBlank(),
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 50.dp),
            ) {
                Icon(
                    imageVector = Icons.Rounded.Restore,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp),
                )
                Text(
                    text = stringResource(R.string.action_restore_default),
                    modifier = Modifier.padding(start = 9.dp),
                )
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun DefaultsCard(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
            SectionTitle(
                title = stringResource(R.string.settings_media_defaults),
                supportingText = stringResource(R.string.settings_media_defaults_support),
                icon = Icons.Rounded.Tune,
            )

            ChoiceChips(
                label = stringResource(R.string.settings_default_video_quality),
                choices = videoQualityChoices(),
                selectedId = state.defaultVideoQualityId,
                onSelect = { onAction(MobileUiAction.SetDefaultVideoQuality(it)) },
            )
            ChoiceChips(
                label = stringResource(R.string.settings_default_video_format),
                choices = VIDEO_FORMAT_CHOICES,
                selectedId = state.defaultVideoFormatId,
                onSelect = { onAction(MobileUiAction.SetDefaultVideoFormat(it)) },
            )
            ChoiceChips(
                label = stringResource(R.string.settings_default_audio_quality),
                choices = AUDIO_QUALITY_CHOICES,
                selectedId = state.defaultAudioBitrate.toString(),
                onSelect = { onAction(MobileUiAction.SetDefaultAudioBitrate(it.toInt())) },
            )
            ChoiceChips(
                label = stringResource(R.string.settings_default_audio_format),
                choices = AUDIO_FORMAT_CHOICES,
                selectedId = state.defaultAudioFormatId,
                onSelect = { onAction(MobileUiAction.SetDefaultAudioFormat(it)) },
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun DownloadsCard(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
            SectionTitle(
                title = stringResource(R.string.settings_downloads),
                supportingText = stringResource(R.string.settings_downloads_support),
                icon = Icons.Rounded.RocketLaunch,
            )
            ChoiceChips(
                label = stringResource(R.string.settings_parallel_downloads),
                choices = parallelDownloadChoices(),
                selectedId = state.parallelDownloads.toString(),
                onSelect = { onAction(MobileUiAction.SetParallelDownloads(it.toInt())) },
            )
            SettingsToggleRow(
                title = stringResource(R.string.settings_wifi_only),
                subtitle = stringResource(R.string.settings_wifi_only_support),
                icon = Icons.Rounded.Wifi,
                checked = state.wifiOnly,
                onToggle = { onAction(MobileUiAction.SetWifiOnly(it)) },
            )
            SettingsToggleRow(
                title = stringResource(R.string.settings_schedule_window),
                subtitle = stringResource(R.string.settings_schedule_window_support),
                icon = Icons.Rounded.Schedule,
                checked = state.downloadWindowEnabled,
                onToggle = { onAction(MobileUiAction.SetDownloadWindowEnabled(it)) },
            )
            if (state.downloadWindowEnabled) {
                OutlinedTextField(
                    value = state.downloadWindowStartMin.toString(),
                    onValueChange = { raw ->
                        raw.filter(Char::isDigit).toIntOrNull()?.let {
                            onAction(MobileUiAction.SetDownloadWindowStartMin(it))
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text(stringResource(R.string.settings_window_start_label)) },
                    supportingText = { Text(stringResource(R.string.settings_window_start_hint)) },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    shape = MaterialTheme.shapes.medium,
                )
                OutlinedTextField(
                    value = state.downloadWindowEndMin.toString(),
                    onValueChange = { raw ->
                        raw.filter(Char::isDigit).toIntOrNull()?.let {
                            onAction(MobileUiAction.SetDownloadWindowEndMin(it))
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text(stringResource(R.string.settings_window_end_label)) },
                    supportingText = { Text(stringResource(R.string.settings_window_end_hint)) },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    shape = MaterialTheme.shapes.medium,
                )
            }
            SettingsToggleRow(
                title = stringResource(R.string.settings_keep_awake),
                subtitle = stringResource(R.string.settings_keep_awake_support),
                icon = Icons.Rounded.SettingsPower,
                checked = state.keepAwakeDuringDownloads,
                onToggle = { onAction(MobileUiAction.SetKeepAwakeDuringDownloads(it)) },
            )
            SectionTitle(
                title = stringResource(R.string.settings_on_complete),
                supportingText = stringResource(R.string.settings_on_complete_support),
                icon = Icons.Rounded.Notifications,
            )
            SettingsToggleRow(
                title = stringResource(R.string.settings_completion_sound),
                subtitle = stringResource(R.string.settings_completion_sound_support),
                icon = Icons.AutoMirrored.Rounded.VolumeUp,
                checked = state.completionSound,
                onToggle = { onAction(MobileUiAction.SetCompletionSound(it)) },
            )
            SettingsToggleRow(
                title = stringResource(R.string.settings_completion_vibrate),
                subtitle = stringResource(R.string.settings_completion_vibrate_support),
                icon = Icons.Rounded.Vibration,
                checked = state.completionVibrate,
                onToggle = { onAction(MobileUiAction.SetCompletionVibrate(it)) },
            )
        }
    }
}

@Composable
private fun StatsCard(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
            SectionTitle(
                title = stringResource(R.string.settings_stats),
                supportingText = stringResource(R.string.settings_stats_support),
                icon = Icons.Rounded.Insights,
            )
            StatRow(
                label = stringResource(R.string.settings_stats_completed),
                value = state.statsCompletedCount.toString(),
            )
            StatRow(
                label = stringResource(R.string.settings_stats_downloaded),
                value = StatFormatting.bytes(state.statsDownloadedBytes),
            )
            StatRow(
                label = stringResource(R.string.settings_stats_temp),
                value = StatFormatting.bytes(state.statsTempBytes),
            )
            StatRow(
                label = stringResource(R.string.settings_stats_free),
                value = StatFormatting.bytes(state.statsFreeBytes),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(
                    onClick = { onAction(MobileUiAction.RefreshStats) },
                    modifier = Modifier
                        .weight(1f)
                        .heightIn(min = 50.dp),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.Refresh,
                        contentDescription = null,
                        modifier = Modifier.size(20.dp),
                    )
                    Text(
                        text = stringResource(R.string.settings_stats_refresh),
                        modifier = Modifier.padding(start = 9.dp),
                    )
                }
                OutlinedButton(
                    onClick = { onAction(MobileUiAction.RemoveTemporaryFiles) },
                    modifier = Modifier
                        .weight(1f)
                        .heightIn(min = 50.dp),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.CleaningServices,
                        contentDescription = null,
                        modifier = Modifier.size(20.dp),
                    )
                    Text(
                        text = stringResource(R.string.settings_stats_clean),
                        modifier = Modifier.padding(start = 9.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun StatRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Bold,
        )
    }
}

private object StatFormatting {
    fun bytes(value: Long): String {
        if (value <= 0) return "0 B"
        val units = arrayOf("B", "KiB", "MiB", "GiB", "TiB")
        var amount = value.toDouble()
        var unit = 0
        while (amount >= 1024 && unit < units.size - 1) {
            amount /= 1024
            unit += 1
        }
        return "%.1f %s".format(amount, units[unit])
    }
}

@Composable
private fun SettingsToggleRow(
    title: String,
    subtitle: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    checked: Boolean,
    onToggle: (Boolean) -> Unit,
) {
    Surface(
        modifier = Modifier.toggleable(
            value = checked,
            role = Role.Switch,
            onValueChange = onToggle,
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
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Switch(checked = checked, onCheckedChange = null)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ChoiceChips(
    label: String,
    choices: List<Pair<String, String>>,
    selectedId: String,
    onSelect: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontWeight = FontWeight.SemiBold,
        )
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            choices.forEach { (id, labelText) ->
                FilterChip(
                    selected = selectedId == id,
                    onClick = { onSelect(id) },
                    label = { Text(labelText) },
                )
            }
        }
    }
}

@Composable
private fun CookiesCard(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
            SectionTitle(
                title = stringResource(R.string.settings_cookies),
                supportingText = stringResource(R.string.settings_cookies_support),
                icon = Icons.Rounded.Cookie,
            )

            if (state.cookie != null) {
                val check = state.cookie
                val container = if (check.ok) {
                    MaterialTheme.colorScheme.tertiaryContainer
                } else {
                    MaterialTheme.colorScheme.errorContainer
                }
                val content = if (check.ok) {
                    MaterialTheme.colorScheme.onTertiaryContainer
                } else {
                    MaterialTheme.colorScheme.onErrorContainer
                }
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = MaterialTheme.shapes.medium,
                    color = container,
                    contentColor = content,
                ) {
                    Row(
                        modifier = Modifier.padding(14.dp),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(
                            imageVector = if (check.ok) {
                                Icons.Rounded.CheckCircle
                            } else {
                                Icons.Rounded.ErrorOutline
                            },
                            contentDescription = null,
                            modifier = Modifier.size(24.dp),
                        )
                        Column(
                            modifier = Modifier.weight(1f),
                            verticalArrangement = Arrangement.spacedBy(2.dp),
                        ) {
                            Text(
                                text = check.message,
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.Bold,
                            )
                            if (check.detail.isNotBlank()) {
                                Text(
                                    text = check.detail,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = content.copy(alpha = 0.8f),
                                )
                            }
                        }
                    }
                }
            } else {
                InfoBanner(
                    text = stringResource(R.string.settings_cookies_none),
                    icon = Icons.Rounded.ErrorOutline,
                )
            }

            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(
                    onClick = { onAction(MobileUiAction.ChooseCookieFile) },
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
                        stringResource(
                            if (state.cookieFileName == null) {
                                R.string.settings_cookies_choose_file
                            } else {
                                R.string.settings_cookies_replace_file
                            },
                        ),
                        modifier = Modifier.padding(start = 9.dp),
                    )
                }
                if (state.cookieFileName != null) {
                    TextButton(
                        onClick = { onAction(MobileUiAction.ClearCookies) },
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                    ) {
                        Icon(
                            imageVector = Icons.Rounded.Delete,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                        )
                        Text(
                            text = stringResource(R.string.settings_cookies_remove),
                            modifier = Modifier.padding(start = 9.dp),
                        )
                    }
                }
            }

            HorizontalDivider(
                color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f),
            )

            SectionTitle(
                title = stringResource(R.string.settings_cookies_by_site),
                supportingText = stringResource(R.string.settings_cookies_by_site_support),
                icon = Icons.Rounded.Language,
            )
            OutlinedTextField(
                value = state.siteCookieHosts,
                onValueChange = { onAction(MobileUiAction.SiteCookieHostsChanged(it)) },
                modifier = Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.settings_sites_label)) },
                placeholder = { Text("youtube.com, instagram.com") },
                supportingText = {
                    Text(
                        state.siteCookieHostsError
                            ?: stringResource(R.string.settings_sites_support),
                    )
                },
                isError = state.siteCookieHostsError != null,
                singleLine = true,
                shape = MaterialTheme.shapes.medium,
            )
            OutlinedButton(
                onClick = { onAction(MobileUiAction.ChooseSiteCookieFile) },
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
                    text = stringResource(R.string.settings_sites_choose_file),
                    modifier = Modifier.padding(start = 9.dp),
                )
            }

            state.cookieSubProfiles.forEach { profile ->
                Surface(
                    shape = MaterialTheme.shapes.medium,
                    color = MaterialTheme.colorScheme.surfaceContainer,
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(start = 14.dp, top = 10.dp, bottom = 10.dp, end = 6.dp),
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(
                            imageVector = Icons.Rounded.Cookie,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(22.dp),
                        )
                        Column(
                            modifier = Modifier.weight(1f),
                            verticalArrangement = Arrangement.spacedBy(2.dp),
                        ) {
                            Text(
                                text = profile.label,
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.SemiBold,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                            Text(
                                text = profile.hosts,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                            Text(
                                text = profile.cookie?.message
                                    ?: stringResource(R.string.settings_profile_no_diagnostic),
                                style = MaterialTheme.typography.bodySmall,
                                color = if (profile.cookie?.ok == true) {
                                    MaterialTheme.colorScheme.tertiary
                                } else {
                                    MaterialTheme.colorScheme.onSurfaceVariant
                                },
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis,
                            )
                            OutlinedTextField(
                                value = profile.impersonate,
                                onValueChange = {
                                    onAction(MobileUiAction.SetCookieProfileImpersonate(profile.id, it))
                                },
                                modifier = Modifier.fillMaxWidth(),
                                label = { Text(stringResource(R.string.settings_impersonate_label)) },
                                placeholder = { Text("chrome, safari, edge…") },
                                supportingText = {
                                    Text(stringResource(R.string.settings_impersonate_support))
                                },
                                singleLine = true,
                                shape = MaterialTheme.shapes.small,
                            )
                        }
                        TextButton(
                            onClick = { onAction(MobileUiAction.ReplaceSiteCookieFile(profile.id)) },
                        ) {
                            Text(stringResource(R.string.settings_profile_replace))
                        }
                        IconButton(
                            onClick = { onAction(MobileUiAction.RemoveCookieProfile(profile.id)) },
                        ) {
                            Icon(
                                imageVector = Icons.Rounded.Delete,
                                contentDescription = stringResource(R.string.settings_profile_remove_cd),
                                tint = MaterialTheme.colorScheme.error,
                            )
                        }
                    }
                }
            }

            Text(
                text = stringResource(R.string.settings_cookies_privacy_note),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/**
 * Sites listed so the user knows what to expect before pasting a link. The engine runs
 * yt-dlp, so support depends on the bundled version; only the cookie hint differs.
 */
enum class SiteCompatibility(
    val id: String,
    val labelRes: Int,
    val supportedRes: Int,
    val unsupportedRes: Int,
) {
    YOUTUBE(
        id = "youtube",
        labelRes = R.string.settings_compat_youtube,
        supportedRes = R.string.settings_compat_youtube_ok,
        unsupportedRes = R.string.settings_compat_generic_issue,
    ),
    TIKTOK(
        id = "tiktok",
        labelRes = R.string.settings_compat_tiktok,
        supportedRes = R.string.settings_compat_tiktok_ok,
        unsupportedRes = R.string.settings_compat_generic_issue,
    ),
    INSTAGRAM(
        id = "instagram",
        labelRes = R.string.settings_compat_instagram,
        supportedRes = R.string.settings_compat_instagram_ok,
        unsupportedRes = R.string.settings_compat_instagram_issue,
    ),
    FACEBOOK(
        id = "facebook",
        labelRes = R.string.settings_compat_facebook,
        supportedRes = R.string.settings_compat_generic_ok,
        unsupportedRes = R.string.settings_compat_generic_issue,
    ),
    X(
        id = "x",
        labelRes = R.string.settings_compat_x,
        supportedRes = R.string.settings_compat_generic_ok,
        unsupportedRes = R.string.settings_compat_x_issue,
    ),
    SOUNDCLOUD(
        id = "soundcloud",
        labelRes = R.string.settings_compat_soundcloud,
        supportedRes = R.string.settings_compat_soundcloud_ok,
        unsupportedRes = R.string.settings_compat_generic_issue,
    ),
}

@Composable
private fun SiteCompatibilityCard(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            SectionTitle(
                title = stringResource(R.string.settings_compat_title),
                supportingText = stringResource(R.string.settings_compat_support),
                icon = Icons.Rounded.Language,
            )
            SiteCompatibility.entries.forEach { site ->
                val supported = state.compatSupportedSites.contains(site.id)
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalAlignment = Alignment.Top,
                ) {
                    Icon(
                        imageVector = if (supported) {
                            Icons.Rounded.CheckCircle
                        } else {
                            Icons.Rounded.RemoveCircleOutline
                        },
                        contentDescription = null,
                        tint = if (supported) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        },
                        modifier = Modifier.size(20.dp),
                    )
                    Column(
                        modifier = Modifier.weight(1f),
                        verticalArrangement = Arrangement.spacedBy(2.dp),
                    ) {
                        Text(
                            text = stringResource(site.labelRes),
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Bold,
                        )
                        Text(
                            text = stringResource(
                                if (supported) site.supportedRes else site.unsupportedRes,
                            ),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            Text(
                text = stringResource(R.string.settings_compat_cookies_hint),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedButton(
                onClick = { onAction(MobileUiAction.Navigate(AppTab.SETTINGS)) },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(stringResource(R.string.settings_compat_configure_cookies))
            }
        }
    }
}

@Composable
private fun SpotifyCard(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    val isBusy = state.isSpotifyConnecting
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
            SectionTitle(
                title = "Spotify",
                supportingText = stringResource(R.string.settings_spotify_support),
                icon = Icons.Rounded.MusicNote,
            )

            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium,
                color = if (state.spotifyConnected) {
                    MaterialTheme.colorScheme.tertiaryContainer
                } else {
                    MaterialTheme.colorScheme.surfaceContainer
                },
                contentColor = if (state.spotifyConnected) {
                    MaterialTheme.colorScheme.onTertiaryContainer
                } else {
                    MaterialTheme.colorScheme.onSurface
                },
            ) {
                Row(
                    modifier = Modifier.padding(14.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        imageVector = if (state.spotifyConnected) {
                            Icons.Rounded.CheckCircle
                        } else {
                            Icons.Rounded.MusicNote
                        },
                        contentDescription = null,
                        modifier = Modifier.size(24.dp),
                    )
                    Column(
                        modifier = Modifier.weight(1f),
                        verticalArrangement = Arrangement.spacedBy(2.dp),
                    ) {
                        Text(
                            text = if (state.spotifyConnected) {
                                stringResource(R.string.settings_spotify_connected)
                            } else {
                                stringResource(R.string.settings_spotify_not_connected)
                            },
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Bold,
                        )
                        Text(
                            text = state.spotifyAccountName
                                ?: stringResource(R.string.settings_spotify_account_hint),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            OutlinedTextField(
                value = state.spotifyClientId,
                onValueChange = { onAction(MobileUiAction.SetSpotifyClientId(it)) },
                modifier = Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.settings_spotify_client_id_label)) },
                supportingText = {
                    Text(
                        state.spotifyClientIdError
                            ?: stringResource(R.string.settings_spotify_client_id_support),
                    )
                },
                isError = state.spotifyClientIdError != null,
                enabled = !isBusy,
                singleLine = true,
                shape = MaterialTheme.shapes.medium,
            )

            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(
                    onClick = { onAction(MobileUiAction.ConnectSpotify) },
                    enabled = !isBusy && !state.spotifyConnected,
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 52.dp),
                ) {
                    if (isBusy) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(20.dp),
                            strokeWidth = 2.dp,
                            color = MaterialTheme.colorScheme.onPrimary,
                        )
                        Text(
                            text = stringResource(R.string.settings_spotify_waiting),
                            modifier = Modifier.padding(start = 9.dp),
                        )
                    } else {
                        Icon(
                            imageVector = Icons.Rounded.MusicNote,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                        )
                        Text(
                            text = stringResource(R.string.settings_spotify_connect),
                            modifier = Modifier.padding(start = 9.dp),
                        )
                    }
                }
                if (state.spotifyConnected) {
                    TextButton(
                        onClick = { onAction(MobileUiAction.DisconnectSpotify) },
                        enabled = !isBusy,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                    ) {
                        Icon(
                            imageVector = Icons.Rounded.Delete,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                        )
                        Text(
                            text = stringResource(R.string.settings_spotify_disconnect),
                            modifier = Modifier.padding(start = 9.dp),
                        )
                    }
                }
            }

            Text(
                text = stringResource(R.string.settings_spotify_note),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun YtDlpUpdateCard(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    val isBusy = state.isYtDlpOperationBusy

    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
            SectionTitle(
                title = stringResource(R.string.settings_site_compat),
                supportingText = stringResource(R.string.settings_site_compat_support),
                icon = Icons.Rounded.Language,
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(9.dp),
            ) {
                VersionTile(
                    label = stringResource(R.string.settings_ytdlp_current_version),
                    value = state.ytDlpVersion
                        ?: stringResource(R.string.settings_ytdlp_version_unknown),
                    modifier = Modifier.weight(1f),
                )
                state.availableYtDlpVersion?.let { version ->
                    VersionTile(
                        label = stringResource(R.string.settings_ytdlp_available_version),
                        value = version,
                        highlighted = true,
                        modifier = Modifier.weight(1f),
                    )
                }
            }

            state.previousYtDlpVersion?.let { version ->
                LabelValueRow(
                    label = stringResource(R.string.settings_ytdlp_previous_version),
                    value = version,
                )
            }

            Surface(
                modifier = Modifier.toggleable(
                    value = state.autoUpdateYtDlp,
                    enabled = !isBusy,
                    role = Role.Switch,
                    onValueChange = { onAction(MobileUiAction.SetAutoUpdateYtDlp(it)) },
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
                        imageVector = Icons.Rounded.Autorenew,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(23.dp),
                    )
                    Column(
                        modifier = Modifier.weight(1f),
                        verticalArrangement = Arrangement.spacedBy(2.dp),
                    ) {
                        Text(
                            text = stringResource(R.string.settings_ytdlp_auto_check),
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Text(
                            text = stringResource(R.string.settings_ytdlp_auto_check_support),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Switch(
                        checked = state.autoUpdateYtDlp,
                        onCheckedChange = null,
                        enabled = !isBusy,
                    )
                }
            }

            UpdateStatus(state = state)

            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(
                    onClick = { onAction(MobileUiAction.CheckYtDlpUpdate) },
                    enabled = !isBusy,
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 50.dp),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.Search,
                        contentDescription = null,
                        modifier = Modifier.size(20.dp),
                    )
                    Text(
                        text = stringResource(R.string.settings_ytdlp_check_update),
                        modifier = Modifier.padding(start = 9.dp),
                    )
                }
                if (state.canInstallYtDlpUpdate) {
                    Button(
                        onClick = { onAction(MobileUiAction.UpdateYtDlp) },
                        enabled = !isBusy,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 52.dp),
                    ) {
                        Icon(
                            imageVector = Icons.Rounded.SystemUpdate,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                        )
                        Text(
                            text = stringResource(R.string.settings_ytdlp_update_now),
                            modifier = Modifier.padding(start = 9.dp),
                        )
                    }
                }
                if (state.canRollbackYtDlp) {
                    TextButton(
                        onClick = { onAction(MobileUiAction.RequestYtDlpRollback) },
                        enabled = !isBusy,
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 48.dp),
                    ) {
                        Icon(
                            imageVector = Icons.Rounded.Restore,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                        )
                        Text(
                            text = stringResource(R.string.settings_ytdlp_restore_previous),
                            modifier = Modifier.padding(start = 9.dp),
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun VersionTile(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    highlighted: Boolean = false,
) {
    val container = if (highlighted) {
        MaterialTheme.colorScheme.primaryContainer
    } else {
        MaterialTheme.colorScheme.surfaceContainer
    }
    val content = if (highlighted) {
        MaterialTheme.colorScheme.onPrimaryContainer
    } else {
        MaterialTheme.colorScheme.onSurface
    }
    Surface(
        modifier = modifier,
        shape = MaterialTheme.shapes.medium,
        color = container,
        contentColor = content,
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(3.dp),
        ) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelSmall,
                color = content.copy(alpha = 0.72f),
            )
            Text(
                text = value,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun UpdateStatus(state: SettingsUiState) {
    val title = when (state.updateState) {
        YtDlpUpdateState.IDLE -> stringResource(R.string.settings_ytdlp_state_idle)
        YtDlpUpdateState.CHECKING -> stringResource(R.string.settings_ytdlp_state_checking)
        YtDlpUpdateState.AVAILABLE -> stringResource(R.string.settings_ytdlp_state_available)
        YtDlpUpdateState.UPDATING -> stringResource(R.string.settings_ytdlp_state_updating)
        YtDlpUpdateState.ROLLING_BACK -> stringResource(R.string.settings_ytdlp_state_rolling_back)
        YtDlpUpdateState.UP_TO_DATE -> stringResource(R.string.settings_ytdlp_state_up_to_date)
        YtDlpUpdateState.ROLLED_BACK -> stringResource(R.string.settings_ytdlp_state_rolled_back)
        YtDlpUpdateState.REJECTED -> stringResource(R.string.settings_ytdlp_state_rejected)
        YtDlpUpdateState.FAILED -> stringResource(R.string.settings_ytdlp_state_failed)
    }
    val detail = state.updateDetail ?: when (state.updateState) {
        YtDlpUpdateState.IDLE -> stringResource(R.string.settings_ytdlp_state_idle_detail)
        YtDlpUpdateState.CHECKING -> stringResource(R.string.settings_ytdlp_state_checking_detail)
        YtDlpUpdateState.AVAILABLE -> stringResource(R.string.settings_ytdlp_state_available_detail)
        YtDlpUpdateState.UPDATING -> stringResource(R.string.settings_ytdlp_state_updating_detail)
        YtDlpUpdateState.ROLLING_BACK ->
            stringResource(R.string.settings_ytdlp_state_rolling_back_detail)
        YtDlpUpdateState.UP_TO_DATE -> stringResource(R.string.settings_ytdlp_state_up_to_date_detail)
        YtDlpUpdateState.ROLLED_BACK -> stringResource(R.string.settings_ytdlp_state_rolled_back_detail)
        YtDlpUpdateState.REJECTED -> stringResource(R.string.settings_ytdlp_state_rejected_detail)
        YtDlpUpdateState.FAILED -> stringResource(R.string.settings_ytdlp_state_failed_detail)
    }
    val isBusy = state.isYtDlpOperationBusy
    val container = when (state.updateState) {
        YtDlpUpdateState.FAILED -> MaterialTheme.colorScheme.errorContainer
        YtDlpUpdateState.AVAILABLE -> MaterialTheme.colorScheme.primaryContainer
        YtDlpUpdateState.UP_TO_DATE,
        YtDlpUpdateState.ROLLED_BACK -> MaterialTheme.colorScheme.tertiaryContainer
        else -> MaterialTheme.colorScheme.surfaceContainer
    }
    val content = when (state.updateState) {
        YtDlpUpdateState.FAILED -> MaterialTheme.colorScheme.onErrorContainer
        YtDlpUpdateState.AVAILABLE -> MaterialTheme.colorScheme.onPrimaryContainer
        YtDlpUpdateState.UP_TO_DATE,
        YtDlpUpdateState.ROLLED_BACK -> MaterialTheme.colorScheme.onTertiaryContainer
        else -> MaterialTheme.colorScheme.onSurface
    }

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .semantics { liveRegion = LiveRegionMode.Polite },
        shape = MaterialTheme.shapes.medium,
        color = container,
        contentColor = content,
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (isBusy) {
                CircularProgressIndicator(
                    modifier = Modifier.size(24.dp),
                    strokeWidth = 2.5.dp,
                    color = content,
                )
            } else {
                Icon(
                    imageVector = state.updateState.icon,
                    contentDescription = null,
                    modifier = Modifier.size(24.dp),
                )
            }
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = detail,
                    style = MaterialTheme.typography.bodySmall,
                    color = content.copy(alpha = 0.78f),
                )
            }
        }
    }
}

@Composable
private fun YtDlpRollbackConfirmationDialog(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    AlertDialog(
        onDismissRequest = { onAction(MobileUiAction.DismissYtDlpRollback) },
        icon = {
            Icon(imageVector = Icons.Rounded.Restore, contentDescription = null)
        },
        title = {
            Text(
                text = stringResource(R.string.settings_ytdlp_restore_title),
                fontWeight = FontWeight.Bold,
            )
        },
        text = {
            Text(
                stringResource(
                    R.string.settings_ytdlp_restore_message,
                    state.previousYtDlpVersion
                        ?: stringResource(R.string.settings_ytdlp_word_previous),
                    state.ytDlpVersion
                        ?: stringResource(R.string.settings_ytdlp_word_current),
                ),
            )
        },
        confirmButton = {
            Button(onClick = { onAction(MobileUiAction.ConfirmYtDlpRollback) }) {
                Text(stringResource(R.string.settings_restore))
            }
        },
        dismissButton = {
            TextButton(onClick = { onAction(MobileUiAction.DismissYtDlpRollback) }) {
                Text(stringResource(R.string.action_cancel))
            }
        },
    )
}

@Composable
private fun AppInfoCard(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
    onImportSettings: () -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            SectionTitle(
                title = stringResource(R.string.settings_about),
                supportingText = stringResource(R.string.settings_about_support),
                icon = Icons.Rounded.Info,
            )

            Surface(
                shape = MaterialTheme.shapes.medium,
                color = MaterialTheme.colorScheme.primaryContainer,
                contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(14.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        imageVector = Icons.Rounded.Download,
                        contentDescription = null,
                        modifier = Modifier.size(25.dp),
                    )
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "MediaDownloader",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                        )
                        Text(
                            text = stringResource(R.string.settings_version_format, state.appVersion),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.76f),
                        )
                        Text(
                            text = stringResource(R.string.settings_copyright),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.76f),
                        )
                    }
                }
            }

            TextButton(
                onClick = { onAction(MobileUiAction.ShareDiagnostics) },
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 50.dp),
            ) {
                Icon(
                    imageVector = Icons.Rounded.BugReport,
                    contentDescription = null,
                    modifier = Modifier.size(21.dp),
                )
                Text(
                    text = stringResource(R.string.settings_share_diagnostics),
                    modifier = Modifier.padding(start = 9.dp),
                )
            }

            Surface(
                shape = MaterialTheme.shapes.medium,
                color = MaterialTheme.colorScheme.surfaceContainer,
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 14.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text(
                        text = stringResource(R.string.settings_backup_title),
                        style = MaterialTheme.typography.titleSmall,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                    Text(
                        text = stringResource(R.string.settings_backup_export_support),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = stringResource(R.string.settings_backup_restore_support),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        OutlinedButton(
                            onClick = { onAction(MobileUiAction.ExportSettings) },
                            modifier = Modifier
                                .weight(1f)
                                .heightIn(min = 50.dp),
                        ) {
                            Icon(
                                imageVector = Icons.Rounded.Backup,
                                contentDescription = null,
                                modifier = Modifier.size(20.dp),
                            )
                            Text(
                                text = stringResource(R.string.settings_backup_export),
                                modifier = Modifier.padding(start = 9.dp),
                            )
                        }
                        OutlinedButton(
                            onClick = onImportSettings,
                            modifier = Modifier
                                .weight(1f)
                                .heightIn(min = 50.dp),
                        ) {
                            Icon(
                                imageVector = Icons.Rounded.SettingsBackupRestore,
                                contentDescription = null,
                                modifier = Modifier.size(20.dp),
                            )
                            Text(
                                text = stringResource(R.string.settings_backup_restore),
                                modifier = Modifier.padding(start = 9.dp),
                            )
                        }
                    }
                }
            }

            Surface(
                shape = MaterialTheme.shapes.medium,
                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f),
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    SectionTitle(
                        title = stringResource(R.string.settings_support_title),
                        supportingText = stringResource(R.string.settings_support_description),
                        icon = Icons.Rounded.Favorite,
                    )
                    val pixQrCode = remember { createQrCode(SupportConfig.PIX_PAYLOAD) }
                    Surface(
                        modifier = Modifier.size(196.dp),
                        shape = RoundedCornerShape(14.dp),
                        color = Color.White,
                    ) {
                        Box(
                            modifier = Modifier.padding(12.dp),
                            contentAlignment = Alignment.Center,
                        ) {
                            Image(
                                bitmap = pixQrCode,
                                contentDescription = stringResource(R.string.settings_pix_qr_cd),
                                modifier = Modifier.fillMaxWidth(),
                            )
                        }
                    }
                    Text(
                        text = stringResource(R.string.settings_pix_scan_hint),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        text = stringResource(R.string.settings_pix_key_label),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.Bold,
                    )
                    SelectionContainer {
                        Text(
                            text = SupportConfig.PIX_KEY,
                            style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                        )
                    }
                    Button(
                        onClick = { onAction(MobileUiAction.CopySupportPixPayload) },
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 52.dp),
                    ) {
                        Icon(Icons.Rounded.ContentCopy, contentDescription = null)
                        Text(
                            text = stringResource(R.string.settings_pix_copy_payload),
                            modifier = Modifier.padding(start = 9.dp),
                        )
                    }
                    OutlinedButton(
                        onClick = { onAction(MobileUiAction.CopySupportPixKey) },
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 52.dp),
                    ) {
                        Icon(Icons.Rounded.ContentCopy, contentDescription = null)
                        Text(
                            text = stringResource(R.string.settings_pix_copy_key),
                            modifier = Modifier.padding(start = 9.dp),
                        )
                    }
                    Text(
                        text = stringResource(R.string.settings_pix_warning),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                    Text(
                        text = stringResource(R.string.settings_pix_free_note),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            LegalButton(
                label = stringResource(R.string.legal_responsible_use_title),
                icon = Icons.Rounded.Security,
                onClick = {
                    onAction(MobileUiAction.OpenLegalDocument(LegalDocument.RESPONSIBLE_USE))
                },
            )
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f))
            LegalButton(
                label = stringResource(R.string.legal_privacy_title),
                icon = Icons.Rounded.PrivacyTip,
                onClick = { onAction(MobileUiAction.OpenLegalDocument(LegalDocument.PRIVACY)) },
            )
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f))
            LegalButton(
                label = stringResource(R.string.settings_license_mit),
                icon = Icons.Rounded.Info,
                onClick = {
                    onAction(MobileUiAction.OpenLegalDocument(LegalDocument.APPLICATION_LICENSE))
                },
            )
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f))
            LegalButton(
                label = stringResource(R.string.settings_license_third_party),
                icon = Icons.Rounded.Code,
                onClick = {
                    onAction(MobileUiAction.OpenLegalDocument(LegalDocument.OPEN_SOURCE_LICENSES))
                },
            )
        }
    }
}

@Composable
private fun LegalButton(
    label: String,
    icon: ImageVector,
    onClick: () -> Unit,
) {
    TextButton(
        onClick = onClick,
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = 50.dp),
        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 6.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(imageVector = icon, contentDescription = null, modifier = Modifier.size(21.dp))
            Text(
                text = label,
                modifier = Modifier.weight(1f),
                fontWeight = FontWeight.SemiBold,
            )
            Icon(
                imageVector = Icons.Rounded.ChevronRight,
                contentDescription = null,
                modifier = Modifier.size(20.dp),
            )
        }
    }
}

private val ThemePreference.icon: ImageVector
    get() = when (this) {
        ThemePreference.SYSTEM -> Icons.Rounded.BrightnessAuto
        ThemePreference.LIGHT -> Icons.Rounded.LightMode
        ThemePreference.DARK -> Icons.Rounded.DarkMode
        ThemePreference.AMOLED -> Icons.Rounded.DarkMode
    }

private val YtDlpUpdateState.icon: ImageVector
    get() = when (this) {
        YtDlpUpdateState.IDLE -> Icons.Rounded.Schedule
        YtDlpUpdateState.CHECKING -> Icons.Rounded.Search
        YtDlpUpdateState.AVAILABLE -> Icons.Rounded.SystemUpdate
        YtDlpUpdateState.UPDATING -> Icons.Rounded.Download
        YtDlpUpdateState.ROLLING_BACK -> Icons.Rounded.Restore
        YtDlpUpdateState.UP_TO_DATE -> Icons.Rounded.CheckCircle
        YtDlpUpdateState.ROLLED_BACK -> Icons.Rounded.Restore
        YtDlpUpdateState.REJECTED -> Icons.Rounded.Block
        YtDlpUpdateState.FAILED -> Icons.Rounded.ErrorOutline
    }

@Composable
private fun videoQualityChoices(): List<Pair<String, String>> = listOf(
    "best" to stringResource(R.string.settings_quality_best),
    "2160" to "2160p",
    "1440" to "1440p",
    "1080" to "1080p",
    "720" to "720p",
    "480" to "480p",
    "360" to "360p",
    "240" to "240p",
)

@Composable
private fun parallelDownloadChoices(): List<Pair<String, String>> =
    listOf(1, 2, 3).map { count ->
        count.toString() to pluralStringResource(
            R.plurals.settings_parallel_downloads_count,
            count,
            count,
        )
    }

private val VIDEO_FORMAT_CHOICES = listOf(
    "mp4" to "MP4",
    "mkv" to "MKV",
    "webm" to "WEBM",
)

private val AUDIO_QUALITY_CHOICES = listOf(
    "320" to "320 kbps",
    "256" to "256 kbps",
    "192" to "192 kbps",
    "128" to "128 kbps",
)

private val AUDIO_FORMAT_CHOICES = listOf(
    "mp3" to "MP3",
    "m4a" to "M4A",
    "opus" to "OPUS",
    "flac" to "FLAC",
    "wav" to "WAV",
)
