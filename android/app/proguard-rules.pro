# yt-dlp/FFmpeg are invoked through their public Kotlin APIs. Keep Jackson mapper
# models because their fields are populated reflectively.
-keep class com.yausername.youtubedl_android.mapper.** { *; }
-keepattributes *Annotation*
