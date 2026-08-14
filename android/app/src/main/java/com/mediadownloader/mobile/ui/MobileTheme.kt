package com.mediadownloader.mobile.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val LightColors = lightColorScheme(
    primary = Color(0xFF146B4A),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFB9F1D2),
    onPrimaryContainer = Color(0xFF002114),
    inversePrimary = Color(0xFF94D5B4),
    secondary = Color(0xFF4E6357),
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Color(0xFFD1E8DA),
    onSecondaryContainer = Color(0xFF0B1F15),
    tertiary = Color(0xFF316775),
    onTertiary = Color(0xFFFFFFFF),
    tertiaryContainer = Color(0xFFB6EBF7),
    onTertiaryContainer = Color(0xFF001F26),
    error = Color(0xFFBA1A1A),
    onError = Color(0xFFFFFFFF),
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),
    background = Color(0xFFF6FAF7),
    onBackground = Color(0xFF181D1A),
    surface = Color(0xFFF9FDF9),
    onSurface = Color(0xFF181D1A),
    surfaceVariant = Color(0xFFDDE5DF),
    onSurfaceVariant = Color(0xFF414943),
    surfaceTint = Color(0xFF146B4A),
    inverseSurface = Color(0xFF2D322F),
    inverseOnSurface = Color(0xFFEFF2EF),
    outline = Color(0xFF717973),
    outlineVariant = Color(0xFFC1C9C3),
    scrim = Color(0xFF000000),
    surfaceBright = Color(0xFFF9FDF9),
    surfaceDim = Color(0xFFD7DBD7),
    surfaceContainerLowest = Color(0xFFFFFFFF),
    surfaceContainerLow = Color(0xFFF1F5F1),
    surfaceContainer = Color(0xFFEBEFEB),
    surfaceContainerHigh = Color(0xFFE5E9E5),
    surfaceContainerHighest = Color(0xFFDFE3DF),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF94D5B4),
    onPrimary = Color(0xFF003823),
    primaryContainer = Color(0xFF005237),
    onPrimaryContainer = Color(0xFFB9F1D2),
    inversePrimary = Color(0xFF146B4A),
    secondary = Color(0xFFB5CCBE),
    onSecondary = Color(0xFF20362A),
    secondaryContainer = Color(0xFF374D40),
    onSecondaryContainer = Color(0xFFD1E8DA),
    tertiary = Color(0xFF9CCFDA),
    onTertiary = Color(0xFF003640),
    tertiaryContainer = Color(0xFF164E5B),
    onTertiaryContainer = Color(0xFFB6EBF7),
    error = Color(0xFFFFB4AB),
    onError = Color(0xFF690005),
    errorContainer = Color(0xFF93000A),
    onErrorContainer = Color(0xFFFFDAD6),
    background = Color(0xFF101512),
    onBackground = Color(0xFFE0E4E0),
    surface = Color(0xFF101512),
    onSurface = Color(0xFFE0E4E0),
    surfaceVariant = Color(0xFF414943),
    onSurfaceVariant = Color(0xFFC1C9C3),
    surfaceTint = Color(0xFF94D5B4),
    inverseSurface = Color(0xFFE0E4E0),
    inverseOnSurface = Color(0xFF2D322F),
    outline = Color(0xFF8B938D),
    outlineVariant = Color(0xFF414943),
    scrim = Color(0xFF000000),
    surfaceBright = Color(0xFF353B37),
    surfaceDim = Color(0xFF101512),
    surfaceContainerLowest = Color(0xFF0A0F0C),
    surfaceContainerLow = Color(0xFF181D1A),
    surfaceContainer = Color(0xFF1C211E),
    surfaceContainerHigh = Color(0xFF262B28),
    surfaceContainerHighest = Color(0xFF313633),
)

private val AppTypography = Typography(
    displaySmall = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Bold,
        fontSize = 36.sp,
        lineHeight = 42.sp,
        letterSpacing = (-0.5).sp,
    ),
    headlineLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Bold,
        fontSize = 32.sp,
        lineHeight = 38.sp,
        letterSpacing = (-0.35).sp,
    ),
    headlineMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Bold,
        fontSize = 28.sp,
        lineHeight = 34.sp,
        letterSpacing = (-0.25).sp,
    ),
    headlineSmall = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Bold,
        fontSize = 24.sp,
        lineHeight = 30.sp,
    ),
    titleLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 20.sp,
        lineHeight = 26.sp,
    ),
    titleMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 16.sp,
        lineHeight = 22.sp,
        letterSpacing = 0.sp,
    ),
    titleSmall = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 14.sp,
        lineHeight = 20.sp,
    ),
    bodyLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Normal,
        fontSize = 16.sp,
        lineHeight = 24.sp,
    ),
    bodyMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        lineHeight = 21.sp,
    ),
    bodySmall = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Normal,
        fontSize = 12.sp,
        lineHeight = 18.sp,
    ),
    labelLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 14.sp,
        lineHeight = 20.sp,
        letterSpacing = 0.1.sp,
    ),
    labelMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 12.sp,
        lineHeight = 16.sp,
        letterSpacing = 0.15.sp,
    ),
    labelSmall = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Medium,
        fontSize = 11.sp,
        lineHeight = 16.sp,
        letterSpacing = 0.2.sp,
    ),
)

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(18.dp),
    large = RoundedCornerShape(24.dp),
    extraLarge = RoundedCornerShape(32.dp),
)

@Composable
fun MediaDownloaderTheme(
    preference: ThemePreference,
    content: @Composable () -> Unit,
) {
    val useDarkTheme = when (preference) {
        ThemePreference.SYSTEM -> isSystemInDarkTheme()
        ThemePreference.LIGHT -> false
        ThemePreference.DARK -> true
    }

    MaterialTheme(
        colorScheme = if (useDarkTheme) DarkColors else LightColors,
        typography = AppTypography,
        shapes = AppShapes,
        content = content,
    )
}
