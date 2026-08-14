package com.mediadownloader.mobile.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Autorenew
import androidx.compose.material.icons.rounded.Block
import androidx.compose.material.icons.rounded.BrightnessAuto
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.ChevronRight
import androidx.compose.material.icons.rounded.Code
import androidx.compose.material.icons.rounded.DarkMode
import androidx.compose.material.icons.rounded.Download
import androidx.compose.material.icons.rounded.ErrorOutline
import androidx.compose.material.icons.rounded.Folder
import androidx.compose.material.icons.rounded.FolderOpen
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.Language
import androidx.compose.material.icons.rounded.LightMode
import androidx.compose.material.icons.rounded.Palette
import androidx.compose.material.icons.rounded.PrivacyTip
import androidx.compose.material.icons.rounded.Restore
import androidx.compose.material.icons.rounded.Schedule
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Security
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material.icons.rounded.SystemUpdate
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

@Composable
fun SettingsScreen(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
    modifier: Modifier = Modifier,
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
                    eyebrow = "Do seu jeito",
                    title = "Ajustes",
                    supportingText = "Controle aparência, armazenamento e compatibilidade em um só lugar.",
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
                YtDlpUpdateCard(state = state, onAction = onAction)
            }

            item {
                AppInfoCard(state = state, onAction = onAction)
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
                title = "Aparência",
                supportingText = "O modo Sistema acompanha automaticamente o seu aparelho.",
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
                text = theme.label,
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
                title = "Armazenamento",
                supportingText = "Limpar o histórico nunca apaga os arquivos salvos.",
                icon = Icons.Rounded.Folder,
            )
            Surface(
                shape = MaterialTheme.shapes.medium,
                color = MaterialTheme.colorScheme.surfaceContainer,
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(14.dp),
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
                            text = "Pasta de destino",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(
                            text = state.downloadLocationLabel,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.SemiBold,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
            if (state.canChooseDownloadLocation) {
                OutlinedButton(
                    onClick = { onAction(MobileUiAction.ChooseDownloadLocation) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 50.dp),
                ) {
                    Icon(
                        imageVector = Icons.Rounded.FolderOpen,
                        contentDescription = null,
                        modifier = Modifier.size(20.dp),
                    )
                    Text("Escolher pasta", modifier = Modifier.padding(start = 9.dp))
                }
            }
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
                title = "Compatibilidade com sites",
                supportingText = "O yt-dlp recebe correções frequentes para acompanhar mudanças nas plataformas.",
                icon = Icons.Rounded.Language,
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(9.dp),
            ) {
                VersionTile(
                    label = "Versão atual",
                    value = state.ytDlpVersion ?: "Não identificada",
                    modifier = Modifier.weight(1f),
                )
                state.availableYtDlpVersion?.let { version ->
                    VersionTile(
                        label = "Disponível",
                        value = version,
                        highlighted = true,
                        modifier = Modifier.weight(1f),
                    )
                }
            }

            state.previousYtDlpVersion?.let { version ->
                LabelValueRow(label = "Versão anterior", value = version)
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
                            text = "Verificar automaticamente",
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Text(
                            text = "No máximo uma vez por dia; você decide quando instalar",
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
                    Text("Verificar atualização", modifier = Modifier.padding(start = 9.dp))
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
                        Text("Atualizar agora", modifier = Modifier.padding(start = 9.dp))
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
                        Text("Restaurar versão anterior", modifier = Modifier.padding(start = 9.dp))
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
        YtDlpUpdateState.IDLE -> "Pronto para verificar"
        YtDlpUpdateState.CHECKING -> "Verificando compatibilidade"
        YtDlpUpdateState.AVAILABLE -> "Atualização disponível"
        YtDlpUpdateState.UPDATING -> "Instalando atualização"
        YtDlpUpdateState.ROLLING_BACK -> "Restaurando versão"
        YtDlpUpdateState.UP_TO_DATE -> "Tudo atualizado"
        YtDlpUpdateState.ROLLED_BACK -> "Versão restaurada"
        YtDlpUpdateState.REJECTED -> "Versão ignorada"
        YtDlpUpdateState.FAILED -> "Não foi possível verificar"
    }
    val detail = state.updateDetail ?: when (state.updateState) {
        YtDlpUpdateState.IDLE -> "Ainda não verificado nesta sessão."
        YtDlpUpdateState.CHECKING -> "Procurando uma versão mais recente…"
        YtDlpUpdateState.AVAILABLE -> "Uma versão mais recente está pronta para instalar."
        YtDlpUpdateState.UPDATING -> "Aguarde enquanto os componentes são atualizados…"
        YtDlpUpdateState.ROLLING_BACK -> "Aguarde enquanto a versão anterior é restaurada…"
        YtDlpUpdateState.UP_TO_DATE -> "Você já está usando a versão mais recente."
        YtDlpUpdateState.ROLLED_BACK -> "A versão anterior está ativa."
        YtDlpUpdateState.REJECTED -> "A versão problemática foi ignorada."
        YtDlpUpdateState.FAILED -> "Tente novamente quando sua conexão estiver estável."
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
        title = { Text("Restaurar versão anterior?", fontWeight = FontWeight.Bold) },
        text = {
            Text(
                "A versão ${state.previousYtDlpVersion ?: "anterior"} substituirá a " +
                    "${state.ytDlpVersion ?: "atual"}. Downloads em andamento terminarão antes da troca.",
            )
        },
        confirmButton = {
            Button(onClick = { onAction(MobileUiAction.ConfirmYtDlpRollback) }) {
                Text("Restaurar")
            }
        },
        dismissButton = {
            TextButton(onClick = { onAction(MobileUiAction.DismissYtDlpRollback) }) {
                Text("Cancelar")
            }
        },
    )
}

@Composable
private fun AppInfoCard(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            SectionTitle(
                title = "Sobre e legal",
                supportingText = "Transparência para baixar apenas o que você tem permissão para salvar.",
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
                            text = "Versão ${state.appVersion}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.76f),
                        )
                    }
                }
            }

            LegalButton(
                label = "Uso responsável",
                icon = Icons.Rounded.Security,
                onClick = {
                    onAction(MobileUiAction.OpenLegalDocument(LegalDocument.RESPONSIBLE_USE))
                },
            )
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f))
            LegalButton(
                label = "Privacidade",
                icon = Icons.Rounded.PrivacyTip,
                onClick = { onAction(MobileUiAction.OpenLegalDocument(LegalDocument.PRIVACY)) },
            )
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f))
            LegalButton(
                label = "Licenças de código aberto",
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
