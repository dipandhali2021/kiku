package com.kiku.ui.lesson

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.kiku.data.LessonRepository
import com.kiku.data.remote.LessonDto
import com.kiku.data.remote.LessonLineDto
import com.kiku.data.remote.WordChipDto
import com.kiku.data.remote.WordCreateDto
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class LessonUiState(
    val loading: Boolean = true,
    val error: String? = null,
    val lesson: LessonDto? = null,
    val lineIndex: Int = 0,
    /** Romaji is a crutch, so it can be hidden per line without losing place. */
    val showRomaji: Boolean = true,
    val showEnglish: Boolean = false,
    val selectedWord: WordChipDto? = null,
    val savedLemmas: Set<String> = emptySet(),
    val message: String? = null,
) {
    val line: LessonLineDto? get() = lesson?.lines?.getOrNull(lineIndex)
    val isLastLine: Boolean get() = lesson != null && lineIndex >= lesson.lines.lastIndex
    val progress: Float
        get() = lesson?.lines?.size?.takeIf { it > 0 }?.let { (lineIndex + 1f) / it } ?: 0f
}

@HiltViewModel
class LessonViewModel @Inject constructor(
    private val repository: LessonRepository,
    savedState: SavedStateHandle,
) : ViewModel() {

    private val clipId: String = savedState["clipId"] ?: ""

    private val _state = MutableStateFlow(LessonUiState())
    val state: StateFlow<LessonUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            runCatching { repository.lesson(clipId) }
                .onSuccess { lesson ->
                    _state.update {
                        it.copy(
                            loading = false,
                            lesson = lesson,
                            savedLemmas = lesson.lines
                                .flatMap(LessonLineDto::words)
                                .filter(WordChipDto::known)
                                .map(WordChipDto::lemma)
                                .toSet(),
                        )
                    }
                }
                .onFailure { throwable ->
                    _state.update {
                        it.copy(
                            loading = false,
                            error = throwable.message ?: "Could not load that lesson.",
                        )
                    }
                }
        }
    }

    fun selectWord(word: WordChipDto?) = _state.update { it.copy(selectedWord = word) }

    fun toggleRomaji() = _state.update { it.copy(showRomaji = !it.showRomaji) }

    /** English stays hidden until asked for, so the learner guesses first. */
    fun revealEnglish() = _state.update { it.copy(showEnglish = true) }

    fun nextLine() = _state.update {
        if (it.isLastLine) it else it.copy(
            lineIndex = it.lineIndex + 1,
            showEnglish = false,
            selectedWord = null,
        )
    }

    fun previousLine() = _state.update {
        it.copy(
            lineIndex = (it.lineIndex - 1).coerceAtLeast(0),
            showEnglish = false,
            selectedWord = null,
        )
    }

    fun saveWord(word: WordChipDto) {
        val line = _state.value.line
        // Optimistic: the chip fills in immediately. A failed save only costs
        // a toast, and pretending otherwise makes the tap feel broken.
        _state.update { it.copy(savedLemmas = it.savedLemmas + word.lemma, selectedWord = null) }
        viewModelScope.launch {
            runCatching {
                repository.saveWord(
                    WordCreateDto(
                        lemma = word.lemma,
                        surface = word.surface,
                        reading = word.reading,
                        romaji = word.romaji,
                        meaning = word.meaning,
                        contextJapanese = line?.japanese,
                        contextEnglish = line?.english,
                        clipId = clipId,
                    ),
                )
            }
                .onSuccess { _state.update { s -> s.copy(message = "Saved \u201c${word.surface}\u201d") } }
                .onFailure {
                    _state.update { s ->
                        s.copy(
                            savedLemmas = s.savedLemmas - word.lemma,
                            message = "Could not save that word. Try again.",
                        )
                    }
                }
        }
    }

    fun messageShown() = _state.update { it.copy(message = null) }
}
