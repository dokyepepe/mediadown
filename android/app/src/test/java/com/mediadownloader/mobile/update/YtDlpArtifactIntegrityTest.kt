package com.mediadownloader.mobile.update

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.io.IOException

class YtDlpArtifactIntegrityTest {
    @get:Rule
    val temporaryFolder = TemporaryFolder()

    @Test
    fun sha256MatchesAKnownDigest() {
        val source = temporaryFolder.newFile("known.txt").apply {
            writeText("abc")
        }

        assertEquals(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            YtDlpArtifactIntegrity.sha256(source),
        )
    }

    @Test
    fun copyVerifiedCreatesParentsAndReplacesTheDestinationExactly() {
        val source = temporaryFolder.newFile("source.bin").apply {
            writeBytes(byteArrayOf(0, 1, 2, 3, 127, -1))
        }
        val destination = File(temporaryFolder.root, "nested/backup.bin")

        YtDlpArtifactIntegrity.copyVerified(source, destination)

        assertTrue(source.isFile)
        assertTrue(destination.isFile)
        assertArrayEquals(source.readBytes(), destination.readBytes())
        assertEquals(
            YtDlpArtifactIntegrity.sha256(source),
            YtDlpArtifactIntegrity.sha256(destination),
        )

        source.writeText("replacement")
        YtDlpArtifactIntegrity.copyVerified(source, destination)
        assertEquals("replacement", destination.readText())
    }

    @Test
    fun copyVerifiedRejectsAMissingSourceWithoutCreatingTheDestination() {
        val source = File(temporaryFolder.root, "missing.bin")
        val destination = File(temporaryFolder.root, "nested/backup.bin")

        val error = assertThrows(IOException::class.java) {
            YtDlpArtifactIntegrity.copyVerified(source, destination)
        }

        assertTrue(error.message.orEmpty().contains("ausente"))
        assertFalse(destination.exists())
    }

    @Test
    fun atomicReplaceMovesTheSourceAndOverwritesTheDestination() {
        val source = temporaryFolder.newFile("new.bin").apply {
            writeText("new content")
        }
        val destination = File(temporaryFolder.root, "nested/active.bin").apply {
            parentFile?.mkdirs()
            writeText("old content")
        }

        YtDlpArtifactIntegrity.atomicReplace(source, destination)

        assertFalse(source.exists())
        assertTrue(destination.isFile)
        assertEquals("new content", destination.readText())
    }
}
