package com.mediadownloader.mobile.data

import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

internal class DownloadDatabase(context: Context) :
    SQLiteOpenHelper(context.applicationContext, DATABASE_NAME, null, DATABASE_VERSION) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(CREATE_DOWNLOADS)
        db.execSQL(CREATE_HISTORY)
        db.execSQL("CREATE INDEX idx_downloads_state_created ON downloads(state, created_at)")
        db.execSQL("CREATE INDEX idx_history_completed ON history(completed_at DESC)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion < 2) {
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN audio_speed REAL NOT NULL DEFAULT 1.0",
            )
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN audio_pitch_semitones REAL NOT NULL DEFAULT 0.0",
            )
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN audio_volume_percent INTEGER NOT NULL DEFAULT 100",
            )
        }
        if (oldVersion < 3) {
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN audio_bass INTEGER NOT NULL DEFAULT 0",
            )
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN audio_echo INTEGER NOT NULL DEFAULT 0",
            )
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN audio_tremolo INTEGER NOT NULL DEFAULT 0",
            )
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN audio_normalize INTEGER NOT NULL DEFAULT 0",
            )
        }
        if (oldVersion < 4) {
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN trim_start_seconds REAL NOT NULL DEFAULT 0.0",
            )
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN trim_duration_seconds REAL",
            )
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN fade_in_seconds REAL NOT NULL DEFAULT 0.0",
            )
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN fade_out_seconds REAL NOT NULL DEFAULT 0.0",
            )
        }
        if (oldVersion < 5) {
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN editor_compatible INTEGER NOT NULL DEFAULT 0",
            )
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN rate_limit_kbps INTEGER NOT NULL DEFAULT 0",
            )
        }
        if (oldVersion < 6) {
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0",
            )
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN keep_partial_files INTEGER NOT NULL DEFAULT 0",
            )
            // Assigns a stable manual position to the rows created before the column existed.
            db.execSQL(
                """
                UPDATE downloads SET sort_order = (
                    SELECT COUNT(*) FROM downloads AS older
                    WHERE older.created_at < downloads.created_at
                       OR (older.created_at = downloads.created_at AND older.id < downloads.id)
                )
                """.trimIndent(),
            )
            db.execSQL("CREATE INDEX IF NOT EXISTS idx_downloads_state_order ON downloads(state, sort_order)")
        }
        if (oldVersion < 7) {
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN embed_metadata INTEGER NOT NULL DEFAULT 1",
            )
            db.execSQL(
                "ALTER TABLE downloads ADD COLUMN embed_thumbnail INTEGER NOT NULL DEFAULT 1",
            )
        }
    }

    fun upsertDownload(item: DownloadItem) {
        writableDatabase.insertWithOnConflict(
            "downloads",
            null,
            item.toValues(),
            SQLiteDatabase.CONFLICT_REPLACE,
        )
    }

    fun getDownload(id: String): DownloadItem? = readableDatabase.query(
        "downloads",
        null,
        "id = ?",
        arrayOf(id),
        null,
        null,
        null,
        "1",
    ).use { cursor -> if (cursor.moveToFirst()) cursor.toDownloadItem() else null }

    fun getNextQueuedDownload(): DownloadItem? = readableDatabase.query(
        "downloads",
        null,
        "state = ?",
        arrayOf(DownloadState.QUEUED.name),
        null,
        null,
        "sort_order ASC, created_at ASC",
        "1",
    ).use { cursor -> if (cursor.moveToFirst()) cursor.toDownloadItem() else null }

    /** Highest manual position currently in use, so new items land at the end. */
    fun maxSortOrder(): Int = readableDatabase.rawQuery(
        "SELECT IFNULL(MAX(sort_order), 0) FROM downloads",
        null,
    ).use { cursor -> if (cursor.moveToFirst()) cursor.getInt(0) else 0 }

    fun loadDownloads(): List<DownloadItem> = readableDatabase.query(
        "downloads",
        null,
        null,
        null,
        null,
        null,
        // The queue is shown in manual order; everything else stays by recency.
        "CASE WHEN state = 'QUEUED' THEN 0 ELSE 1 END ASC, " +
            "CASE WHEN state = 'QUEUED' THEN sort_order ELSE 0 END ASC, " +
            "created_at DESC",
    ).use { cursor -> buildList { while (cursor.moveToNext()) add(cursor.toDownloadItem()) } }

    fun deleteDownload(id: String) {
        writableDatabase.delete("downloads", "id = ?", arrayOf(id))
    }

    fun updateSortOrder(id: String, sortOrder: Int) {
        writableDatabase.update(
            "downloads",
            ContentValues().apply { put("sort_order", sortOrder) },
            "id = ?",
            arrayOf(id),
        )
    }

    fun deleteFinishedDownloads() {
        writableDatabase.delete(
            "downloads",
            "state IN (?, ?, ?)",
            arrayOf(
                DownloadState.COMPLETED.name,
                DownloadState.FAILED.name,
                DownloadState.CANCELLED.name,
            ),
        )
    }

    fun upsertHistory(item: HistoryItem) {
        writableDatabase.insertWithOnConflict(
            "history",
            null,
            item.toValues(),
            SQLiteDatabase.CONFLICT_REPLACE,
        )
    }

    fun loadHistory(): List<HistoryItem> = readableDatabase.query(
        "history",
        null,
        null,
        null,
        null,
        null,
        "completed_at DESC",
    ).use { cursor -> buildList { while (cursor.moveToNext()) add(cursor.toHistoryItem()) } }

    fun deleteHistory(id: String) {
        writableDatabase.delete("history", "id = ?", arrayOf(id))
    }

    fun deleteHistory(ids: Set<String>) {
        if (ids.isEmpty()) return
        val placeholders = ids.joinToString(",") { "?" }
        writableDatabase.delete("history", "id IN ($placeholders)", ids.toTypedArray())
    }

    fun clearHistory() {
        writableDatabase.delete("history", null, null)
    }

    private fun DownloadItem.toValues() = ContentValues().apply {
        put("id", id)
        put("source_url", sourceUrl)
        put("title", title)
        putNullable("source_name", sourceName)
        putNullable("thumbnail_url", thumbnailUrl)
        put("media_type", options.mediaType.name)
        putNullable("max_video_height", options.maxVideoHeight)
        put("video_container", options.videoContainer.name)
        put("editor_compatible", options.editorCompatible.asInt())
        put("rate_limit_kbps", options.rateLimitKbps)
        put("audio_format", options.audioFormat.name)
        put("audio_bitrate", options.audioBitrateKbps)
        putNullable("format_id", options.formatId)
        put("download_playlist", options.downloadPlaylist.asInt())
        put("include_subtitles", options.includeSubtitles.asInt())
        put("subtitle_languages", options.subtitleLanguages.joinToString(LANGUAGE_SEPARATOR))
        put("embed_metadata", options.embedMetadata.asInt())
        put("embed_thumbnail", options.embedThumbnail.asInt())
        put("audio_speed", options.audioSpeed)
        put("audio_pitch_semitones", options.audioPitchSemitones)
        put("audio_volume_percent", options.audioVolumePercent)
        put("audio_bass", options.audioBass.asInt())
        put("audio_echo", options.audioEcho.asInt())
        put("audio_tremolo", options.audioTremolo.asInt())
        put("audio_normalize", options.audioNormalize.asInt())
        put("trim_start_seconds", options.trimStartSeconds)
        putNullable("trim_duration_seconds", options.trimDurationSeconds)
        put("fade_in_seconds", options.fadeInSeconds)
        put("fade_out_seconds", options.fadeOutSeconds)
        put("state", state.name)
        put("progress", progress.coerceIn(0, 100))
        putNullable("eta_seconds", etaSeconds)
        putNullable("status_line", statusLine)
        putNullable("error_message", errorMessage)
        putNullable("output_uri", outputUri)
        putNullable("output_file_name", outputFileName)
        putNullable("output_mime_type", outputMimeType)
        putNullable("output_size", outputSizeBytes)
        put("retry_count", retryCount)
        put("created_at", createdAtEpochMs)
        put("updated_at", updatedAtEpochMs)
        putNullable("completed_at", completedAtEpochMs)
        put("sort_order", sortOrder)
        put("keep_partial_files", keepPartialFiles.asInt())
    }

    private fun HistoryItem.toValues() = ContentValues().apply {
        put("id", id)
        put("download_id", downloadId)
        put("source_url", sourceUrl)
        put("title", title)
        put("file_uri", fileUri)
        put("file_name", fileName)
        put("mime_type", mimeType)
        put("size_bytes", sizeBytes)
        putNullable("thumbnail_url", thumbnailUrl)
        put("completed_at", completedAtEpochMs)
    }

    private fun Cursor.toDownloadItem(): DownloadItem {
        val options = DownloadOptions(
            mediaType = enumOrDefault(string("media_type"), MediaType.VIDEO),
            maxVideoHeight = nullableInt("max_video_height"),
            videoContainer = enumOrDefault(string("video_container"), VideoContainer.MP4),
            editorCompatible = int("editor_compatible") != 0,
            rateLimitKbps = int("rate_limit_kbps").coerceAtLeast(0),
            audioFormat = enumOrDefault(string("audio_format"), AudioFormat.MP3),
            audioBitrateKbps = int("audio_bitrate").coerceIn(32, 320),
            formatId = nullableString("format_id"),
            downloadPlaylist = int("download_playlist") != 0,
            includeSubtitles = int("include_subtitles") != 0,
            subtitleLanguages = string("subtitle_languages")
                .split(LANGUAGE_SEPARATOR)
                .filter(String::isNotBlank),
            embedMetadata = int("embed_metadata") != 0,
            embedThumbnail = int("embed_thumbnail") != 0,
            audioSpeed = float("audio_speed").coerceIn(
                AudioEffects.MIN_SPEED,
                AudioEffects.MAX_SPEED,
            ),
            audioPitchSemitones = float("audio_pitch_semitones").coerceIn(
                AudioEffects.MIN_SEMITONES,
                AudioEffects.MAX_SEMITONES,
            ),
            audioVolumePercent = int("audio_volume_percent").coerceIn(
                AudioEffects.MIN_VOLUME_PERCENT,
                AudioEffects.MAX_VOLUME_PERCENT,
            ),
            audioBass = int("audio_bass") != 0,
            audioEcho = int("audio_echo") != 0,
            audioTremolo = int("audio_tremolo") != 0,
            audioNormalize = int("audio_normalize") != 0,
            trimStartSeconds = float("trim_start_seconds").coerceAtLeast(0f),
            trimDurationSeconds = nullableFloat("trim_duration_seconds")
                ?.takeIf { it > 0f },
            fadeInSeconds = float("fade_in_seconds").coerceAtLeast(0f),
            fadeOutSeconds = float("fade_out_seconds").coerceAtLeast(0f),
        )
        return DownloadItem(
            id = string("id"),
            sourceUrl = string("source_url"),
            title = string("title"),
            sourceName = nullableString("source_name"),
            thumbnailUrl = nullableString("thumbnail_url"),
            options = options,
            state = enumOrDefault(string("state"), DownloadState.FAILED),
            progress = int("progress").coerceIn(0, 100),
            etaSeconds = nullableLong("eta_seconds"),
            statusLine = nullableString("status_line"),
            errorMessage = nullableString("error_message"),
            outputUri = nullableString("output_uri"),
            outputFileName = nullableString("output_file_name"),
            outputMimeType = nullableString("output_mime_type"),
            outputSizeBytes = nullableLong("output_size"),
            retryCount = int("retry_count"),
            createdAtEpochMs = long("created_at"),
            updatedAtEpochMs = long("updated_at"),
            completedAtEpochMs = nullableLong("completed_at"),
            sortOrder = int("sort_order"),
            keepPartialFiles = int("keep_partial_files") != 0,
        )
    }

    private fun Cursor.toHistoryItem() = HistoryItem(
        id = string("id"),
        downloadId = string("download_id"),
        sourceUrl = string("source_url"),
        title = string("title"),
        fileUri = string("file_uri"),
        fileName = string("file_name"),
        mimeType = string("mime_type"),
        sizeBytes = long("size_bytes"),
        thumbnailUrl = nullableString("thumbnail_url"),
        completedAtEpochMs = long("completed_at"),
    )

    private fun Cursor.index(column: String) = getColumnIndexOrThrow(column)
    private fun Cursor.string(column: String) = getString(index(column))
    private fun Cursor.int(column: String) = getInt(index(column))
    private fun Cursor.long(column: String) = getLong(index(column))
    private fun Cursor.float(column: String) = getFloat(index(column))
    private fun Cursor.nullableString(column: String) =
        index(column).let { if (isNull(it)) null else getString(it) }
    private fun Cursor.nullableInt(column: String) =
        index(column).let { if (isNull(it)) null else getInt(it) }
    private fun Cursor.nullableLong(column: String) =
        index(column).let { if (isNull(it)) null else getLong(it) }
    private fun Cursor.nullableFloat(column: String) =
        index(column).let { if (isNull(it)) null else getFloat(it) }

    private fun ContentValues.putNullable(key: String, value: String?) {
        if (value == null) putNull(key) else put(key, value)
    }

    private fun ContentValues.putNullable(key: String, value: Int?) {
        if (value == null) putNull(key) else put(key, value)
    }

    private fun ContentValues.putNullable(key: String, value: Long?) {
        if (value == null) putNull(key) else put(key, value)
    }

    private fun ContentValues.putNullable(key: String, value: Float?) {
        if (value == null) putNull(key) else put(key, value)
    }

    private inline fun <reified T : Enum<T>> enumOrDefault(raw: String, default: T): T =
        enumValues<T>().firstOrNull { it.name == raw } ?: default

    private fun Boolean.asInt() = if (this) 1 else 0

    companion object {
        private const val DATABASE_NAME = "media_downloader.db"
        private const val DATABASE_VERSION = 7
        private const val LANGUAGE_SEPARATOR = "\u001F"

        private const val CREATE_DOWNLOADS = """
            CREATE TABLE downloads (
                id TEXT PRIMARY KEY NOT NULL,
                source_url TEXT NOT NULL,
                title TEXT NOT NULL,
                source_name TEXT,
                thumbnail_url TEXT,
                media_type TEXT NOT NULL,
                max_video_height INTEGER,
                video_container TEXT NOT NULL,
                editor_compatible INTEGER NOT NULL DEFAULT 0,
                rate_limit_kbps INTEGER NOT NULL DEFAULT 0,
                audio_format TEXT NOT NULL,
                audio_bitrate INTEGER NOT NULL,
                format_id TEXT,
                download_playlist INTEGER NOT NULL,
                include_subtitles INTEGER NOT NULL,
                subtitle_languages TEXT NOT NULL,
                embed_metadata INTEGER NOT NULL DEFAULT 1,
                embed_thumbnail INTEGER NOT NULL DEFAULT 1,
                audio_speed REAL NOT NULL DEFAULT 1.0,
                audio_pitch_semitones REAL NOT NULL DEFAULT 0.0,
                audio_volume_percent INTEGER NOT NULL DEFAULT 100,
                audio_bass INTEGER NOT NULL DEFAULT 0,
                audio_echo INTEGER NOT NULL DEFAULT 0,
                audio_tremolo INTEGER NOT NULL DEFAULT 0,
                audio_normalize INTEGER NOT NULL DEFAULT 0,
                trim_start_seconds REAL NOT NULL DEFAULT 0.0,
                trim_duration_seconds REAL,
                fade_in_seconds REAL NOT NULL DEFAULT 0.0,
                fade_out_seconds REAL NOT NULL DEFAULT 0.0,
                state TEXT NOT NULL,
                progress INTEGER NOT NULL,
                eta_seconds INTEGER,
                status_line TEXT,
                error_message TEXT,
                output_uri TEXT,
                output_file_name TEXT,
                output_mime_type TEXT,
                output_size INTEGER,
                retry_count INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                completed_at INTEGER,
                sort_order INTEGER NOT NULL DEFAULT 0,
                keep_partial_files INTEGER NOT NULL DEFAULT 0
            )
        """

        private const val CREATE_HISTORY = """
            CREATE TABLE history (
                id TEXT PRIMARY KEY NOT NULL,
                download_id TEXT NOT NULL,
                source_url TEXT NOT NULL,
                title TEXT NOT NULL,
                file_uri TEXT NOT NULL,
                file_name TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                thumbnail_url TEXT,
                completed_at INTEGER NOT NULL
            )
        """
    }
}
