package com.mediadownloader.mobile.site

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SiteFileDiscoveryTest {
    @Test
    fun findsRelativeEmbeddedAndScriptPdfsWithoutDuplicates() {
        val html = """
            <html><head><title>Central de documentos</title></head><body>
            <a href="docs/relatorio.pdf#page=2">Relatório</a>
            <iframe src="/manual.pdf" type="application/pdf"></iframe>
            <script>window.file = "\/editais\/edital.pdf?download=1";</script>
            <script>window.copy = "\/editais\/edital.pdf?download=1";</script>
            </body></html>
        """.trimIndent()

        val result = SiteFileDiscovery.parse(
            sourceUrl = "https://example.com/portal",
            finalUrl = "https://example.com/area/index.html",
            html = html,
            includeImages = false,
        )

        assertEquals("Central de documentos", result.pageTitle)
        assertEquals(
            setOf(
                "https://example.com/area/docs/relatorio.pdf",
                "https://example.com/manual.pdf",
                "https://example.com/editais/edital.pdf?download=1",
            ),
            result.files.map(SiteFile::url).toSet(),
        )
        assertTrue(result.files.all { it.kind == SiteFileKind.PDF })
    }

    @Test
    fun findsResponsiveLazyAndSocialImages() {
        val html = """
            <meta property="og:image" content="/social.webp">
            <img src="/cover.jpg" srcset="/small.png 1x, /large.png 2x">
            <img data-src="https://cdn.example.net/photo.avif">
            <div style="background-image: url('/background.svg')"></div>
        """.trimIndent()

        val result = SiteFileDiscovery.parse(
            sourceUrl = "https://example.com",
            finalUrl = "https://example.com/news/",
            html = html,
            includePdfs = false,
        )

        assertEquals(
            setOf(
                "https://example.com/social.webp",
                "https://example.com/cover.jpg",
                "https://example.com/small.png",
                "https://example.com/large.png",
                "https://cdn.example.net/photo.avif",
                "https://example.com/background.svg",
            ),
            result.files.map(SiteFile::url).toSet(),
        )
        assertTrue(result.files.any { it.url.endsWith("background.svg") })
    }

    @Test
    fun respectsFiltersAndRemovesFragments() {
        val html = """
            <a href="/one.pdf#page=4">PDF</a>
            <img src="/one.png#preview">
        """.trimIndent()

        val onlyPdfs = SiteFileDiscovery.parse(
            "https://example.com",
            "https://example.com/page",
            html,
            includeImages = false,
        )

        assertEquals(listOf("https://example.com/one.pdf"), onlyPdfs.files.map(SiteFile::url))
    }

    @Test
    fun recognizesPdfLabelsAndQueryFileNames() {
        val html = """
            <a href="/download?id=42"><strong>Baixar PDF</strong></a>
            <a href="/download?file=guia.pdf&public=1">Guia</a>
        """.trimIndent()

        val result = SiteFileDiscovery.parse(
            "https://example.com",
            "https://example.com/portal/",
            html,
            includeImages = false,
        )

        assertEquals(
            setOf(
                "https://example.com/download?id=42",
                "https://example.com/download?file=guia.pdf&public=1",
            ),
            result.files.map(SiteFile::url).toSet(),
        )
    }

    @Test
    fun rejectsUnsafeSchemesAndSanitizesNames() {
        val html = """
            <a href="javascript:alert(1).pdf">bad</a>
            <img src="data:image/png;base64,abc">
            <a href="/file.pdf" download="Relatório: 2026?.pdf">good</a>
        """.trimIndent()

        val result = SiteFileDiscovery.parse(
            "https://example.com",
            "https://example.com/page",
            html,
        )

        assertEquals(1, result.files.size)
        assertEquals("Relatório_ 2026_.pdf", result.files.single().name)
    }
}
