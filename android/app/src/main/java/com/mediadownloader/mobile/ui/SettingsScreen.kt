package com.mediadownloader.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
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
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item {
                ScreenHeading(
                    title = "Ajustes",
                    supportingText = "Personalize a aparência, o destino e as atualizações.",
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
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            SectionTitle(
                title = "Aparência",
                supportingText = "O tema Sistema acompanha o modo claro ou escuro do aparelho.",
            )
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                items(ThemePreference.entries, key = { it.name }) { theme ->
                    FilterChip(
                        selected = state.theme == theme,
                        onClick = { onAction(MobileUiAction.SetTheme(theme)) },
                        label = { Text(theme.label) },
                    )
                }
            }
        }
    }
}

@Composable
private fun StorageCard(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            SectionTitle(
                title = "Armazenamento",
                supportingText = "Os arquivos continuam no aparelho mesmo se o histórico for limpo.",
            )
            LabelValueRow(label = "Destino", value = state.downloadLocationLabel)
            if (state.canChooseDownloadLocation) {
                OutlinedButton(
                    onClick = { onAction(MobileUiAction.ChooseDownloadLocation) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Escolher pasta")
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
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            SectionTitle(
                title = "Compatibilidade com sites",
                supportingText = "O yt-dlp recebe correções frequentes para manter os extratores atualizados.",
            )

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
                    Text("Verificar automaticamente", style = MaterialTheme.typography.bodyLarge)
                    Text(
                        text = "No máximo uma vez por dia; você decide quando instalar",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(
                    checked = state.autoUpdateYtDlp,
                    onCheckedChange = { onAction(MobileUiAction.SetAutoUpdateYtDlp(it)) },
                    enabled = !isBusy,
                )
            }

            LabelValueRow(label = "Versão atual", value = state.ytDlpVersion ?: "Não identificada")
            state.previousYtDlpVersion?.let { version ->
                LabelValueRow(label = "Versão anterior", value = version)
            }

            UpdateStatus(state = state)

            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(
                    onClick = { onAction(MobileUiAction.CheckYtDlpUpdate) },
                    enabled = !isBusy,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Verificar atualização")
                }
                if (state.canInstallYtDlpUpdate) {
                    Button(
                        onClick = { onAction(MobileUiAction.UpdateYtDlp) },
                        enabled = !isBusy,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Atualizar agora")
                    }
                }
                if (state.canRollbackYtDlp) {
                    TextButton(
                        onClick = { onAction(MobileUiAction.RequestYtDlpRollback) },
                        enabled = !isBusy,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Restaurar versão anterior")
                    }
                }
            }
        }
    }
}

@Composable
private fun UpdateStatus(state: SettingsUiState) {
    val label = state.updateDetail ?: when (state.updateState) {
        YtDlpUpdateState.IDLE -> "Ainda não verificado nesta sessão."
        YtDlpUpdateState.CHECKING -> "Procurando atualização…"
        YtDlpUpdateState.AVAILABLE -> "Há uma atualização disponível."
        YtDlpUpdateState.UPDATING -> "Instalando atualização…"
        YtDlpUpdateState.ROLLING_BACK -> "Restaurando a versão anterior…"
        YtDlpUpdateState.UP_TO_DATE -> "Você já está usando a versão mais recente."
        YtDlpUpdateState.ROLLED_BACK -> "A versão anterior está ativa."
        YtDlpUpdateState.REJECTED -> "A versão problemática foi ignorada."
        YtDlpUpdateState.FAILED -> "Não foi possível verificar agora."
    }
    val color = when (state.updateState) {
        YtDlpUpdateState.FAILED -> MaterialTheme.colorScheme.error
        YtDlpUpdateState.AVAILABLE,
        YtDlpUpdateState.ROLLED_BACK -> MaterialTheme.colorScheme.primary
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (state.updateState == YtDlpUpdateState.CHECKING ||
            state.updateState == YtDlpUpdateState.UPDATING ||
            state.updateState == YtDlpUpdateState.ROLLING_BACK
        ) {
            CircularProgressIndicator(
                modifier = Modifier.size(20.dp),
                strokeWidth = 2.dp,
            )
        }
        Text(
            text = label,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodySmall,
            color = color,
        )
    }
}

@Composable
private fun YtDlpRollbackConfirmationDialog(
    state: SettingsUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    AlertDialog(
        onDismissRequest = { onAction(MobileUiAction.DismissYtDlpRollback) },
        title = { Text("Restaurar versão anterior?") },
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
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            SectionTitle(
                title = "Sobre e legal",
                supportingText = "Baixe apenas conteúdo que você tem permissão para salvar.",
            )
            LabelValueRow(label = "MediaDownloader", value = state.appVersion)

            LegalButton(
                label = "Uso responsável",
                onClick = {
                    onAction(MobileUiAction.OpenLegalDocument(LegalDocument.RESPONSIBLE_USE))
                },
            )
            LegalButton(
                label = "Privacidade",
                onClick = { onAction(MobileUiAction.OpenLegalDocument(LegalDocument.PRIVACY)) },
            )
            LegalButton(
                label = "Licenças de código aberto",
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
    onClick: () -> Unit,
) {
    TextButton(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(label, fontWeight = FontWeight.Medium)
            Text("›", style = MaterialTheme.typography.titleMedium)
        }
    }
}
