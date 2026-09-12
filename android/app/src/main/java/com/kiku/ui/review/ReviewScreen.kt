package com.kiku.ui.review

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.kiku.ui.theme.KikuType
import com.kiku.ui.theme.Spacing

/**
 * Review session.
 *
 * Cards show the word inside the sentence it was learned from, because a word
 * recalled only in isolation is not usable. Four grades map to the FSRS-style
 * scheduler on the server.
 */
@Composable
fun ReviewScreen(
    onFinished: () -> Unit,
    viewModel: ReviewViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(Spacing.md),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        when {
            state.loading -> CircularProgressIndicator()

            state.queue.isEmpty() -> {
                Text(
                    text = "Nothing due right now.",
                    style = MaterialTheme.typography.headlineSmall,
                    textAlign = TextAlign.Center,
                )
                Spacer(Modifier.height(Spacing.sm))
                Text(
                    text = "Come back later, or import a clip to learn something new.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                )
                Spacer(Modifier.height(Spacing.lg))
                Button(onClick = onFinished) { Text("Done") }
            }

            else -> {
                val card = state.queue.first()
                LinearProgressIndicator(
                    progress = { state.progress },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = Spacing.lg),
                )

                Text(card.surface, style = KikuType.japaneseLine)

                if (state.revealed) {
                    Spacer(Modifier.height(Spacing.sm))
                    card.romaji?.let {
                        Text(
                            text = it,
                            style = KikuType.romajiLine,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Spacer(Modifier.height(Spacing.md))
                    Text(
                        text = card.meaning.orEmpty(),
                        style = MaterialTheme.typography.bodyLarge,
                        textAlign = TextAlign.Center,
                    )
                    card.contextJapanese?.let {
                        Spacer(Modifier.height(Spacing.lg))
                        Text(
                            text = it,
                            style = KikuType.japaneseDense,
                            textAlign = TextAlign.Center,
                        )
                    }
                    card.contextEnglish?.let {
                        Text(
                            text = it,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            textAlign = TextAlign.Center,
                        )
                    }

                    Spacer(Modifier.height(Spacing.xl))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(Spacing.sm),
                    ) {
                        OutlinedButton(
                            onClick = { viewModel.grade(0) },
                            modifier = Modifier.weight(1f),
                        ) { Text("Again") }
                        OutlinedButton(
                            onClick = { viewModel.grade(1) },
                            modifier = Modifier.weight(1f),
                        ) { Text("Hard") }
                        Button(
                            onClick = { viewModel.grade(2) },
                            modifier = Modifier.weight(1f),
                        ) { Text("Good") }
                        FilledTonalButton(
                            onClick = { viewModel.grade(3) },
                            modifier = Modifier.weight(1f),
                        ) { Text("Easy") }
                    }
                } else {
                    Spacer(Modifier.height(Spacing.xl))
                    Button(onClick = viewModel::reveal, modifier = Modifier.fillMaxWidth()) {
                        Text("Show answer")
                    }
                }
            }
        }
    }
}
