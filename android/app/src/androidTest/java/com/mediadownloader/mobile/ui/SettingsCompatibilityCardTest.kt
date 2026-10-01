package com.mediadownloader.mobile.ui

import androidx.activity.ComponentActivity
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class SettingsCompatibilityCardTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<ComponentActivity>()

    @Test
    fun everyKnownSiteIsListedWithItsOwnSupportHint() {
        composeRule.setContent {
            SettingsScreen(state = SettingsUiState(), onAction = {})
        }

        settingsCompatibilityLabels.forEach { label ->
            val text = composeRule.string(label)
            composeRule.scrollUntilComposed(text)
            composeRule.onNodeWithText(text).assertIsDisplayed()
        }
    }

    @Test
    fun supportedSitesAreNotAdvertisedAsBroken() {
        composeRule.setContent {
            SettingsScreen(
                state = SettingsUiState(
                    compatSupportedSites = setOf("youtube", "soundcloud"),
                ),
                onAction = {},
            )
        }

        val soundcloud = composeRule.string(settingsCompatibilityLabels.last())
        composeRule.scrollUntilComposed(soundcloud)
        composeRule.onNodeWithText(soundcloud).assertIsDisplayed()
    }
}
