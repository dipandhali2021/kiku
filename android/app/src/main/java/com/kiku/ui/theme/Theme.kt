package com.kiku.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Material 3 theme for Kiku.
 *
 * Design rule: the app chrome stays quiet so the Japanese text is the loudest
 * thing on screen. We take M3 defaults almost everywhere and only customise
 * the type scale used for dialogue, where size and line height genuinely
 * matter for readability of kanji.
 */

// Fallback palette, used below Android 12 where dynamic color is unavailable.
// Seeded from a deep indigo: calm, readable at night, not Duolingo green.
private val SeedLight = lightColorScheme(
    primary = Color(0xFF3B5BDB),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDCE1FF),
    onPrimaryContainer = Color(0xFF00164E),
    secondary = Color(0xFF585E71),
    tertiary = Color(0xFF1F7A5A),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFB8F2D8),
    onTertiaryContainer = Color(0xFF00241A),
    error = Color(0xFFBA1A1A),
    surface = Color(0xFFFDFBFF),
    onSurface = Color(0xFF1B1B1F),
    onSurfaceVariant = Color(0xFF45464F),
    outlineVariant = Color(0xFFC6C6D0),
)

private val SeedDark = darkColorScheme(
    primary = Color(0xFFB8C3FF),
    onPrimary = Color(0xFF00287B),
    primaryContainer = Color(0xFF1E3FAE),
    onPrimaryContainer = Color(0xFFDCE1FF),
    secondary = Color(0xFFC0C6DC),
    tertiary = Color(0xFF9CD6BC),
    onTertiary = Color(0xFF00382A),
    tertiaryContainer = Color(0xFF005140),
    onTertiaryContainer = Color(0xFFB8F2D8),
    error = Color(0xFFFFB4AB),
    surface = Color(0xFF1B1B1F),
    onSurface = Color(0xFFE4E1E6),
    onSurfaceVariant = Color(0xFFC6C6D0),
    outlineVariant = Color(0xFF45464F),
)

/**
 * Type styles for dialogue. Not part of the M3 scale because the scale has no
 * slot for "large Japanese sentence with tappable words".
 *
 * Kanji needs more line height than Latin text at the same size, and romaji
 * sits directly under the Japanese, so it is deliberately one step quieter.
 */
object KikuType {
    val japaneseLine = TextStyle(
        fontSize = 30.sp,
        lineHeight = 46.sp,
        fontWeight = FontWeight.Medium,
        letterSpacing = 0.sp,
    )
    val japaneseDense = TextStyle(
        fontSize = 22.sp,
        lineHeight = 34.sp,
        fontWeight = FontWeight.Medium,
    )
    val romajiLine = TextStyle(
        fontSize = 15.sp,
        lineHeight = 22.sp,
        letterSpacing = 0.2.sp,
    )
}

/** Spacing scale. Multiples of 4dp, with 48dp as the minimum touch target. */
object Spacing {
    val xs = 4.dp
    val sm = 8.dp
    val md = 16.dp
    val lg = 24.dp
    val xl = 32.dp
    val touchTarget = 48.dp
}

@Composable
fun KikuTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    // Dynamic color makes the app feel native to the user's device. It is the
    // single highest-value M3 feature and costs nothing.
    dynamicColor: Boolean = true,
    content: @Composable () -> Unit,
) {
    val context = LocalContext.current
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        darkTheme -> SeedDark
        else -> SeedLight
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography(),
        content = content,
    )
}
