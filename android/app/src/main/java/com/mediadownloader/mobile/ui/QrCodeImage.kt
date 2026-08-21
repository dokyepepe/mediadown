package com.mediadownloader.mobile.ui

import android.graphics.Bitmap
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel

internal data class QrCodePixels(
    val size: Int,
    val values: IntArray,
)

internal fun createQrCodePixels(value: String, size: Int = 1024): QrCodePixels {
    require(value.isNotBlank()) { "O conteúdo do QR Code não pode estar vazio" }
    require(size >= MIN_QR_CODE_SIZE) { "O QR Code precisa ter pelo menos $MIN_QR_CODE_SIZE pixels" }
    val hints = mapOf(
        EncodeHintType.CHARACTER_SET to Charsets.UTF_8.name(),
        EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.M,
        EncodeHintType.MARGIN to QUIET_ZONE_MODULES,
    )
    val matrix = QRCodeWriter().encode(value, BarcodeFormat.QR_CODE, size, size, hints)
    val pixels = IntArray(size * size)
    for (y in 0 until size) {
        val row = y * size
        for (x in 0 until size) {
            pixels[row + x] = if (matrix[x, y]) QR_BLACK else QR_WHITE
        }
    }
    return QrCodePixels(size = size, values = pixels)
}

internal fun createQrCodeBitmap(value: String, size: Int = 1024): Bitmap {
    val qrCode = createQrCodePixels(value, size)
    return Bitmap.createBitmap(qrCode.values, qrCode.size, qrCode.size, Bitmap.Config.ARGB_8888)
}

internal fun createQrCode(value: String, size: Int = 1024): ImageBitmap =
    createQrCodeBitmap(value, size).asImageBitmap()

internal const val QR_BLACK: Int = 0xFF000000.toInt()
internal const val QR_WHITE: Int = 0xFFFFFFFF.toInt()
private const val QUIET_ZONE_MODULES = 4
private const val MIN_QR_CODE_SIZE = 256
