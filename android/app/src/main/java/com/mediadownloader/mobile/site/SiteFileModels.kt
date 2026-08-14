package com.mediadownloader.mobile.site

import java.net.URI
import java.net.URLDecoder
import java.nio.charset.StandardCharsets

enum class SiteFileKind(val label: String) {
    PDF("PDF"),
    IMAGE("Imagem"),
}

data class SiteFile(
    val url: String,
    val name: String,
    val kind: SiteFileKind,
    val mimeType: String? = null,
    val referer: String? = null,
)

data class SiteScanResult(
    val sourceUrl: String,
    val finalUrl: String,
    val pageTitle: String,
    val files: List<SiteFile>,
)

/** Pure HTML discovery kept free of Android APIs so it can be unit-tested on the JVM. */
object SiteFileDiscovery {
    private val imageExtensions = setOf(
        "avif", "bmp", "gif", "heic", "heif", "ico", "jpeg", "jpg", "png", "svg",
        "tif", "tiff", "webp",
    )
    private val tagRegex = Regex(
        """<\s*([a-z][\w:-]*)\b([^>]*)>""",
        RegexOption.IGNORE_CASE,
    )
    private val attributeRegex = Regex(
        """([:\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))""",
        RegexOption.IGNORE_CASE,
    )
    private val titleRegex = Regex("""<title\b[^>]*>(.*?)</title\s*>""", setOf(
        RegexOption.IGNORE_CASE,
        RegexOption.DOT_MATCHES_ALL,
    ))
    private val anchorPairRegex = Regex("""<a\b([^>]*)>(.*?)</a\s*>""", setOf(
        RegexOption.IGNORE_CASE,
        RegexOption.DOT_MATCHES_ALL,
    ))
    private val styleUrlRegex = Regex(
        """url\(\s*['"]?([^)'"]+)""",
        RegexOption.IGNORE_CASE,
    )
    private val scriptPdfRegex = Regex(
        """(?i)(?<=["'])(?:https?:)?(?:\\?/\\?/|\\?/|\.\.?/)[^\s'"<>]+?\.pdf(?:\?[^\s'"<>]*)?""",
    )

    fun parse(
        sourceUrl: String,
        finalUrl: String,
        html: String,
        includePdfs: Boolean = true,
        includeImages: Boolean = true,
    ): SiteScanResult {
        var baseUrl = finalUrl
        val candidates = mutableListOf<SiteFile>()

        fun add(raw: String?, kind: SiteFileKind, suggestedName: String? = null, mimeType: String? = null) {
            val resolved = resolveWebUrl(baseUrl, raw.orEmpty()) ?: return
            if (kind == SiteFileKind.PDF && !includePdfs) return
            if (kind == SiteFileKind.IMAGE && !includeImages) return
            candidates += SiteFile(
                url = resolved,
                name = nameFor(resolved, kind, suggestedName.orEmpty()),
                kind = kind,
                mimeType = mimeType,
                referer = finalUrl,
            )
        }

        tagRegex.findAll(html).forEach { match ->
            val tag = match.groupValues[1].lowercase()
            val attrs = attributes(match.groupValues[2])
            if (tag == "base") {
                resolveWebUrl(baseUrl, attrs["href"].orEmpty())?.let { baseUrl = it }
                return@forEach
            }
            if (tag == "img" || tag == "source") {
                listOf("src", "data-src", "data-lazy-src", "poster").forEach { key ->
                    attrs[key]?.takeIf(String::isNotBlank)?.let {
                        add(it, SiteFileKind.IMAGE, attrs["alt"] ?: attrs["title"])
                    }
                }
                listOf("srcset", "data-srcset").forEach { key ->
                    attrs[key].orEmpty().split(',').forEach { entry ->
                        entry.trim().substringBefore(' ').takeIf(String::isNotBlank)?.let {
                            add(it, SiteFileKind.IMAGE, attrs["alt"] ?: attrs["title"])
                        }
                    }
                }
            }
            if (tag == "meta") {
                val marker = (attrs["property"] ?: attrs["name"]).orEmpty().lowercase()
                if (marker in setOf("og:image", "og:image:url", "twitter:image", "twitter:image:src")) {
                    add(attrs["content"], SiteFileKind.IMAGE)
                }
            }
            if (tag == "link") {
                val relations = attrs["rel"].orEmpty().lowercase().split(Regex("\\s+"))
                if ("icon" in relations || "image_src" in relations) {
                    add(attrs["href"], SiteFileKind.IMAGE, attrs["title"])
                }
            }
            if (tag == "a") {
                val raw = attrs["href"].orEmpty()
                val explicit = "${attrs["type"].orEmpty()} ${attrs["download"].orEmpty()}".lowercase()
                val kind = if ("pdf" in explicit) SiteFileKind.PDF else kindFromUrl(
                    resolveWebUrl(baseUrl, raw).orEmpty(),
                )
                if (kind != null) add(raw, kind, attrs["download"] ?: attrs["title"])
            }
            if (tag in setOf("embed", "iframe", "object")) {
                val raw = attrs["src"] ?: attrs["data"]
                val kind = if (attrs["type"].orEmpty().contains("pdf", ignoreCase = true)) {
                    SiteFileKind.PDF
                } else {
                    kindFromUrl(resolveWebUrl(baseUrl, raw.orEmpty()).orEmpty())
                }
                if (kind != null) add(raw, kind, attrs["title"])
            }
            styleUrlRegex.findAll(attrs["style"].orEmpty()).forEach {
                add(it.groupValues[1], SiteFileKind.IMAGE)
            }
        }

        anchorPairRegex.findAll(html).forEach { match ->
            val attrs = attributes(match.groupValues[1])
            val raw = attrs["href"].orEmpty()
            val resolved = resolveWebUrl(baseUrl, raw).orEmpty()
            if (kindFromUrl(resolved) == null) {
                val visibleText = decodeHtml(match.groupValues[2].replace(Regex("<[^>]+>"), " "))
                    .replace(Regex("\\s+"), " ")
                    .trim()
                val suggested = attrs["title"].orEmpty()
                if (visibleText.contains("pdf", ignoreCase = true) ||
                    suggested.contains("pdf", ignoreCase = true)
                ) {
                    add(raw, SiteFileKind.PDF, suggested.ifBlank { visibleText })
                }
            }
        }

        if (includePdfs) {
            val embeddedText = html.replace(Regex("<[^>]+>"), " ")
            scriptPdfRegex.findAll(embeddedText).forEach {
                add(it.value, SiteFileKind.PDF, mimeType = "application/pdf")
            }
        }

        val files = candidates
            .distinctBy(SiteFile::url)
            .sortedWith(compareBy<SiteFile> { it.kind.name }.thenBy { it.name.lowercase() }.thenBy { it.url })
        val pageTitle = titleRegex.find(html)?.groupValues?.get(1)
            ?.replace(Regex("<[^>]+>"), " ")
            ?.let(::decodeHtml)
            ?.replace(Regex("\\s+"), " ")
            ?.trim()
            ?.takeIf(String::isNotBlank)
            ?: hostTitle(finalUrl)
        return SiteScanResult(sourceUrl, finalUrl, pageTitle, files)
    }

    fun kindFromUrl(url: String): SiteFileKind? {
        val uri = runCatching { URI(url) }.getOrNull() ?: return null
        val path = uri.path.orEmpty()
        val decoded = decodeUrl("$path?${uri.rawQuery.orEmpty()}").lowercase()
        val extension = path.substringAfterLast('.', "").lowercase()
        return when {
            extension == "pdf" || ".pdf" in decoded -> SiteFileKind.PDF
            extension in imageExtensions || imageExtensions.any { ".$it" in decoded } -> SiteFileKind.IMAGE
            else -> null
        }
    }

    fun nameFor(url: String, kind: SiteFileKind, suggested: String = ""): String {
        val pathName = runCatching { URI(url).path.substringAfterLast('/') }.getOrDefault("")
        val decoded = decodeUrl(suggested.trim()).ifBlank { decodeUrl(pathName) }
        var cleaned = decoded
            .replace(Regex("[\\u0000-\\u001F\\u007F/\\\\:*?\"<>|]"), "_")
            .trim()
            .trim('.')
            .take(220)
            .ifBlank { if (kind == SiteFileKind.PDF) "documento.pdf" else "imagem" }
        if (kind == SiteFileKind.PDF && !cleaned.endsWith(".pdf", ignoreCase = true)) {
            cleaned += ".pdf"
        }
        return cleaned
    }

    fun resolveWebUrl(baseUrl: String, rawValue: String): String? {
        val value = decodeHtml(rawValue.trim()).replace("\\/", "/")
        if (value.isBlank() || value.startsWith('#') || listOf(
                "data:", "blob:", "javascript:", "mailto:",
            ).any { value.startsWith(it, ignoreCase = true) }
        ) return null
        return runCatching {
            val resolved = URI(baseUrl).resolve(value.replace(" ", "%20"))
            if (resolved.scheme.equals("http", true) || resolved.scheme.equals("https", true)) {
                if (resolved.host.isNullOrBlank()) null
                else URI(
                    resolved.scheme,
                    resolved.userInfo,
                    resolved.host,
                    resolved.port,
                    resolved.path,
                    resolved.query,
                    null,
                ).toASCIIString()
            } else null
        }.getOrNull()
    }

    private fun attributes(raw: String): Map<String, String> = buildMap {
        attributeRegex.findAll(raw).forEach { match ->
            val value = match.groupValues.drop(2).firstOrNull(String::isNotEmpty).orEmpty()
            put(match.groupValues[1].lowercase(), decodeHtml(value))
        }
    }

    private fun decodeUrl(value: String): String = runCatching {
        URLDecoder.decode(value, StandardCharsets.UTF_8.name())
    }.getOrDefault(value)

    private fun decodeHtml(value: String): String {
        var result = value
            .replace("&amp;", "&", ignoreCase = true)
            .replace("&quot;", "\"", ignoreCase = true)
            .replace("&apos;", "'", ignoreCase = true)
            .replace("&#39;", "'", ignoreCase = true)
            .replace("&lt;", "<", ignoreCase = true)
            .replace("&gt;", ">", ignoreCase = true)
        Regex("&#(x?[0-9a-fA-F]+);").findAll(result).toList().asReversed().forEach { match ->
            val raw = match.groupValues[1]
            val codePoint = if (raw.startsWith('x', ignoreCase = true)) {
                raw.drop(1).toIntOrNull(16)
            } else raw.toIntOrNull()
            if (codePoint != null && Character.isValidCodePoint(codePoint)) {
                result = result.replaceRange(match.range, String(Character.toChars(codePoint)))
            }
        }
        return result
    }

    private fun hostTitle(url: String): String = runCatching {
        URI(url).host.orEmpty().removePrefix("www.").ifBlank { "Site" }
    }.getOrDefault("Site")
}
