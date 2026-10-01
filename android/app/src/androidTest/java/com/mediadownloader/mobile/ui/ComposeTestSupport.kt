package com.mediadownloader.mobile.ui

import androidx.annotation.PluralsRes
import androidx.annotation.StringRes
import androidx.compose.ui.test.hasScrollAction
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.ComposeContentTestRule
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.test.swipeUp
import androidx.test.platform.app.InstrumentationRegistry
import com.mediadownloader.mobile.R

internal fun ComposeContentTestRule.string(@StringRes id: Int, vararg args: Any): String =
    InstrumentationRegistry.getInstrumentation().targetContext.getString(id, *args)

internal fun ComposeContentTestRule.plural(@PluralsRes id: Int, count: Int): String =
    InstrumentationRegistry.getInstrumentation().targetContext.resources
        .getQuantityString(id, count, count)

/** Scrolls the first scrollable container until [text] is part of the composed tree. */
internal fun ComposeContentTestRule.scrollUntilComposed(text: String) {
    repeat(20) {
        waitForIdle()
        if (onAllNodes(hasText(text)).fetchSemanticsNodes().isNotEmpty()) return
        onNode(hasScrollAction()).performTouchInput { swipeUp() }
    }
    throw AssertionError("\"$text\" was never composed while scrolling")
}

internal fun ComposeContentTestRule.composedTextMatches(text: String): Boolean =
    onAllNodes(hasText(text)).fetchSemanticsNodes().isNotEmpty()

internal val settingsCompatibilityLabels = listOf(
    R.string.settings_compat_youtube,
    R.string.settings_compat_tiktok,
    R.string.settings_compat_instagram,
    R.string.settings_compat_facebook,
    R.string.settings_compat_x,
    R.string.settings_compat_soundcloud,
)
