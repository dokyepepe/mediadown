package com.mediadownloader.mobile.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Download
import androidx.compose.material.icons.rounded.FolderOpen
import androidx.compose.material.icons.rounded.History
import androidx.compose.material.icons.rounded.Home
import androidx.compose.material.icons.rounded.QrCode2
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

private val APPLICATION_LICENSE_TEXT = """
    MIT License

    Copyright (c) 2026 Pietro Ferreira

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
""".trimIndent()

@Composable
fun MediaDownloaderApp(
    controller: MobileUiController,
    modifier: Modifier = Modifier,
    thumbnail: ThumbnailRenderer = { url, referer, description, thumbnailModifier ->
        DefaultThumbnail(url, referer, description, thumbnailModifier)
    },
) {
    val state by controller.state.collectAsStateWithLifecycle()
    MediaDownloaderApp(
        state = state,
        onAction = controller::onAction,
        modifier = modifier,
        thumbnail = thumbnail,
    )
}

@Composable
fun MediaDownloaderApp(
    state: MobileUiState,
    onAction: (MobileUiAction) -> Unit,
    modifier: Modifier = Modifier,
    thumbnail: ThumbnailRenderer = { url, referer, description, thumbnailModifier ->
        DefaultThumbnail(url, referer, description, thumbnailModifier)
    },
) {
    MediaDownloaderTheme(preference = state.settings.theme) {
        val snackbarHostState = remember { SnackbarHostState() }
        val message = state.message

        state.legalDocument?.let { document ->
            LegalDocumentDialog(
                document = document,
                onDismiss = { onAction(MobileUiAction.DismissLegalDocument) },
            )
        }

        LaunchedEffect(message?.id) {
            if (message != null) {
                snackbarHostState.showSnackbar(message.text)
                onAction(MobileUiAction.DismissMessage(message.id))
            }
        }

        Scaffold(
            modifier = modifier,
            topBar = { MobileTopBar(selectedTab = state.selectedTab) },
            bottomBar = {
                MobileBottomBar(
                    selectedTab = state.selectedTab,
                    onTabSelected = { onAction(MobileUiAction.Navigate(it)) },
                )
            },
            snackbarHost = { SnackbarHost(snackbarHostState) },
            containerColor = MaterialTheme.colorScheme.background,
        ) { contentPadding ->
            when (state.selectedTab) {
                AppTab.HOME -> HomeScreen(
                    state = state.home,
                    onAction = onAction,
                    thumbnail = thumbnail,
                    modifier = Modifier.padding(contentPadding),
                )

                AppTab.SITE_FILES -> SiteFilesScreen(
                    state = state.siteFiles,
                    onAction = onAction,
                    modifier = Modifier.padding(contentPadding),
                )

                AppTab.QR_CODE -> QrCodeScreen(
                    state = state.qrCode,
                    onAction = onAction,
                    modifier = Modifier.padding(contentPadding),
                )

                AppTab.DOWNLOADS -> DownloadsScreen(
                    state = state.downloads,
                    onAction = onAction,
                    thumbnail = thumbnail,
                    modifier = Modifier.padding(contentPadding),
                )

                AppTab.HISTORY -> HistoryScreen(
                    state = state.history,
                    onAction = onAction,
                    thumbnail = thumbnail,
                    modifier = Modifier.padding(contentPadding),
                )

                AppTab.SETTINGS -> SettingsScreen(
                    state = state.settings,
                    onAction = onAction,
                    modifier = Modifier.padding(contentPadding),
                )
            }
        }
    }
}

@Composable
private fun LegalDocumentDialog(
    document: LegalDocument,
    onDismiss: () -> Unit,
) {
    val title = when (document) {
        LegalDocument.RESPONSIBLE_USE -> "Uso responsável"
        LegalDocument.PRIVACY -> "Privacidade"
        LegalDocument.APPLICATION_LICENSE -> "Licença do Media Downloader"
        LegalDocument.OPEN_SOURCE_LICENSES -> "Licenças de terceiros"
    }
    val text = when (document) {
        LegalDocument.RESPONSIBLE_USE ->
            "Baixe somente conteúdo próprio, em domínio público ou para o qual você tenha " +
                "autorização. O aplicativo não remove DRM e o usuário é responsável por " +
                "respeitar direitos autorais e os termos da plataforma de origem."

        LegalDocument.PRIVACY ->
            "Links, fila, preferências e histórico permanecem neste aparelho. O aplicativo " +
                "não possui conta, anúncios ou telemetria. A conexão de rede é usada apenas " +
                "para analisar e baixar a mídia ou os arquivos de sites solicitados e atualizar o yt-dlp."

        LegalDocument.APPLICATION_LICENSE -> APPLICATION_LICENSE_TEXT

        LegalDocument.OPEN_SOURCE_LICENSES ->
            "Este aplicativo inclui AndroidX, Kotlin, ZXing, yt-dlp, Python, FFmpeg e " +
                "youtubedl-android. Os componentes mantêm suas respectivas licenças de " +
                "código aberto; os avisos completos acompanham o código-fonte do projeto."
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = {
            BrandMark(modifier = Modifier.size(48.dp))
        },
        title = { Text(title, fontWeight = FontWeight.Bold) },
        text = {
            Text(
                text = text,
                modifier = Modifier.verticalScroll(rememberScrollState()),
            )
        },
        confirmButton = {
            Button(onClick = onDismiss) {
                Text("Fechar")
            }
        },
    )
}

@Composable
private fun MobileTopBar(selectedTab: AppTab) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceContainerLow.copy(alpha = 0.97f),
        tonalElevation = 1.dp,
        shadowElevation = 1.dp,
    ) {
        Row(
            modifier = Modifier
                .statusBarsPadding()
                .fillMaxWidth()
                .padding(horizontal = 18.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            BrandMark(modifier = Modifier.size(42.dp))
            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(start = 12.dp),
            ) {
                Text(
                    text = "MediaDownloader",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = "Seu conteúdo, no seu dispositivo",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                )
            }
            Surface(
                shape = RoundedCornerShape(999.dp),
                color = MaterialTheme.colorScheme.secondaryContainer,
                contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
            ) {
                Text(
                    text = selectedTab.label,
                    modifier = Modifier.padding(horizontal = 11.dp, vertical = 7.dp),
                    style = MaterialTheme.typography.labelMedium,
                )
            }
        }
    }
}

@Composable
private fun BrandMark(modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(
                Brush.linearGradient(
                    colors = listOf(
                        MaterialTheme.colorScheme.primary,
                        MaterialTheme.colorScheme.tertiary,
                    ),
                ),
            ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = Icons.Rounded.Download,
            contentDescription = null,
            modifier = Modifier.size(27.dp),
            tint = MaterialTheme.colorScheme.onPrimary,
        )
    }
}

@Composable
private fun MobileBottomBar(
    selectedTab: AppTab,
    onTabSelected: (AppTab) -> Unit,
) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.background)
            .navigationBarsPadding()
            .padding(horizontal = 12.dp, vertical = 8.dp),
    ) {
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(24.dp),
            color = MaterialTheme.colorScheme.surfaceContainerHigh,
            shadowElevation = 10.dp,
        ) {
            NavigationBar(
                modifier = Modifier.heightIn(min = 72.dp),
                containerColor = MaterialTheme.colorScheme.surfaceContainerHigh,
                tonalElevation = 0.dp,
                windowInsets = WindowInsets(0, 0, 0, 0),
            ) {
                AppTab.entries.forEach { tab ->
                    NavigationBarItem(
                        selected = selectedTab == tab,
                        onClick = { onTabSelected(tab) },
                        icon = {
                            Icon(
                                imageVector = tab.icon,
                                contentDescription = null,
                                modifier = Modifier.size(23.dp),
                            )
                        },
                        label = { Text(tab.label) },
                        alwaysShowLabel = true,
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = MaterialTheme.colorScheme.onPrimaryContainer,
                            selectedTextColor = MaterialTheme.colorScheme.primary,
                            indicatorColor = MaterialTheme.colorScheme.primaryContainer,
                            unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                            unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
                        ),
                    )
                }
            }
        }
    }
}

private val AppTab.icon: ImageVector
    get() = when (this) {
        AppTab.HOME -> Icons.Rounded.Home
        AppTab.SITE_FILES -> Icons.Rounded.FolderOpen
        AppTab.QR_CODE -> Icons.Rounded.QrCode2
        AppTab.DOWNLOADS -> Icons.Rounded.Download
        AppTab.HISTORY -> Icons.Rounded.History
        AppTab.SETTINGS -> Icons.Rounded.Settings
    }
