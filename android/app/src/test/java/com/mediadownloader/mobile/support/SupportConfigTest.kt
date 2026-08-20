package com.mediadownloader.mobile.support

import java.util.UUID
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SupportConfigTest {
    @Test
    fun suppliedPixKeyAndPayloadStayInSync() {
        assertEquals(SupportConfig.PIX_KEY, UUID.fromString(SupportConfig.PIX_KEY).toString())
        assertTrue(SupportConfig.PIX_PAYLOAD.contains(SupportConfig.PIX_KEY))
        assertEquals(
            SupportConfig.PIX_PAYLOAD.takeLast(4),
            crc16CcittFalse(SupportConfig.PIX_PAYLOAD.dropLast(4)),
        )
    }

    private fun crc16CcittFalse(value: String): String {
        var crc = 0xFFFF
        value.encodeToByteArray().forEach { byte ->
            crc = crc xor ((byte.toInt() and 0xFF) shl 8)
            repeat(8) {
                crc = if (crc and 0x8000 != 0) {
                    ((crc shl 1) xor 0x1021) and 0xFFFF
                } else {
                    (crc shl 1) and 0xFFFF
                }
            }
        }
        return crc.toString(16).uppercase().padStart(4, '0')
    }
}
