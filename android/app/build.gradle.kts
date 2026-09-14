plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.mediadownloader.mobile"
    ndkVersion = "26.3.11579264"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.mediadownloader.mobile"
        minSdk = 26
        targetSdk = 36
        versionCode = generatedVersionCode()
        versionName = "1.2.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        ndk {
            abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64")
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        jniLibs.useLegacyPackaging = true
        resources.excludes += setOf(
            "/META-INF/{AL2.0,LGPL2.1}",
            "META-INF/DEPENDENCIES",
            "META-INF/NOTICE*",
        )
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        freeCompilerArgs.add("-Xannotation-default-target=param-property")
    }
}

// The FFmpeg PIE binary (`libffmpeg.so`) from youtubedl-android 0.18.1 links
// against libc++_shared.so, which the published AARs do not ship. Pull it from
// the NDK so the embedded FFmpeg can be spawned at runtime.
val ndkRoot: File? = android.ndkDirectory
val prebuiltLibDir: File? = ndkRoot?.let { root ->
    val prebuilt = File(root, "toolchains/llvm/prebuilt")
    listOf("windows-x86_64", "linux-x86_64", "darwin-x86_64", "darwin-arm64")
        .map { File(File(prebuilt, it), "sysroot/usr/lib") }
        .firstOrNull { it.isDirectory }
}
val cppSharedAbis = mapOf(
    "arm64-v8a" to "aarch64-linux-android",
    "armeabi-v7a" to "arm-linux-androideabi",
    "x86_64" to "x86_64-linux-android",
)
val generatedJniLibs = layout.buildDirectory.dir("generated/jniLibs")

val copyCppShared = tasks.register("copyCppSharedRuntime") {
    val ndk = ndkRoot
    val libDir = prebuiltLibDir
    inputs.property("ndkRoot", ndk?.absolutePath ?: "")
    outputs.dir(generatedJniLibs)
    doLast {
        if (ndk == null || libDir == null) {
            throw GradleException("NDK ausente em $ndk. Instale-o com scripts/setup_android.ps1 (pacote ndk;26.3.11579264).")
        }
        cppSharedAbis.forEach { (abi, triple) ->
            val source = File(libDir, "$triple/libc++_shared.so")
            if (!source.isFile) {
                throw GradleException("libc++_shared.so não encontrado em $source")
            }
            val target = File(generatedJniLibs.get().asFile, "$abi/libc++_shared.so")
            target.parentFile.mkdirs()
            source.copyTo(target, overwrite = true)
        }
    }
}

android.sourceSets.getByName("main").jniLibs.srcDir(generatedJniLibs)
tasks.configureEach {
    if (name.matches(Regex("merge.*JniLibFolders"))) {
        dependsOn(copyCppShared)
    }
}
tasks.named("preBuild").configure { dependsOn(copyCppShared) }

/**
 * Strictly increasing version code so every build replaces the previous one
 * in place, instead of forcing `adb install` to uninstall the app first.
 */
fun generatedVersionCode(): Int {
    val now = System.currentTimeMillis()
    val daysSince2020 = (now / 86_400_000L).toInt() - 18_262
    val minuteOfDay = ((now % 86_400_000L) / 60_000L).toInt()
    return 10_000 + daysSince2020 * 100 + minuteOfDay
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2025.12.01")
    val youtubeDlAndroid = "0.18.1"

    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.17.0")
    implementation("androidx.activity:activity-compose:1.12.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.10.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.10.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    implementation("com.google.zxing:core:3.5.4")
    implementation("androidx.media3:media3-exoplayer:1.7.1")
    implementation("androidx.media3:media3-ui:1.7.1")

    implementation("io.github.junkfood02.youtubedl-android:library:$youtubeDlAndroid")
    implementation("io.github.junkfood02.youtubedl-android:ffmpeg:$youtubeDlAndroid")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")
    androidTestImplementation("androidx.test.ext:junit:1.3.0")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.7.0")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
