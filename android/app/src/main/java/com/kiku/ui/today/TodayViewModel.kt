package com.kiku.ui.today

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.kiku.data.LessonRepository
import com.kiku.data.auth.AuthRepository
import com.kiku.data.local.CachedLesson
import com.kiku.data.remote.ProgressDto
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class TodayUiState(
    val recent: List<CachedLesson> = emptyList(),
    val progress: ProgressDto? = null,
    val importing: Boolean = false,
    val error: String? = null,
    /** Set when an import finishes, so the UI can navigate into the lesson. */
    val openClipId: String? = null,
)

@HiltViewModel
class TodayViewModel @Inject constructor(
    private val repository: LessonRepository,
    private val auth: AuthRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(TodayUiState())
    val state: StateFlow<TodayUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            // Anonymous sign-in on first launch: no sign-up wall before value.
            runCatching { auth.ensureSignedIn() }
            refresh()
        }
        viewModelScope.launch {
            repository.observeRecent().collect { lessons ->
                _state.update { it.copy(recent = lessons) }
            }
        }
    }

    fun refresh() {
        viewModelScope.launch {
            runCatching { repository.progress() }
                .onSuccess { p -> _state.update { it.copy(progress = p) } }
        }
    }

    /**
     * Imports a subtitle file, optionally paired with a local video.
     * The video URI is stored on-device only.
     */
    fun import(subtitleUri: Uri, title: String?, mediaUri: Uri?) {
        _state.update { it.copy(importing = true, error = null) }
        viewModelScope.launch {
            runCatching { repository.importSubtitles(subtitleUri, title, mediaUri) }
                .onSuccess { lesson ->
                    _state.update { it.copy(importing = false, openClipId = lesson.clipId) }
                    refresh()
                }
                .onFailure { error ->
                    _state.update {
                        it.copy(
                            importing = false,
                            error = error.message ?: "That clip could not be imported.",
                        )
                    }
                }
        }
    }

    fun consumeOpenClip() = _state.update { it.copy(openClipId = null) }

    fun errorShown() = _state.update { it.copy(error = null) }
}
