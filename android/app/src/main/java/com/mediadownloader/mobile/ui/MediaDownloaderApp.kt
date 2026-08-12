package com.mediadownloader.mobile.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@Composable
fun MediaDownloaderApp(
    controller: MobileUiController,
    modifier: Modifier = Modifier,
    thumbnail: ThumbnailRenderer = { url, description, thumbnailModifier ->
        DefaultThumbnail(url, description, thumbnailModifier)
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
    thumbnail: ThumbnailRenderer = { url, description, thumbnailModifier ->
        DefaultThumbnail(url, description, thumbnailModifier)
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
            topBar = { MobileTopBar() },
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
        LegalDocument.OPEN_SOURCE_LICENSES -> "Licenças de código aberto"
    }
    val text = when (document) {
        LegalDocument.RESPONSIBLE_USE ->
            "Baixe somente conteúdo próprio, em domínio público ou para o qual você tenha " +
                "autorização. O aplicativo não remove DRM e o usuário é responsável por " +
                "respeitar direitos autorais e os termos da plataforma de origem."

        LegalDocument.PRIVACY ->
            "Links, fila, preferências e histórico permanecem neste aparelho. O aplicativo " +
                "não possui conta, anúncios ou telemetria. A conexão de rede é usada apenas " +
                "para analisar e baixar a mídia solicitada e atualizar o yt-dlp."

        LegalDocument.OPEN_SOURCE_LICENSES ->
            "Este aplicativo inclui AndroidX, Kotlin, yt-dlp, Python, FFmpeg e " +
                "youtubedl-android. Os componentes mantêm suas respectivas licenças de " +
                "código aberto; os avisos completos acompanham o código-fonte do projeto."
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Text(text) },
        confirmButton = {
            Button(onClick = onDismiss) {
                Text("Fechar")
            }
        },
    )
}

@Composable
private fun MobileTopBar() {
    Surface(
        color = MaterialTheme.colorScheme.surface,
        tonalElevation = 2.dp,
    ) {
        Row(
            modifier = Modifier
                .statusBarsPadding()
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Surface(
                modifier = Modifier.size(38.dp),
                shape = RoundedCornerShape(12.dp),
                color = MaterialTheme.colorScheme.primary,
                contentColor = MaterialTheme.colorScheme.onPrimary,
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Text(
                        text = "⇩",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.clearAndSetSemantics { },
                    )
                }
            }
            Text(
                text = "MediaDownloader",
                modifier = Modifier.padding(start = 12.dp),
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}

@Composable
private fun MobileBottomBar(
    selectedTab: AppTab,
    onTabSelected: (AppTab) -> Unit,
) {
    NavigationBar {
        AppTab.entries.forEach { tab ->
            NavigationBarItem(
                selected = selectedTab == tab,
                onClick = { onTabSelected(tab) },
                icon = {
                    Text(
                        text = tab.glyph,
                        style = MaterialTheme.typography.titleMedium,
                        modifier = Modifier.clearAndSetSemantics { },
                    )
                },
                label = { Text(tab.label) },
                alwaysShowLabel = true,
            )
        }
    }
}
