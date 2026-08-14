package com.mediadownloader.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.OpenInNew
import androidx.compose.material.icons.rounded.Cancel
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Collections
import androidx.compose.material.icons.rounded.ContentPaste
import androidx.compose.material.icons.rounded.Description
import androidx.compose.material.icons.rounded.FileDownload
import androidx.compose.material.icons.rounded.Image
import androidx.compose.material.icons.rounded.Link
import androidx.compose.material.icons.rounded.PictureAsPdf
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ElevatedFilterChip
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

@Composable
fun SiteFilesScreen(
    state: SiteFilesUiState,
    onAction: (MobileUiAction) -> Unit,
    modifier: Modifier = Modifier,
) {
    ScreenContainer(modifier) {
        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 20.dp, vertical = 24.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item {
                ScreenHeading(
                    eyebrow = "PDFs e imagens",
                    title = "Arquivos do site",
                    supportingText = "Analise uma página, escolha os arquivos encontrados e salve em Downloads.",
                    icon = Icons.Rounded.Collections,
                )
            }

            item {
                SiteScanCard(state, onAction)
            }

            if (state.pageTitle != null) {
                item {
                    SiteResultHeader(state, onAction)
                }
            }

            if (state.items.isEmpty()) {
                item {
                    EmptyState(
                        icon = if (state.pageTitle == null) Icons.Rounded.Description else Icons.Rounded.Search,
                        title = if (state.pageTitle == null) {
                            "Pronto para investigar"
                        } else {
                            "Nenhum arquivo público encontrado"
                        },
                        supportingText = if (state.pageTitle == null) {
                            "Funciona com PDFs vinculados ou incorporados, imagens responsivas e URLs diretas."
                        } else {
                            "Alguns sites montam o conteúdo apenas com JavaScript ou exigem login."
                        },
                    )
                }
            } else {
                items(state.items, key = SiteFileUi::id) { item ->
                    SiteFileCard(item, state.isDownloading, onAction)
                }

                item {
                    if (state.isDownloading) {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            LinearProgressIndicator(
                                progress = {
                                    if (state.totalDownloads > 0) {
                                        state.completedDownloads.toFloat() / state.totalDownloads
                                    } else 0f
                                },
                                modifier = Modifier.fillMaxWidth(),
                            )
                            OutlinedButton(
                                onClick = { onAction(MobileUiAction.CancelSiteFileDownloads) },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .heightIn(min = 52.dp),
                            ) {
                                Icon(Icons.Rounded.Cancel, contentDescription = null)
                                Spacer(Modifier.size(8.dp))
                                Text("Cancelar downloads")
                            }
                        }
                    } else {
                        Button(
                            onClick = { onAction(MobileUiAction.DownloadSelectedSiteFiles) },
                            enabled = state.canDownload,
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 56.dp),
                        ) {
                            Icon(Icons.Rounded.FileDownload, contentDescription = null)
                            Spacer(Modifier.size(9.dp))
                            Text(
                                if (state.selectedCount == 1) {
                                    "Baixar 1 arquivo"
                                } else {
                                    "Baixar ${state.selectedCount} arquivos"
                                },
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SiteScanCard(
    state: SiteFilesUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
            SectionTitle(
                title = "Página para analisar",
                supportingText = "Vídeo e áudio continuam no fluxo Início; aqui entram somente documentos e imagens.",
                icon = Icons.Rounded.Link,
            )
            OutlinedTextField(
                value = state.url,
                onValueChange = { onAction(MobileUiAction.SiteUrlChanged(it)) },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("URL do site") },
                placeholder = { Text("https://site.com/documentos") },
                leadingIcon = { Icon(Icons.Rounded.Link, contentDescription = null) },
                supportingText = state.urlError?.let { error -> { Text(error) } },
                isError = state.urlError != null,
                enabled = !state.isScanning && !state.isDownloading,
                maxLines = 3,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Uri,
                    imeAction = ImeAction.Go,
                ),
                keyboardActions = KeyboardActions(
                    onGo = {
                        if (state.canScan) onAction(MobileUiAction.ScanSiteFiles)
                    },
                ),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                ElevatedFilterChip(
                    selected = state.includePdfs,
                    onClick = {
                        onAction(MobileUiAction.SetSiteIncludePdfs(!state.includePdfs))
                    },
                    enabled = !state.isScanning && !state.isDownloading,
                    leadingIcon = { Icon(Icons.Rounded.PictureAsPdf, contentDescription = null) },
                    label = { Text("PDFs") },
                )
                ElevatedFilterChip(
                    selected = state.includeImages,
                    onClick = {
                        onAction(MobileUiAction.SetSiteIncludeImages(!state.includeImages))
                    },
                    enabled = !state.isScanning && !state.isDownloading,
                    leadingIcon = { Icon(Icons.Rounded.Image, contentDescription = null) },
                    label = { Text("Imagens") },
                )
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                FilledTonalButton(
                    onClick = { onAction(MobileUiAction.PasteSiteUrl) },
                    enabled = !state.isScanning && !state.isDownloading,
                    modifier = Modifier
                        .weight(1f)
                        .heightIn(min = 52.dp),
                ) {
                    Icon(Icons.Rounded.ContentPaste, contentDescription = null)
                    Spacer(Modifier.size(7.dp))
                    Text("Colar")
                }
                Button(
                    onClick = { onAction(MobileUiAction.ScanSiteFiles) },
                    enabled = state.canScan,
                    modifier = Modifier
                        .weight(1.45f)
                        .heightIn(min = 52.dp),
                ) {
                    if (state.isScanning) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(19.dp),
                            strokeWidth = 2.dp,
                            color = MaterialTheme.colorScheme.onPrimary,
                        )
                    } else {
                        Icon(Icons.Rounded.Search, contentDescription = null)
                    }
                    Spacer(Modifier.size(8.dp))
                    Text(if (state.isScanning) "Analisando…" else "Analisar")
                }
            }
        }
    }
}

@Composable
private fun SiteResultHeader(
    state: SiteFilesUiState,
    onAction: (MobileUiAction) -> Unit,
) {
    SectionCard {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            SectionTitle(
                title = state.pageTitle.orEmpty(),
                supportingText = "${state.items.count { it.kind == SiteFileKindUi.PDF }} PDF(s) • " +
                    "${state.items.count { it.kind == SiteFileKindUi.IMAGE }} imagem(ns)",
                icon = Icons.Rounded.Description,
            )
            if (state.items.isNotEmpty() && !state.isDownloading) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                ) {
                    TextButton(onClick = { onAction(MobileUiAction.SelectAllSiteFiles(true)) }) {
                        Text("Selecionar todos")
                    }
                    TextButton(onClick = { onAction(MobileUiAction.SelectAllSiteFiles(false)) }) {
                        Text("Limpar")
                    }
                }
            }
        }
    }
}

@Composable
private fun SiteFileCard(
    item: SiteFileUi,
    downloadsBusy: Boolean,
    onAction: (MobileUiAction) -> Unit,
) {
    val canSelect = !downloadsBusy && item.status != SiteFileStatus.SAVED
    SectionCard(
        modifier = Modifier.toggleable(
            value = item.selected,
            enabled = canSelect,
            role = Role.Checkbox,
            onValueChange = { onAction(MobileUiAction.ToggleSiteFile(item.id)) },
        ),
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(
                verticalAlignment = Alignment.Top,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Checkbox(
                    checked = item.selected,
                    onCheckedChange = null,
                    enabled = canSelect,
                )
                DecorativeIcon(
                    icon = item.kind.icon,
                    modifier = Modifier
                        .size(44.dp)
                        .padding(8.dp),
                )
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(3.dp),
                ) {
                    Text(
                        text = item.name,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        text = item.sourceHost,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                SiteStatusPill(item.status)
            }
            item.progress?.let { progress ->
                LinearProgressIndicator(
                    progress = { progress },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            item.progressText?.let {
                Text(it, style = MaterialTheme.typography.bodySmall)
            }
            item.errorMessage?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
            if (item.savedUri != null) {
                FilledTonalButton(
                    onClick = { onAction(MobileUiAction.OpenSiteFile(item.id)) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.AutoMirrored.Rounded.OpenInNew, contentDescription = null)
                    Spacer(Modifier.size(8.dp))
                    Text("Abrir arquivo")
                }
            }
        }
    }
}

@Composable
private fun SiteStatusPill(status: SiteFileStatus) {
    val colors = MaterialTheme.colorScheme
    val container = when (status) {
        SiteFileStatus.READY -> colors.secondaryContainer
        SiteFileStatus.DOWNLOADING -> colors.primaryContainer
        SiteFileStatus.SAVED -> colors.tertiaryContainer
        SiteFileStatus.FAILED -> colors.errorContainer
    }
    val content = when (status) {
        SiteFileStatus.READY -> colors.onSecondaryContainer
        SiteFileStatus.DOWNLOADING -> colors.onPrimaryContainer
        SiteFileStatus.SAVED -> colors.onTertiaryContainer
        SiteFileStatus.FAILED -> colors.onErrorContainer
    }
    val icon = when (status) {
        SiteFileStatus.SAVED -> Icons.Rounded.CheckCircle
        SiteFileStatus.DOWNLOADING -> Icons.Rounded.FileDownload
        SiteFileStatus.FAILED -> Icons.Rounded.Cancel
        SiteFileStatus.READY -> null
    }
    StatusPill(status.label, container, content, icon = icon)
}

private val SiteFileKindUi.icon: ImageVector
    get() = when (this) {
        SiteFileKindUi.PDF -> Icons.Rounded.PictureAsPdf
        SiteFileKindUi.IMAGE -> Icons.Rounded.Image
    }
