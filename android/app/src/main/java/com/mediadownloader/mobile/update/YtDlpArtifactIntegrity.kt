package com.mediadownloader.mobile.update

import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest

internal object YtDlpArtifactIntegrity {
    private val sha256Pattern = Regex("^[a-fA-F0-9]{64}$")

    fun normalizeSha256(value: String?): String? {
        val candidate = value
            ?.trim()
            ?.removePrefix("sha256:")
            ?.lowercase()
            ?: return null
        return candidate.takeIf(sha256Pattern::matches)
    }

    fun checksumFromManifest(manifest: String, assetName: String): String? = manifest
        .lineSequence()
        .map(String::trim)
        .mapNotNull { line ->
            val separator = line.indexOfFirst(Char::isWhitespace)
            if (separator <= 0) return@mapNotNull null
            val digest = normalizeSha256(line.substring(0, separator)) ?: return@mapNotNull null
            val name = line.substring(separator).trim().removePrefix("*")
            digest.takeIf { name == assetName }
        }
        .firstOrNull()

    fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                if (count > 0) digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
    }

    fun copyVerified(source: File, destination: File) {
        if (!source.isFile) throw IOException("Arquivo de origem ausente: ${source.name}")
        val sourceDigest = sha256(source)
        destination.parentFile?.let { parent ->
            if (!parent.exists() && !parent.mkdirs()) {
                throw IOException("Não foi possível preparar ${parent.name}")
            }
        }
        destination.delete()
        FileInputStream(source).use { input ->
            FileOutputStream(destination).use { output ->
                input.copyTo(output)
                output.fd.sync()
            }
        }
        if (destination.length() != source.length() || sha256(destination) != sourceDigest) {
            destination.delete()
            throw IOException("A cópia do yt-dlp não passou na verificação de integridade")
        }
    }

    fun atomicReplace(source: File, destination: File) {
        destination.parentFile?.let { parent ->
            if (!parent.exists() && !parent.mkdirs()) {
                throw IOException("Não foi possível preparar ${parent.name}")
            }
        }
        try {
            Files.move(
                source.toPath(),
                destination.toPath(),
                StandardCopyOption.ATOMIC_MOVE,
                StandardCopyOption.REPLACE_EXISTING,
            )
        } catch (_: AtomicMoveNotSupportedException) {
            Files.move(source.toPath(), destination.toPath(), StandardCopyOption.REPLACE_EXISTING)
        }
    }
}
