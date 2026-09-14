package com.mediadownloader.mobile.preview

import android.content.Context
import com.mediadownloader.mobile.data.AudioEffects
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runInterruptible
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException
import java.util.Locale
import java.util.concurrent.TimeUnit

/**
 * Renders a short preview clip with the embedded FFmpeg (unpacked by
 * `com.yausername.ffmpeg.FFmpeg.init`) applying the requested effect chain.
 *
 * Mirrors the desktop `render_preview` fallback order per `includeVideo`:
 * keep the video stream untouched (fast), re-encode hastefully with x264 when
 * the source cannot be remuxed, and finally drop the video so a preview never
 * fails over picture.
 */
class PreviewRenderer(
    private val context: Context,
    private val ffmpegResolver: (Context) -> File = ::resolveFfmpegBinary,
) {
    @Volatile
    private var activeProcess: Process? = null

    suspend fun render(
        sourceUrl: String,
        effects: AudioEffects,
        outputFile: File,
        windowSeconds: Float,
        includeVideo: Boolean,
        startSeconds: Float = 0f,
    ): File = withContext(Dispatchers.IO) {
        val binary = ffmpegResolver(context)
        val filters = effects.sanitized().filterChain()
        val start = formatSeconds(startSeconds.coerceAtLeast(0f))
        val duration = formatSeconds(windowSeconds.coerceAtLeast(1f))

        val attempts = buildList {
            if (includeVideo) {
                add(command(binary, sourceUrl, outputFile, filters, duration, start, videoMode = VideoMode.COPY))
                add(command(binary, sourceUrl, outputFile, filters, duration, start, videoMode = VideoMode.X264))
            }
            add(command(binary, sourceUrl, outputFile, filters, duration, start, videoMode = VideoMode.NONE))
        }

        var lastError = ""
        for (command in attempts) {
            val process = runInterruptible {
                ProcessBuilder(command)
                    .redirectErrorStream(true)
                    .apply { setEmbeddedFfmpegEnvironment(context, environment(), binary) }
                    .start()
            }
            activeProcess = process
            try {
                val finished = runInterruptible {
                    process.waitFor(TIMEOUT_SECONDS, TimeUnit.SECONDS)
                }
                if (!finished) {
                    process.destroy()
                    throw IOException("A geração da prévia demorou demais e foi interrompida.")
                }
                val log = runInterruptible {
                    process.inputStream.bufferedReader().use { it.readText() }
                }
                if (process.exitValue() == 0 && outputFile.exists() && outputFile.length() > 0L) {
                    return@withContext outputFile
                }
                lastError = readableFfmpegError(log)
            } catch (error: Throwable) {
                process.destroy()
                lastError = error.message ?: error.javaClass.simpleName
            } finally {
                activeProcess = null
            }
        }
        throw IOException(lastError.ifBlank { "O FFmpeg não conseguiu gerar a prévia." })
    }

    fun cancel() {
        activeProcess?.destroy()
    }

    private enum class VideoMode { COPY, X264, NONE }

    private fun command(
        binary: File,
        sourceUrl: String,
        outputFile: File,
        filters: String?,
        duration: String,
        start: String,
        videoMode: VideoMode,
    ): List<String> = buildList {
        add(binary.absolutePath)
        add("-hide_banner")
        add("-loglevel")
        add("error")
        add("-y")
        add("-ss")
        add(start)
        add("-i")
        add(sourceUrl)
        add("-t")
        add(duration)
        when (videoMode) {
            VideoMode.NONE -> add("-vn")
            VideoMode.COPY -> {
                add("-c:v")
                add("copy")
            }
            VideoMode.X264 -> {
                add("-c:v")
                add("libx264")
                add("-preset")
                add("ultrafast")
                add("-crf")
                add("30")
            }
        }
        add("-c:a")
        add("aac")
        add("-b:a")
        add("160k")
        if (filters != null) {
            add("-af")
            add(filters)
        }
        add("-f")
        add("mp4")
        add(outputFile.absolutePath)
    }

    private fun readableFfmpegError(log: String): String {
        val trimmed = log.trim()
        return if (trimmed.isNotBlank()) {
            trimmed.lineSequence()
                .lastOrNull(String::isNotBlank)
                ?.take(240)
                ?.let { "O FFmpeg retornou erro: $it" }
                ?: "O FFmpeg não conseguiu gerar a prévia."
        } else {
            "O FFmpeg não conseguiu gerar a prévia."
        }
    }

    private fun formatSeconds(value: Float): String =
        String.format(Locale.US, "%.3f", value.coerceAtLeast(0f))
}

/**
 * The youtubedl-android FFmpeg 0.18.1 fork ships FFmpeg as a Position-Independent
 * Executable named `libffmpeg.so` inside the ABI-specific native library folder,
 * and its runtime dependencies are unpacked by `FFmpeg.init` into
 * `files/youtubedl-android/packages/ffmpeg/usr/lib` (a Termux prefix). The library
 * itself execs such `.so`-named binaries directly (e.g. `libpython.so`).
 */
fun resolveFfmpegBinary(context: Context): File {
    val binary = File(context.applicationInfo.nativeLibraryDir, "libffmpeg.so")
    if (binary.exists()) return binary
    throw IOException("O FFmpeg embutido não foi encontrado neste aparelho.")
}

private fun setEmbeddedFfmpegEnvironment(
    context: Context,
    environment: MutableMap<String, String>,
    binary: File,
) {
    environment["LD_LIBRARY_PATH"] = listOfNotNull(
        packagesUserLibDir(context, "python"),
        packagesUserLibDir(context, "ffmpeg"),
        binary.parentFile?.absolutePath,
    ).distinct().joinToString(File.pathSeparator)
    environment["TMPDIR"] = context.cacheDir.absolutePath
    environment["LANG"] = "C.UTF-8"
    environment["LC_ALL"] = "C.UTF-8"
    if (binary.canExecute().not()) {
        // PIE ELFs forged as `.so` must still be spawned through chmod +x.
        binary.setExecutable(true, false)
    }
}

private fun packagesUserLibDir(context: Context, packageName: String): File =
    File(
        context.noBackupFilesDir,
        "youtubedl-android/packages/$packageName/usr/lib",
    )

private const val TIMEOUT_SECONDS = 90L