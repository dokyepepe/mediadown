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
    val isBusy = state.updateState == YtDlpUpdateState.CHECKING ||
        state.updateState == YtDlpUpdateState.UPDATING

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
                    Text("Atualização automática", style = MaterialTheme.typography.bodyLarge)
                    Text(
                        text = "Verificar ao abrir o aplicativo",
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

            state.ytDlpVersion?.let { version ->
                LabelValueRow(label = "Versão instalada", value = version)
            }

            UpdateStatus(state = state)

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                OutlinedButton(
                    onClick = { onAction(MobileUiAction.CheckYtDlpUpdate) },
                    enabled = !isBusy,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Verificar")
                }
                if (state.updateState == YtDlpUpdateState.AVAILABLE) {
                    Button(
                        onClick = { onAction(MobileUiAction.UpdateYtDlp) },
                        modifier = Modifier.weight(1f),
                    ) {
                        Text("Atualizar")
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
        YtDlpUpdateState.UP_TO_DATE -> "Você já está usando a versão mais recente."
        YtDlpUpdateState.FAILED -> "Não foi possível verificar agora."
    }
    val color = when (state.updateState) {
        YtDlpUpdateState.FAILED -> MaterialTheme.colorScheme.error
        YtDlpUpdateState.AVAILABLE -> MaterialTheme.colorScheme.primary
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (state.updateState == YtDlpUpdateState.CHECKING ||
            state.updateState == YtDlpUpdateState.UPDATING
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
