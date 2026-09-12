package com.kiku.ui.words

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.kiku.ui.theme.KikuType
import com.kiku.ui.theme.Spacing

/** Saved words, newest first, each still carrying the sentence it came from. */
@Composable
fun WordsScreen(
    onOpenLesson: (String) -> Unit,
    viewModel: WordsViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = Spacing.md),
        verticalArrangement = Arrangement.spacedBy(Spacing.sm),
    ) {
        item {
            Text(
                text = "Words",
                style = MaterialTheme.typography.headlineMedium,
                modifier = Modifier.padding(vertical = Spacing.md),
            )
        }

        if (state.words.isEmpty() && !state.loading) {
            item {
                Text(
                    text = "Tap any word in a lesson to save it here.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        items(state.words, key = { it.id }) { word ->
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { word.clipId?.let(onOpenLesson) },
            ) {
                Column(Modifier.padding(Spacing.md)) {
                    Text(word.surface, style = KikuType.japaneseDense)
                    word.romaji?.let {
                        Text(
                            text = it,
                            style = KikuType.romajiLine,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    word.meaning?.let {
                        Spacer(Modifier.height(Spacing.xs))
                        Text(it, style = MaterialTheme.typography.bodyMedium)
                    }
                    word.contextJapanese?.let {
                        Spacer(Modifier.height(Spacing.sm))
                        Text(
                            text = it,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }

        item { Spacer(Modifier.height(Spacing.xl)) }
    }
}
