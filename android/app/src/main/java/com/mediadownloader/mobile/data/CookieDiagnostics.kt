package com.mediadownloader.mobile.data

/**
 * Diagnostics for a configured cookies.txt source, mirroring the desktop
 * `CookieCheck` model shown in Settings.
 */
data class CookieCheckUi(
    val ok: Boolean,
    val message: String,
    val detail: String = "",
    val cookieCount: Int = 0,
    val loggedIn: Boolean = false,
)

/**
 * Parses Netscape-format cookies.txt files (the only cookie source that is
 * portable to Android, where browser cookie databases are sandboxed).
 */
object CookieDiagnostics {

    private val SESSION_COOKIE_NAMES = setOf(
        "SID",
        "SAPISID",
        "__Secure-3PAPISID",
        "LOGIN_INFO",
    )

    /**
     * Returns a friendly report for a cookies.txt file. A line is treated as a
     * cookie when it is TAB-separated into at least 7 fields; this also counts
     * `#HttpOnly_`-prefixed domains while skipping the `# Netscape ...`
     * header comment.
     */
    fun check(content: String, label: String): CookieCheckUi {
        val names = cookieNames(content)
        if (names.isEmpty()) {
            return CookieCheckUi(
                ok = false,
                message = "O arquivo ($label) não trouxe cookies no formato Netscape.",
                detail = "Exporte os cookies do seu navegador como cookies.txt (formato Netscape) e tente de novo.",
                cookieCount = 0,
                loggedIn = false,
            )
        }
        val loggedIn = names.any { it in SESSION_COOKIE_NAMES }
        val count = names.size
        return if (loggedIn) {
            CookieCheckUi(
                ok = true,
                message = "Cookies carregados ($label): $count com sessão do YouTube reconhecida.",
                detail = "",
                cookieCount = count,
                loggedIn = true,
            )
        } else {
            CookieCheckUi(
                ok = true,
                message = "Cookies carregados ($label): $count.",
                detail = "",
                cookieCount = count,
                loggedIn = false,
            )
        }
    }

    fun cookieNames(content: String): List<String> = content.lineSequence()
        .map { it.split("\t") }
        .filter { fields -> fields.size >= FIELDS_PER_COOKIE }
        .mapNotNull { fields -> fields.getOrNull(NAME_INDEX)?.takeIf(String::isNotBlank) }
        .toList()

    private const val FIELDS_PER_COOKIE = 7
    private const val NAME_INDEX = 5
}