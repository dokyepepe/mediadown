package com.mediadownloader.mobile.data

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SpotifyModelsTest {
    @Test
    fun parsesTrackAlbumPlaylistAndLocalizedPaths() {
        assertEquals(
            SpotifyResource("track", "4cOdK2wGLETKBW3PvgPWqT", "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"),
            SpotifyModels.parseSpotifyResource("https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"),
        )
        assertEquals(
            "playlist",
            SpotifyModels.parseSpotifyResource(
                "https://open.spotify.com/intl-pt/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc",
            )?.kind,
        )
        assertEquals(
            "album",
            SpotifyModels.parseSpotifyResource("https://open.spotify.com/embed/album/1ATL5GLyefJaxhQzSPVrLX")?.kind,
        )
        assertEquals(
            "short",
            SpotifyModels.parseSpotifyResource("https://spotify.link/abc123")?.kind,
        )
    }

    @Test
    fun rejectsNonSpotifyHostsAndMalformedIds() {
        assertNull(SpotifyModels.parseSpotifyResource("https://example.com/track/abc"))
        assertNull(SpotifyModels.parseSpotifyResource("https://open.spotify.com/track/../../etc"))
        assertNull(SpotifyModels.parseSpotifyResource("https://open.spotify.com/track/"))
        assertNull(SpotifyModels.parseSpotifyResource("https://open.spotify.com/collection/tracks"))
        assertNull(SpotifyModels.parseSpotifyResource("not a url"))
        assertFalse(SpotifyModels.isSpotifyUrl("https://youtube.com/watch?v=1"))
        assertTrue(SpotifyModels.isSpotifyUrl("https://open.spotify.com/artist/0OdUWJ0sBjDrqHygGUXeCF"))
    }

    @Test
    fun validatesClientIdShape() {
        assertTrue(SpotifyModels.validClientId("a".repeat(32)))
        assertTrue(SpotifyModels.validClientId("AbC123".repeat(4)))
        assertFalse(SpotifyModels.validClientId("curto"))
        assertFalse(SpotifyModels.validClientId("com-hifen-e-espacos".repeat(2)))
        assertFalse(SpotifyModels.validClientId("a".repeat(65)))
    }

    @Test
    fun codeChallengeMatchesRfc7636Vector() {
        assertEquals(
            "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
            SpotifyModels.codeChallenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"),
        )
    }

    @Test
    fun authorizationUrlCarriesPkceAndRedirect() {
        val url = SpotifyModels.authorizationUrl(
            clientId = "a".repeat(32),
            state = "estado",
            challenge = "desafio",
        )

        assertTrue(url.startsWith(SpotifyModels.AUTHORIZE_URL))
        assertTrue(url.contains("client_id=${"a".repeat(32)}"))
        assertTrue(url.contains("code_challenge_method=S256"))
        assertTrue(url.contains("code_challenge=desafio"))
        assertTrue(url.contains("state=estado"))
        assertTrue(
            url.contains("redirect_uri=mediadownloader%3A%2F%2Fspotify%2Fcallback"),
        )
        assertTrue(url.contains("scope=playlist-read-private%20playlist-read-collaborative"))
        assertTrue(url.contains("response_type=code"))
    }

    @Test
    fun youTubeSearchKeepsArtistFirstAndStripsQuotes() {
        assertEquals(
            "ytsearch1:\"Artist A Song B\"",
            SpotifyModels.youTubeSearchQuery("Song \"B\"", "Artist A"),
        )
        assertEquals(
            "ytsearch1:\"Only Title\"",
            SpotifyModels.youTubeSearchQuery("Only Title", null),
        )
    }

    @Test
    fun parseRedirectReadsCodeAndState() {
        val redirect = SpotifyModels.parseRedirect(
            "mediadownloader://spotify/callback?code=abc123&state=xyz",
        )

        assertEquals("abc123", redirect?.code)
        assertEquals("xyz", redirect?.state)
        assertNull(redirect?.error)
        assertNull(SpotifyModels.parseRedirect("https://example.com/callback?code=abc"))
        assertEquals(
            "access_denied",
            SpotifyModels.parseRedirect(
                "mediadownloader://spotify/callback?error=access_denied&state=xyz",
            )?.error,
        )
    }

    @Test
    fun mediaFromOembedResolvesEmbedResourceAndThumbnail() {
        val oembed = JSONObject(
            """
            {
              "title": "Minha Playlist",
              "thumbnail_url": "https://image/cover.jpg",
              "iframe_url": "https://open.spotify.com/embed/playlist/37i9dQZF1DXcBWIGoYBM5M"
            }
            """.trimIndent(),
        )

        val media = SpotifyModels.mediaFromOembed("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M", oembed)

        assertEquals("Minha Playlist", media.title)
        assertEquals("https://image/cover.jpg", media.thumbnailUrl)
        assertEquals("playlist", media.resourceKind)
        assertEquals("37i9dQZF1DXcBWIGoYBM5M", media.resourceId)
        assertTrue(media.isPlaylist)
        assertFalse(media.authenticated)
    }

    @Test
    fun applyDetailsEnrichesPlaylistTracks() {
        val oembed = JSONObject(
            """{"title":"Minha Playlist","iframe_url":"https://open.spotify.com/embed/playlist/abc"}""",
        )
        val base = SpotifyModels.mediaFromOembed(
            "https://open.spotify.com/playlist/abc",
            oembed,
        )
        val details = JSONObject(
            """
            {
              "name": "Minha Playlist",
              "owner": { "display_name": "Pietro" },
              "images": [ { "url": "https://image/cover.jpg" } ],
              "external_urls": { "spotify": "https://open.spotify.com/playlist/abc" },
              "tracks": { "total": 42 },
              "_display_items": [
                {
                  "item": {
                    "name": "Song A",
                    "type": "track",
                    "duration_ms": 185000,
                    "artists": [ { "name": "Artist A" } ],
                    "album": { "name": "Album A", "images": [ { "url": "https://image/a.jpg" } ] },
                    "external_urls": { "spotify": "https://open.spotify.com/track/a" }
                  }
                },
                {
                  "item": {
                    "name": "Episode B",
                    "type": "episode",
                    "duration_ms": 60000,
                    "show": { "name": "Show B", "images": [ { "url": "https://image/b.jpg" } ] }
                  }
                },
                { "item": null }
              ]
            }
            """.trimIndent(),
        )

        val media = SpotifyModels.applyDetails(base, details)

        assertEquals("Pietro", media.subtitle)
        assertEquals("https://image/cover.jpg", media.thumbnailUrl)
        assertEquals(42, media.itemCount)
        assertTrue(media.authenticated)
        assertEquals(2, media.tracks.size)
        assertEquals("Song A", media.tracks[0].title)
        assertEquals("Artist A", media.tracks[0].artist)
        assertEquals("Album A", media.tracks[0].album)
        assertEquals(185L, media.tracks[0].durationSeconds)
        assertEquals("https://open.spotify.com/track/a", media.tracks[0].webpageUrl)
        assertEquals("Show B", media.tracks[1].artist)
        assertEquals(60L, media.tracks[1].durationSeconds)
        assertEquals(1, media.tracks[0].index)
        assertEquals(2, media.tracks[1].index)
    }
}
