package com.mediadownloader.mobile.data

import org.junit.Assert.assertEquals
import org.junit.Test

class StorageLocationsTest {
    @Test
    fun treeUriIsRenderedAsReadableRelativePath() {
        assertEquals(
            "Music/Media Downloader",
            StorageLocationStore.treeLocationLabel(
                "content://com.android.externalstorage.documents/tree/primary%3AMusic%2FMedia%20Downloader",
            ),
        )
    }

    @Test
    fun storageCategoriesHaveIndependentPreferenceKeys() {
        assertEquals(3, StorageCategory.entries.map(StorageCategory::preferenceKey).distinct().size)
    }
}
