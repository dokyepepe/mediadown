package com.mediadownloader.mobile.ui

import androidx.activity.ComponentActivity
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.mediadownloader.mobile.R
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class HomeScreenBatchTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<ComponentActivity>()

    @Test
    fun singleUrlKeepsTheBatchActionHidden() {
        composeRule.setContent {
            HomeScreen(
                state = HomeUiState(
                    url = "https://example.com/watch?v=1",
                    batchCount = 1,
                ),
                onAction = {},
                thumbnail = { _, _, _, _ -> },
            )
        }

        composeRule.onNodeWithText(composeRule.string(R.string.home_action_analyze)).assertIsDisplayed()
        assertFalse(
            composeRule.composedTextMatches(composeRule.plural(R.plurals.home_action_enqueue_batch, 2)),
        )
    }

    @Test
    fun multipleUrlsOfferTheBatchActionAndDispatchIt() {
        val dispatched = mutableListOf<MobileUiAction>()
        composeRule.setContent {
            HomeScreen(
                state = HomeUiState(
                    url = "https://example.com/watch?v=1\nhttps://example.com/watch?v=2",
                    batchCount = 2,
                ),
                onAction = { dispatched += it },
                thumbnail = { _, _, _, _ -> },
            )
        }

        composeRule.onNodeWithText(composeRule.plural(R.plurals.home_batch_hint, 2)).assertIsDisplayed()
        composeRule.onNodeWithText(composeRule.plural(R.plurals.home_action_enqueue_batch, 2)).performClick()

        assertTrue(dispatched.contains(MobileUiAction.EnqueueUrlBatch))
    }
}
