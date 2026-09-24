package com.mediadownloader.mobile.data

import org.json.JSONArray
import org.json.JSONObject
import java.net.URI
import java.net.URLEncoder
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.Base64

/** Normalized public Spotify resource identifier. */
data class SpotifyResource(
    val kind: String,
    val resourceId: String,
    val url: String,
)

/** One playlist entry resolved from the Spotify Web API. */
data class SpotifyTrack(
    val index: Int,
    val title: String,
    val artist: String,
    val album: String,
    val durationSeconds: Long?,
    val webpageUrl: String?,
    val thumbnailUrl: String?,
)

/** Metadata-only view of a Spotify resource. */
data class SpotifyMedia(
    val title: String,
    val subtitle: String?,
    val thumbnailUrl: String?,
    val resourceKind: String,
    val resourceId: String,
    val webpageUrl: String,
    val isPlaylist: Boolean,
    val itemCount: Int?,
    val durationSeconds: Long?,
    val tracks: List<SpotifyTrack>,
    val authenticated: Boolean = false,
    val requiresAuth: Boolean = false,
    val notice: String? = null,
)

/** Result parsed from the OAuth redirect deep link. */
data class SpotifyRedirect(
    val code: String?,
    val state: String?,
    val error: String?,
)

/**
 * Pure Spotify helpers: URL parsing, OAuth PKCE and JSON response mapping.
 *
 * Everything here is JVM-only so it can be unit tested without an Android device.
 */
object SpotifyModels {
    const val OEMBED_URL = "https://open.spotify.com/oembed"
    const val API_URL = "https://api.spotify.com/v1"
    const val AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
    const val TOKEN_URL = "https://accounts.spotify.com/api/token"
    const val SCOPES = "playlist-read-private playlist-read-collaborative"
    const val DISPLAY_ITEM_LIMIT = 50
    const val REDIRECT_URI = "mediadownloader://spotify/callback"

    private val RESOURCE_TYPES =
        setOf("track", "album", "artist", "playlist", "show", "episode", "audiobook")
    private val CLIENT_ID_REGEX = Regex("[A-Za-z0-9]{20,64}")
    private val RESOURCE_ID_REGEX = Regex("[A-Za-z0-9]+")
    private val SEARCH_SANITIZE = Regex("[\"\r\n\t]+")
    private val WHITESPACE = Regex("\\s+")
    private val secureRandom = SecureRandom()

    fun isSpotifyUrl(url: String): Boolean = parseSpotifyResource(url) != null

    /** Parses official Spotify URLs, including localized and embed paths. */
    fun parseSpotifyResource(url: String): SpotifyResource? {
        val trimmed = url.trim()
        if (trimmed.isEmpty()) return null
        val uri = runCatching { URI(trimmed) }.getOrNull() ?: return null
        val host = uri.host?.lowercase() ?: return null
        val isSpotify = host == "spotify.link" ||
            host == "open.spotify.com" ||
            host.endsWith(".spotify.com")
        if (!isSpotify) return null
        if (host == "spotify.link") return SpotifyResource("short", "", trimmed)

        val parts = uri.path.orEmpty()
            .split('/')
            .filter { it.isNotBlank() }
            .filterNot { it.lowercase().startsWith("intl-") }
            .toMutableList()
        if (parts.firstOrNull()?.lowercase() == "embed") parts.removeAt(0)
        if (parts.size < 2) return null
        val kind = parts[0].lowercase()
        if (kind !in RESOURCE_TYPES) return null
        val resourceId = parts[1].substringBefore('?')
        if (!RESOURCE_ID_REGEX.matches(resourceId)) return null
        return SpotifyResource(kind, resourceId, trimmed)
    }

    fun validClientId(value: String): Boolean = CLIENT_ID_REGEX.matches(value.trim())

    fun randomVerifier(): String {
        val bytes = ByteArray(64)
        secureRandom.nextBytes(bytes)
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes)
    }

    fun randomState(): String {
        val bytes = ByteArray(32)
        secureRandom.nextBytes(bytes)
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes)
    }

    /** RFC 7636 S256 code challenge. */
    fun codeChallenge(verifier: String): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray(Charsets.US_ASCII))
        return Base64.getUrlEncoder().withoutPadding().encodeToString(digest)
    }

    fun authorizationUrl(clientId: String, state: String, challenge: String): String {
        val params = linkedMapOf(
            "client_id" to clientId.trim(),
            "response_type" to "code",
            "redirect_uri" to REDIRECT_URI,
            "scope" to SCOPES,
            "state" to state,
            "code_challenge_method" to "S256",
            "code_challenge" to challenge,
            "show_dialog" to "true",
        )
        return "$AUTHORIZE_URL?${encodeForm(params)}"
    }

    fun parseRedirect(rawUri: String): SpotifyRedirect? {
        val uri = runCatching { URI(rawUri) }.getOrNull() ?: return null
        if (!uri.scheme.equals("mediadownloader", ignoreCase = true)) return null
        if (!uri.host.equals("spotify", ignoreCase = true)) return null
        val values = parseQuery(uri.rawQuery)
        return SpotifyRedirect(
            code = values["code"]?.firstOrNull(),
            state = values["state"]?.firstOrNull(),
            error = values["error"]?.firstOrNull(),
        )
    }

    /**
     * Search query handed to yt-dlp. The `ytsearch1:` prefix keeps the request
     * inside YouTube, since Spotify audio must never be fetched directly.
     */
    fun youTubeSearchQuery(title: String, artist: String?): String {
        val cleanTitle = title.replace(SEARCH_SANITIZE, " ").replace(WHITESPACE, " ").trim()
        val cleanArtist = artist.orEmpty().replace(SEARCH_SANITIZE, " ").replace(WHITESPACE, " ").trim()
        val term = listOf(cleanArtist, cleanTitle)
            .filter { it.isNotBlank() }
            .joinToString(" ")
            .trim()
        return "ytsearch1:\"$term\""
    }

    fun mediaFromOembed(url: String, oembed: JSONObject): SpotifyMedia {
        val requested = parseSpotifyResource(url) ?: SpotifyResource("", "", url.trim())
        val embedded = parseSpotifyResource(oembed.optString("iframe_url").orEmpty())
        val resolved = if (requested.kind == "short" && embedded != null) embedded else requested
        return SpotifyMedia(
            title = oembed.optString("title").takeIf(String::isNotBlank) ?: "Conteúdo do Spotify",
            subtitle = null,
            thumbnailUrl = oembed.optString("thumbnail_url").takeIf(String::isNotBlank),
            resourceKind = resolved.kind.ifBlank { "spotify" },
            resourceId = resolved.resourceId,
            webpageUrl = url.trim(),
            isPlaylist = resolved.kind == "playlist",
            itemCount = null,
            durationSeconds = null,
            tracks = emptyList(),
        )
    }

    /** Enriches an oEmbed result with authorized Web API details. */
    fun applyDetails(media: SpotifyMedia, details: JSONObject): SpotifyMedia {
        val kind = media.resourceKind
        val tracks = if (kind == "playlist") playlistTracks(details, DISPLAY_ITEM_LIMIT) else emptyList()
        val image = imageUrl(details.optJSONArray("images")) ?: media.thumbnailUrl
        val externalUrl = details.optJSONObject("external_urls")
            ?.optString("spotify")
            ?.takeIf(String::isNotBlank)
            ?: media.webpageUrl
        val total = details.optInt("_items_total", 0).takeIf { it > 0 }
            ?: details.optJSONObject("tracks")?.optInt("total")?.takeIf { it > 0 }
            ?: tracks.size.takeIf { it > 0 }
        return media.copy(
            title = details.optString("name").takeIf(String::isNotBlank) ?: media.title,
            subtitle = subtitleFor(kind, details),
            thumbnailUrl = image,
            webpageUrl = externalUrl,
            isPlaylist = kind == "playlist",
            itemCount = total,
            durationSeconds = durationSeconds(details.optLong("duration_ms")) ?: media.durationSeconds,
            tracks = tracks,
            authenticated = true,
            requiresAuth = false,
        )
    }

    fun playlistTracks(details: JSONObject, limit: Int): List<SpotifyTrack> {
        val items = details.optJSONArray("_display_items")
            ?: details.optJSONArray("items")
            ?: details.optJSONObject("tracks")?.optJSONArray("items")
            ?: return emptyList()
        val result = mutableListOf<SpotifyTrack>()
        for (index in 0 until items.length()) {
            if (result.size >= limit) break
            val wrapper = items.optJSONObject(index) ?: continue
            val track = wrapper.optJSONObject("item")
                ?: wrapper.optJSONObject("track")
                ?: wrapper
            val name = track.optString("name").takeIf(String::isNotBlank) ?: continue
            val album = track.optJSONObject("album")
            val show = track.optJSONObject("show")
            val artists = artistNames(track.optJSONArray("artists"))
            result += SpotifyTrack(
                index = result.size + 1,
                title = name,
                artist = artists.ifBlank { show?.optString("name").orEmpty() },
                album = album?.optString("name").orEmpty().ifBlank {
                    show?.optString("name").orEmpty()
                },
                durationSeconds = durationSeconds(track.optLong("duration_ms")),
                webpageUrl = track.optJSONObject("external_urls")
                    ?.optString("spotify")
                    ?.takeIf(String::isNotBlank),
                thumbnailUrl = imageUrl(album?.optJSONArray("images"))
                    ?: imageUrl(track.optJSONArray("images"))
                    ?: imageUrl(show?.optJSONArray("images")),
            )
        }
        return result
    }

    private fun subtitleFor(kind: String, details: JSONObject): String? = when (kind) {
        "track", "album" -> artistNames(details.optJSONArray("artists")).ifBlank { null }
        "artist" -> "Artista"
        "playlist" -> details.optJSONObject("owner")
            ?.let { it.optString("display_name").ifBlank { it.optString("id") } }
            ?.takeIf(String::isNotBlank)
        "episode" -> details.optJSONObject("show")?.optString("name")
            ?.takeIf(String::isNotBlank)
            ?: details.optString("publisher").takeIf(String::isNotBlank)
        "show", "audiobook" -> details.optString("publisher").takeIf(String::isNotBlank)
        else -> null
    }

    private fun artistNames(artists: JSONArray?): String {
        if (artists == null) return ""
        val names = mutableListOf<String>()
        for (index in 0 until artists.length()) {
            val name = artists.optJSONObject(index)?.optString("name")
            if (!name.isNullOrBlank()) names += name
        }
        return names.joinToString(", ")
    }

    private fun imageUrl(images: JSONArray?): String? {
        if (images == null) return null
        for (index in 0 until images.length()) {
            val url = images.optJSONObject(index)?.optString("url")
            if (!url.isNullOrBlank()) return url
        }
        return null
    }

    private fun durationSeconds(millis: Long): Long? =
        if (millis > 0) millis / 1000 else null

    private fun encodeForm(values: Map<String, String>): String = values.entries
        .joinToString("&") { (key, value) ->
            "${URLEncoder.encode(key, "UTF-8")}=${URLEncoder.encode(value, "UTF-8")}"
        }
        .replace("+", "%20")

    private fun parseQuery(rawQuery: String?): Map<String, List<String>> {
        if (rawQuery.isNullOrBlank()) return emptyMap()
        val result = mutableMapOf<String, MutableList<String>>()
        rawQuery.split('&').forEach { pair ->
            if (pair.isBlank()) return@forEach
            val key = pair.substringBefore('=')
            val value = pair.substringAfter('=', "")
            result.getOrPut(decode(key)) { mutableListOf() } += decode(value)
        }
        return result
    }

    private fun decode(value: String): String =
        runCatching { java.net.URLDecoder.decode(value, "UTF-8") }.getOrDefault(value)
}
