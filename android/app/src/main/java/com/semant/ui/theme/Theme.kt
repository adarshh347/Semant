package com.semant.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColors = lightColorScheme(
    primary = Terracotta,
    onPrimary = PaperSurface,
    primaryContainer = TerracottaSoft,
    onPrimaryContainer = TerracottaDeep,
    background = PaperBg,
    onBackground = PaperInk,
    surface = PaperSurface,
    onSurface = PaperInk,
    surfaceVariant = PaperSurface2,
    onSurfaceVariant = PaperInkMuted,
    outline = PaperLine,
)

private val DarkColors = darkColorScheme(
    primary = TerracottaDark,
    onPrimary = InkBg,
    primaryContainer = TerracottaSoftDark,
    onPrimaryContainer = TerracottaDark,
    background = InkBg,
    onBackground = InkText,
    surface = InkSurface,
    onSurface = InkText,
    surfaceVariant = InkSurface2,
    onSurfaceVariant = InkTextMuted,
    outline = InkLine,
)

@Composable
fun SemantTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        typography = SemantTypography,
        content = content,
    )
}
