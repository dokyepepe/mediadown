package com.mediadownloader.mobile.data

/** A single CSV row for the exported download history. */
data class HistoryCsvRow(
    val id: String,
    val title: String,
    val fileName: String,
    val sizeBytes: Long?,
    val completedAtIso: String?,
    val sourceUrl: String,
    val mimeType: String?,
)

/**
 * Pure CSV builder for the export-history feature. Quoting follows RFC 4180 so
 * titles that contain commas, quotes or line breaks survive a round trip in a
 * spreadsheet.
 */
fun historyToCsv(rows: List<HistoryCsvRow>): String {
    val header = listOf("id", "título", "arquivo", "tamanho_bytes", "concluído_em", "url", "mime")
    val lines = buildList {
        add(header)
        addAll(rows.map {
            listOf(
                it.id,
                it.title,
                it.fileName,
                it.sizeBytes?.toString().orEmpty(),
                it.completedAtIso.orEmpty(),
                it.sourceUrl,
                it.mimeType.orEmpty(),
            )
        })
    }
    return lines.joinToString("\n") { row -> row.joinToString(",") { field -> csvField(field) } }
}

internal fun csvField(field: String): String =
    if (field.any { it == ',' || it == '"' || it == '\n' || it == '\r' }) {
        "\"" + field.replace("\"", "\"\"") + "\""
    } else {
        field
    }