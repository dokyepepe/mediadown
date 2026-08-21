package com.mediadownloader.mobile.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.OpenInNew
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Link
import androidx.compose.material.icons.rounded.QrCode2
import androidx.compose.material.icons.rounded.SaveAlt
import androidx.compose.material.icons.rounded.Share
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

@Composable
fun QrCodeScreen(
    state: QrCodeUiState,
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
                    eyebrow = "Compartilhar links",
                    title = "Gerar QR Code",
                    supportingText = "Transforme uma URL em QR Code sem enviar dados para a internet.",
                    icon = Icons.Rounded.QrCode2,
                )
            }

            item {
                SectionCard {
                    Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                        SectionTitle(
                            title = "URL do QR Code",
                            supportingText = "Use um endereço completo iniciado por http:// ou https://.",
                            icon = Icons.Rounded.Link,
                        )
                        OutlinedTextField(
                            value = state.url,
                            onValueChange = { onAction(MobileUiAction.QrCodeUrlChanged(it)) },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text("URL") },
                            placeholder = { Text("https://exemplo.com") },
                            leadingIcon = { Icon(Icons.Rounded.Link, contentDescription = null) },
                            supportingText = state.urlError?.let { error -> { Text(error) } },
                            isError = state.urlError != null,
                            maxLines = 3,
                            keyboardOptions = KeyboardOptions(
                                keyboardType = KeyboardType.Uri,
                                imeAction = ImeAction.Go,
                            ),
                            keyboardActions = KeyboardActions(
                                onGo = {
                                    if (state.canGenerate) onAction(MobileUiAction.GenerateQrCode)
                                },
                            ),
                        )
                        Button(
                            onClick = { onAction(MobileUiAction.GenerateQrCode) },
                            enabled = state.canGenerate,
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 56.dp),
                        ) {
                            Icon(Icons.Rounded.QrCode2, contentDescription = null)
                            Text("  Gerar QR Code")
                        }
                    }
                }
            }

            item {
                val image = remember(state.generatedUrl) {
                    state.generatedUrl?.let { value -> runCatching { createQrCode(value) }.getOrNull() }
                }
                SectionCard {
                    if (image == null) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 280.dp)
                                .padding(20.dp),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(
                                text = "O QR Code aparecerá aqui depois de gerar.",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                textAlign = TextAlign.Center,
                            )
                        }
                    } else {
                        Column(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.spacedBy(16.dp),
                        ) {
                            SectionTitle(
                                title = "QR Code pronto",
                                supportingText = "Imagem em alto contraste, gerada somente neste aparelho.",
                                icon = Icons.Rounded.CheckCircle,
                            )
                            Box(
                                modifier = Modifier
                                    .widthIn(max = 440.dp)
                                    .fillMaxWidth()
                                    .aspectRatio(1f)
                                    .border(2.dp, Color.Black, RoundedCornerShape(18.dp))
                                    .background(Color.White, RoundedCornerShape(18.dp))
                                    .clickable { onAction(MobileUiAction.OpenGeneratedQrCode) }
                                    .padding(24.dp),
                                contentAlignment = Alignment.Center,
                            ) {
                                Image(
                                    bitmap = image,
                                    contentDescription =
                                        "QR Code gerado para ${state.generatedUrl}. Toque para abrir.",
                                    modifier = Modifier.fillMaxSize(),
                                    contentScale = ContentScale.Fit,
                                    filterQuality = FilterQuality.None,
                                )
                            }
                            Text(
                                text = "Toque na imagem para ampliar ou use uma das opções abaixo.",
                                modifier = Modifier.fillMaxWidth(),
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                style = MaterialTheme.typography.bodySmall,
                                textAlign = TextAlign.Center,
                            )
                            Button(
                                onClick = { onAction(MobileUiAction.OpenGeneratedQrCode) },
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .heightIn(min = 52.dp),
                            ) {
                                Icon(Icons.AutoMirrored.Rounded.OpenInNew, contentDescription = null)
                                Text("  Abrir QR Code", fontWeight = FontWeight.SemiBold)
                            }
                            Column(
                                modifier = Modifier.fillMaxWidth(),
                                verticalArrangement = Arrangement.spacedBy(10.dp),
                            ) {
                                OutlinedButton(
                                    onClick = { onAction(MobileUiAction.SaveGeneratedQrCode) },
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .heightIn(min = 52.dp),
                                ) {
                                    Icon(Icons.Rounded.SaveAlt, contentDescription = null)
                                    Text("  Salvar PNG")
                                }
                                OutlinedButton(
                                    onClick = { onAction(MobileUiAction.ShareGeneratedQrCode) },
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .heightIn(min = 52.dp),
                                ) {
                                    Icon(Icons.Rounded.Share, contentDescription = null)
                                    Text("  Compartilhar")
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
