package com.mediadownloader.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Test

class HistoryCsvTest {

    private fun row(
        id: String = "abc123",
        title: String = "Música legal",
        fileName: String = "musica.mp3",
        sizeBytes: Long? = 1_234L,
        completedAtIso: String? = "2026-09-20T10:00:00Z",
        sourceUrl: String = "https://example.com/musica",
    ) = HistoryCsvRow(
        id = id,
        title = title,
        fileName = fileName,
        sizeBytes = sizeBytes,
        completedAtIso = completedAtIso,
        sourceUrl = sourceUrl,
        mimeType = "audio/mpeg",
    )

    @Test
    fun headerIsAlwaysTheFirstLine() {
        val csv = historyToCsv(emptyList())
        val firstLine = csv.lineSequence().first()
        assertEquals("id,título,arquivo,tamanho_bytes,concluído_em,url,mime", firstLine)
    }

    @Test
    fun simpleRowIsNotQuoted() {
        val csv = historyToCsv(listOf(row()))
        val line = csv.lineSequence().drop(1).first()
        assertEquals(
            "abc123,Música legal,musica.mp3,1234,2026-09-20T10:00:00Z,https://example.com/musica,audio/mpeg",
            line,
        )
    }

    @Test
    fun nullOptionalsBecomeEmptyColumns() {
        val csv = historyToCsv(listOf(row(sizeBytes = null, completedAtIso = null)))
        assert(csv.lineSequence().any { it == "abc123,Música legal,musica.mp3,,,https://example.com/musica,audio/mpeg" })
    }

    @Test
    fun titleWithCommaAndQuotesIsQuotedWithEscaping() {
        val csv = historyToCsv(listOf(row(title = "Música, \"Top\" \n 10")))
        assertEquals(
            "id,título,arquivo,tamanho_bytes,concluído_em,url,mime\n" +
                "abc123,\"Música, \"\"Top\"\" \n 10\",musica.mp3,1234,2026-09-20T10:00:00Z,https://example.com/musica,audio/mpeg",
            csv,
        )
    }

    @Test
    fun newlineSeperatedRowPerEntry() {
        val csv = historyToCsv(listOf(row(id = "a"), row(id = "b")))
        assertEquals(3, csv.lineSequence().count())
    }
}