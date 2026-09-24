package com.mediadownloader.mobile.data

/**
 * Pure helpers for the media settings introduced in the 2.0.x line.
 */

/** Resolves which offered choice id should be applied for a media default. */
fun resolveChoiceId(
    choiceIds: List<String>,
    preferredId: String?,
    recommendedId: String?,
): String? = choiceIds.firstOrNull { it == preferredId } ?: recommendedId

/**
 * Out-of-the-box output template for downloads. Kept in sync with the desktop
 * app so file names stay stable across platforms.
 */
object FileNameTemplates {

    const val DEFAULT_TEMPLATE = "%(title).180B [%(id)s].%(ext)s"

    /**
     * Normalizes the user-provided template. Blanks fall back to the default;
     * templates without an extension token get `%(ext)s` appended so the
     * finished file always keeps its real extension.
     */
    fun resolved(raw: String?): String {
        val trimmed = raw?.trim().orEmpty()
        val base = trimmed.ifEmpty { DEFAULT_TEMPLATE }
        return if (base.contains("%(ext)")) base else "$base.%(ext)s"
    }
}