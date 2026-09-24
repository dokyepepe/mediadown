package com.mediadownloader.mobile.spotify

import com.mediadownloader.mobile.data.SpotifyMedia
import com.mediadownloader.mobile.data.SpotifyModels
import com.mediadownloader.mobile.data.SpotifyTokenStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

enum class SpotifyError {
    GENERIC,
    UNAUTHORIZED,
    FORBIDDEN,
    NOT_FOUND,
    RATE_LIMIT,
    NETWORK,
    RESPONSE,
}

/** A Spotify failure whose [message] is already a user-facing Portuguese sentence. */
class SpotifyException(
    message: String,
    val error: SpotifyError = SpotifyError.GENERIC,
    cause: Throwable? = null,
) : Exception(message, cause)

/**
 * Metadata-only Spotify client: public oEmbed plus the authorized Web API.
 *
 * The access token is refreshed transparently and the session is kept encrypted by
 * [SpotifyTokenStore]. Spotify audio is never downloaded here.
 */
class SpotifyMetadataClient(
    private val tokenStore: SpotifyTokenStore,
    private val clientIdProvider: () -> String,
) {
    private data class StoredToken(
        val accessToken: String,
        val refreshToken: String,
        val expiresAt: Long,
        val scope: String,
        val clientId: String,
        val profileName: String,
        val profileId: String,
    )

    fun clientId(): String = clientIdProvider().trim()

    fun isConnected(): Boolean {
        val token = loadToken() ?: return false
        return token.clientId == clientId() && token.hasCredentials()
    }

    fun accountName(): String? {
        val token = loadToken() ?: return null
        if (token.clientId != clientId()) return null
        return token.profileName.takeIf(String::isNotBlank)
            ?: token.profileId.takeIf(String::isNotBlank)
    }

    fun disconnect() {
        tokenStore.clear()
    }

    suspend fun analyze(url: String): SpotifyMedia = withContext(Dispatchers.IO) {
        val resource = SpotifyModels.parseSpotifyResource(url)
            ?: throw SpotifyException("Este link do Spotify não possui um formato reconhecido.")
        val oembed = requestJson(
            "${SpotifyModels.OEMBED_URL}?url=${URLEncoder.encode(url.trim(), "UTF-8")}",
        )
        var media = SpotifyModels.mediaFromOembed(url, oembed)
        if (media.resourceId.isBlank() || !isConnected()) {
            return@withContext media.copy(requiresAuth = media.isPlaylist)
        }
        try {
            val details = resourceDetails(
                kind = media.resourceKind,
                resourceId = media.resourceId,
                resource = resource,
            )
            media = SpotifyModels.applyDetails(media, details)
        } catch (error: SpotifyException) {
            media = media.copy(requiresAuth = media.isPlaylist, notice = error.message)
        }
        media
    }

    /** Exchanges the authorization code for a token and returns the account name. */
    suspend fun exchangeCode(code: String, verifier: String): String = withContext(Dispatchers.IO) {
        val currentClientId = clientId()
        val token = requestJson(
            SpotifyModels.TOKEN_URL,
            method = "POST",
            form = mapOf(
                "client_id" to currentClientId,
                "grant_type" to "authorization_code",
                "code" to code,
                "redirect_uri" to SpotifyModels.REDIRECT_URI,
                "code_verifier" to verifier,
            ),
        )
        val accessToken = token.optString("access_token")
        if (accessToken.isBlank()) {
            throw SpotifyException("O Spotify não retornou um token de acesso.")
        }
        var profileName = ""
        var profileId = ""
        runCatching {
            requestJson(
                "${SpotifyModels.API_URL}/me",
                headers = mapOf("Authorization" to "Bearer $accessToken"),
            )
        }.onSuccess { profile ->
            profileName = profile.optString("display_name")
            profileId = profile.optString("id")
        }
        saveToken(
            StoredToken(
                accessToken = accessToken,
                refreshToken = token.optString("refresh_token"),
                expiresAt = epochSeconds() + token.optLong("expires_in", 3600L),
                scope = token.optString("scope"),
                clientId = currentClientId,
                profileName = profileName,
                profileId = profileId,
            ),
        )
        profileName.takeIf(String::isNotBlank) ?: "Conta conectada"
    }

    private fun resourceDetails(
        kind: String,
        resourceId: String,
        resource: com.mediadownloader.mobile.data.SpotifyResource,
    ): JSONObject {
        val endpoint = ENDPOINTS[kind]
            ?: ENDPOINTS[resource.kind]
            ?: return JSONObject()
        val details = apiGet("/$endpoint/$resourceId")
        if (kind == "playlist" || resource.kind == "playlist") {
            val page = apiGet(
                "/playlists/$resourceId/items?limit=${SpotifyModels.DISPLAY_ITEM_LIMIT}" +
                    "&offset=0&additional_types=track,episode",
            )
            details.put("_display_items", page.optJSONArray("items") ?: JSONArray())
            details.put("_items_total", page.optInt("total"))
        }
        return details
    }

    private fun apiGet(path: String): JSONObject {
        var token = accessToken(forceRefresh = false)
        try {
            return requestJson(
                "${SpotifyModels.API_URL}$path",
                headers = mapOf("Authorization" to "Bearer $token"),
            )
        } catch (error: SpotifyException) {
            if (error.error != SpotifyError.UNAUTHORIZED) throw error
        }
        token = accessToken(forceRefresh = true)
        return requestJson(
            "${SpotifyModels.API_URL}$path",
            headers = mapOf("Authorization" to "Bearer $token"),
        )
    }

    private fun accessToken(forceRefresh: Boolean): String {
        val token = loadToken() ?: throw authRequired()
        if (token.clientId != clientId()) throw authRequired()
        val now = epochSeconds()
        if (token.accessToken.isNotBlank() && !forceRefresh && token.expiresAt > now + 60) {
            return token.accessToken
        }
        if (token.refreshToken.isBlank()) {
            throw SpotifyException("A sessão do Spotify expirou. Conecte a conta novamente.")
        }
        val refreshed = requestJson(
            SpotifyModels.TOKEN_URL,
            method = "POST",
            form = mapOf(
                "client_id" to clientId(),
                "grant_type" to "refresh_token",
                "refresh_token" to token.refreshToken,
            ),
        )
        val updated = token.copy(
            accessToken = refreshed.optString("access_token").ifBlank { token.accessToken },
            refreshToken = refreshed.optString("refresh_token").ifBlank { token.refreshToken },
            expiresAt = now + refreshed.optLong("expires_in", 3600L),
        )
        saveToken(updated)
        return updated.accessToken
    }

    private fun authRequired() =
        SpotifyException("Conecte sua conta do Spotify nos Ajustes para ver playlists completas.")

    private fun requestJson(
        url: String,
        method: String = "GET",
        headers: Map<String, String> = emptyMap(),
        form: Map<String, String>? = null,
    ): JSONObject {
        val body = form?.let { encodeForm(it).toByteArray(Charsets.UTF_8) }
        var attempt = 0
        while (true) {
            val connection = (URL(url).openConnection() as HttpURLConnection).apply {
                requestMethod = method
                connectTimeout = 20_000
                readTimeout = 20_000
                setRequestProperty("Accept", "application/json")
                setRequestProperty("User-Agent", "MediaDownloader-Android")
                headers.forEach { (name, value) -> setRequestProperty(name, value) }
                if (body != null) {
                    doOutput = true
                    setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
                }
            }
            try {
                if (body != null) {
                    connection.outputStream.use { it.write(body) }
                }
                val status = connection.responseCode
                if (status == HTTP_TOO_MANY_REQUESTS && attempt == 0) {
                    attempt += 1
                    val delay = connection.getHeaderField("Retry-After")?.toIntOrNull() ?: 1
                    Thread.sleep(delay.coerceIn(1, 5) * 1000L)
                    continue
                }
                if (status !in 200..299) {
                    throw httpException(status)
                }
                val text = connection.inputStream.bufferedReader().use { it.readText() }
                return runCatching { JSONObject(text) }.getOrElse {
                    throw SpotifyException("O Spotify retornou uma resposta inválida.", SpotifyError.RESPONSE, it)
                }
            } catch (error: SpotifyException) {
                throw error
            } catch (error: Exception) {
                throw SpotifyException(
                    "Não foi possível conectar ao Spotify. Verifique sua conexão.",
                    SpotifyError.NETWORK,
                    error,
                )
            } finally {
                connection.disconnect()
            }
        }
    }

    private fun httpException(status: Int): SpotifyException = when (status) {
        HttpURLConnection.HTTP_UNAUTHORIZED -> SpotifyException(
            "A autorização do Spotify expirou ou foi recusada.",
            SpotifyError.UNAUTHORIZED,
        )

        HttpURLConnection.HTTP_FORBIDDEN -> SpotifyException(
            "O Spotify não permitiu acesso a este item. A playlist deve pertencer a você " +
                "ou ser colaborativa.",
            SpotifyError.FORBIDDEN,
        )

        HttpURLConnection.HTTP_NOT_FOUND -> SpotifyException(
            "O conteúdo do Spotify não foi encontrado.",
            SpotifyError.NOT_FOUND,
        )

        HTTP_TOO_MANY_REQUESTS -> SpotifyException(
            "O limite temporário da API do Spotify foi atingido. Aguarde e tente novamente.",
            SpotifyError.RATE_LIMIT,
        )

        else -> SpotifyException(
            "O Spotify não conseguiu processar esta solicitação (HTTP $status).",
        )
    }

    private fun loadToken(): StoredToken? {
        val raw = tokenStore.read() ?: return null
        return runCatching {
            val json = JSONObject(raw)
            StoredToken(
                accessToken = json.optString("access_token"),
                refreshToken = json.optString("refresh_token"),
                expiresAt = json.optLong("expires_at"),
                scope = json.optString("scope"),
                clientId = json.optString("client_id"),
                profileName = json.optString("profile_name"),
                profileId = json.optString("profile_id"),
            )
        }.getOrNull()
    }

    private fun saveToken(token: StoredToken) {
        val json = JSONObject().apply {
            put("access_token", token.accessToken)
            put("refresh_token", token.refreshToken)
            put("expires_at", token.expiresAt)
            put("scope", token.scope)
            put("client_id", token.clientId)
            put("profile_name", token.profileName)
            put("profile_id", token.profileId)
        }
        tokenStore.write(json.toString())
    }

    private fun StoredToken.hasCredentials(): Boolean =
        accessToken.isNotBlank() || refreshToken.isNotBlank()

    private fun epochSeconds(): Long = System.currentTimeMillis() / 1000

    private fun encodeForm(values: Map<String, String>): String = values.entries
        .joinToString("&") { (key, value) ->
            "${URLEncoder.encode(key, "UTF-8")}=${URLEncoder.encode(value, "UTF-8")}"
        }
        .replace("+", "%20")

    companion object {
        private const val HTTP_TOO_MANY_REQUESTS = 429

        private val ENDPOINTS = mapOf(
            "track" to "tracks",
            "album" to "albums",
            "artist" to "artists",
            "playlist" to "playlists",
            "show" to "shows",
            "episode" to "episodes",
            "audiobook" to "audiobooks",
        )
    }
}
