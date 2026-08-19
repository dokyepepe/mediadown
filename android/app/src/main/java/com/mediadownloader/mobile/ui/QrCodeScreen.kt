package com.mediadownloader.mobile.ui

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Link
import androidx.compose.material.icons.rounded.QrCode2
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.google.zxing.BarcodeFormat
import com.google.zxing.qrcode.QRCodeWriter

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
                    state.generatedUrl?.let { value -> createQrCode(value) }
                }
                SectionCard {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .aspectRatio(1f)
                            .background(Color.White, RoundedCornerShape(16.dp))
                            .padding(18.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        if (image == null) {
                            Text(
                                text = "O QR Code aparecerá aqui depois de gerar.",
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        } else {
                            Image(
                                bitmap = image,
                                contentDescription = "QR Code gerado para ${state.generatedUrl}",
                                modifier = Modifier.fillMaxWidth(),
                            )
                        }
                    }
                }
            }
        }
    }
}

private fun createQrCode(value: String, size: Int = 720): ImageBitmap {
    val matrix = QRCodeWriter().encode(value, BarcodeFormat.QR_CODE, size, size)
    val pixels = IntArray(size * size)
    for (y in 0 until size) {
        val row = y * size
        for (x in 0 until size) {
            pixels[row + x] = if (matrix[x, y]) 0xFF000000.toInt() else 0xFFFFFFFF.toInt()
        }
    }
    return Bitmap.createBitmap(pixels, size, size, Bitmap.Config.ARGB_8888).asImageBitmap()
}
