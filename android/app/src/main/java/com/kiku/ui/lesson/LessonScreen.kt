package com.kiku.ui.lesson

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.outlined.BookmarkBorder
import androidx.compose.material.icons.outlined.Close
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.kiku.data.remote.WordChipDto
import com.kiku.ui.theme.KikuType
import com.kiku.ui.theme.Spacing

/**
 * The core screen: one line of dialogue at a time.
 *
 * Design decisions worth keeping:
 *  - One line fills the screen. Scrolling walls of subtitles is how immersion
 *    apps lose beginners.
 *  - Every word is a tap target; tapping never leaves the screen, it opens a
 *    sheet, so the learner keeps their place.
 *  - English is hidden until requested, forcing a guess first.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LessonScreen(
    clipId: String,
    onClose: () -> Unit,
    viewModel: LessonViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val snackbarHost = remember { SnackbarHostState() }
    val sheetState = rememberModalBottomSheetState()

    LaunchedEffect(state.message) {
        state.message?.let {
            snackbarHost.showSnackbar(it)
            viewModel.messageShown()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHost) },
        topBar = {
            TopAppBar(
                title = { Text(state.lesson?.title ?: "Lesson", maxLines = 1) },
                navigationIcon = {
                    IconButton(onClick = onClose) {
                        Icon(Icons.Outlined.Close, contentDescription = "Close lesson")
                    }
                },
                actions = {
                    TextButton(onClick = viewModel::toggleRomaji) {
                        Text(if (state.showRomaji) "Hide romaji" else "Show romaji")
                    }
                },
            )
        },
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentAlignment = Alignment.Center,
        ) {
            when {
                state.loading -> CircularProgressIndicator()

                state.error != null -> ErrorState(state.error!!, viewModel::load)

                else -> LessonContent(
                    state = state,
                    onWordTap = viewModel::selectWord,
                    onReveal = viewModel::revealEnglish,
                    onNext = { if (state.isLastLine) onClose() else viewModel.nextLine() },
                    onPrevious = viewModel::previousLine,
                )
            }
        }
    }

    state.selectedWord?.let { word ->
        ModalBottomSheet(
            onDismissRequest = { viewModel.selectWord(null) },
            sheetState = sheetState,
        ) {
            WordSheet(
                word = word,
                saved = word.lemma in state.savedLemmas,
                onSave = { viewModel.saveWord(word) },
            )
        }
    }
}

@Composable
private fun LessonContent(
    state: LessonUiState,
    onWordTap: (WordChipDto) -> Unit,
    onReveal: () -> Unit,
    onNext: () -> Unit,
    onPrevious: () -> Unit,
) {
    val line = state.line ?: return

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = Spacing.md),
        verticalArrangement = Arrangement.SpaceBetween,
    ) {
        Column {
            LinearProgressIndicator(
                progress = { state.progress },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = Spacing.sm),
            )
            line.speaker?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
        }

        Column(
            modifier = Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.Center,
        ) {
            // Tappable word chips. FlowRow keeps natural line wrapping while
            // giving every word its own 48dp-tall touch target.
            androidx.compose.foundation.layout.FlowRow(
                horizontalArrangement = Arrangement.spacedBy(Spacing.xs),
                verticalArrangement = Arrangement.spacedBy(Spacing.xs),
            ) {
                line.words.forEach { word ->
                    WordChip(
                        word = word,
                        saved = word.lemma in state.savedLemmas,
                        onTap = { if (word.teachable) onWordTap(word) },
                    )
                }
            }

            if (state.showRomaji) {
                Spacer(Modifier.height(Spacing.sm))
                Text(
                    text = line.romaji,
                    style = KikuType.romajiLine,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Spacer(Modifier.height(Spacing.lg))

            if (state.showEnglish) {
                Text(line.english, style = MaterialTheme.typography.bodyLarge)
                line.note?.let {
                    Spacer(Modifier.height(Spacing.sm))
                    Surface(
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        shape = RoundedCornerShape(12.dp),
                    ) {
                        Text(
                            text = it,
                            style = MaterialTheme.typography.bodyMedium,
                            modifier = Modifier.padding(Spacing.md),
                        )
                    }
                }
            } else {
                FilledTonalButton(onClick = onReveal) { Text("Show meaning") }
            }
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = Spacing.md),
            horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
        ) {
            if (state.lineIndex > 0) {
                FilledTonalButton(onClick = onPrevious) { Text("Back") }
            }
            Button(onClick = onNext, modifier = Modifier.weight(1f)) {
                Text(if (state.isLastLine) "Finish" else "Next line")
            }
        }
    }
}

@Composable
private fun WordChip(word: WordChipDto, saved: Boolean, onTap: () -> Unit) {
    val background = when {
        saved -> MaterialTheme.colorScheme.tertiaryContainer
        word.teachable -> MaterialTheme.colorScheme.surfaceVariant
        else -> MaterialTheme.colorScheme.surface
    }
    Box(
        modifier = Modifier
            .background(background, RoundedCornerShape(8.dp))
            .clickable(enabled = word.teachable, onClick = onTap)
            .padding(horizontal = Spacing.sm, vertical = Spacing.xs),
    ) {
        Text(text = word.surface, style = KikuType.japaneseLine)
    }
}

@Composable
private fun WordSheet(word: WordChipDto, saved: Boolean, onSave: () -> Unit) {
    Column(Modifier.padding(Spacing.lg)) {
        Text(word.surface, style = KikuType.japaneseLine)
        Text(
            text = listOfNotNull(word.reading, word.romaji).joinToString("  ·  "),
            style = KikuType.romajiLine,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(Spacing.md))
        Text(word.meaning, style = MaterialTheme.typography.bodyLarge)

        Row(Modifier.padding(top = Spacing.sm)) {
            Text(word.pos, style = MaterialTheme.typography.labelMedium)
            word.jlpt?.let {
                Spacer(Modifier.width(Spacing.sm))
                Text(it, style = MaterialTheme.typography.labelMedium)
            }
        }

        // The nuance note is the reason to build this app rather than use a
        // dictionary: why this form, in this sentence.
        word.note?.let {
            Spacer(Modifier.height(Spacing.md))
            Surface(
                color = MaterialTheme.colorScheme.surfaceVariant,
                shape = RoundedCornerShape(12.dp),
            ) {
                Text(
                    text = it,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(Spacing.md),
                )
            }
        }

        Spacer(Modifier.height(Spacing.lg))
        Button(
            onClick = onSave,
            enabled = !saved,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Icon(
                imageVector = if (saved) Icons.Filled.Bookmark else Icons.Outlined.BookmarkBorder,
                contentDescription = null,
            )
            Spacer(Modifier.width(Spacing.sm))
            Text(if (saved) "Saved for review" else "Save for review")
        }
        Spacer(Modifier.height(Spacing.md))
    }
}

@Composable
private fun ErrorState(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier.padding(Spacing.xl),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(message, textAlign = TextAlign.Center, style = MaterialTheme.typography.bodyLarge)
        Spacer(Modifier.height(Spacing.md))
        Button(onClick = onRetry) { Text("Try again") }
    }
}
