package com.kiku.ui.today

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.kiku.ui.theme.Spacing

/**
 * Home. Answers one question in the first screenful: what should I do now?
 *
 * Order is deliberate: due reviews first (the thing that decays), then recent
 * clips, then import. No leaderboard, no streak-shaming.
 */
@Composable
fun TodayScreen(
    sharedMediaUri: Uri?,
    onOpenLesson: (String) -> Unit,
    onStartReview: () -> Unit,
    viewModel: TodayViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val snackbarHost = remember { SnackbarHostState() }
    var pendingMediaUri by remember { mutableStateOf(sharedMediaUri) }

    val pickSubtitle = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri ->
        uri?.let {
            viewModel.import(
                subtitleUri = it,
                title = it.lastPathSegment?.substringAfterLast('/'),
                mediaUri = pendingMediaUri,
            )
            pendingMediaUri = null
        }
    }

    LaunchedEffect(state.openClipId) {
        state.openClipId?.let {
            onOpenLesson(it)
            viewModel.consumeOpenClip()
        }
    }

    LaunchedEffect(state.error) {
        state.error?.let {
            snackbarHost.showSnackbar(it)
            viewModel.errorShown()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHost) },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = {
                    // Subtitle formats have unreliable MIME types, so accept
                    // everything and validate after reading.
                    pickSubtitle.launch(arrayOf("*/*"))
                },
                icon = { Icon(Icons.Outlined.Add, contentDescription = null) },
                text = { Text("Import clip") },
            )
        },
    ) { padding ->
        if (state.importing) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                CircularProgressIndicator()
                Spacer(Modifier.height(Spacing.md))
                Text("Building your lesson…", style = MaterialTheme.typography.bodyLarge)
                Text(
                    text = "Only the subtitles are sent. Your video stays on this phone.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            return@Scaffold
        }

        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = Spacing.md),
            verticalArrangement = Arrangement.spacedBy(Spacing.sm),
        ) {
            item {
                Text(
                    text = "Today",
                    style = MaterialTheme.typography.headlineMedium,
                    modifier = Modifier.padding(vertical = Spacing.md),
                )
            }

            state.progress?.let { progress ->
                item {
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(Spacing.md)) {
                            Text(
                                text = if (progress.dueNow > 0) {
                                    "${progress.dueNow} words to review"
                                } else {
                                    "All caught up"
                                },
                                style = MaterialTheme.typography.titleLarge,
                            )
                            Spacer(Modifier.height(Spacing.xs))
                            Text(
                                text = "${progress.savedWords} saved · " +
                                    "${progress.clipsImported} clips · " +
                                    "${progress.streakDays}-day streak",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            if (progress.dueNow > 0) {
                                Spacer(Modifier.height(Spacing.md))
                                Button(onClick = onStartReview) { Text("Start review") }
                            }
                        }
                    }
                }
            }

            item {
                Text(
                    text = "Your clips",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(top = Spacing.md, bottom = Spacing.xs),
                )
            }

            if (state.recent.isEmpty()) {
                item {
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(Spacing.md)) {
                            Text(
                                text = "Import a clip to begin",
                                style = MaterialTheme.typography.titleMedium,
                            )
                            Spacer(Modifier.height(Spacing.xs))
                            Text(
                                text = "Pick a .srt or .vtt file from a scene you like. " +
                                    "Kiku turns the dialogue into a lesson with romaji, " +
                                    "English and word notes.",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            } else {
                items(state.recent, key = { it.clipId }) { lesson ->
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onOpenLesson(lesson.clipId) },
                    ) {
                        Row(
                            modifier = Modifier.padding(Spacing.md),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(lesson.title, style = MaterialTheme.typography.titleMedium)
                                Text(
                                    text = "${lesson.level} · ${lesson.lineCount} lines",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                }
            }

            item { Spacer(Modifier.height(96.dp)) } // clear the FAB
        }
    }
}
