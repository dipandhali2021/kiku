package com.kiku.ui.review

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.kiku.data.LessonRepository
import com.kiku.data.remote.WordDto
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ReviewUiState(
    val loading: Boolean = true,
    val queue: List<WordDto> = emptyList(),
    val revealed: Boolean = false,
    val reviewed: Int = 0,
    val streakDays: Int = 0,
    val error: String? = null,
) {
    val total: Int get() = reviewed + queue.size
    val progress: Float get() = if (total == 0) 0f else reviewed.toFloat() / total
}

@HiltViewModel
class ReviewViewModel @Inject constructor(
    private val repository: LessonRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(ReviewUiState())
    val state: StateFlow<ReviewUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            runCatching { repository.dueWords() }
                .onSuccess { due -> _state.update { it.copy(loading = false, queue = due) } }
                .onFailure { error ->
                    _state.update {
                        it.copy(loading = false, error = error.message ?: "Could not load reviews.")
                    }
                }
        }
    }

    fun reveal() = _state.update { it.copy(revealed = true) }

    /**
     * Grades the current card. The card is removed optimistically so the
     * session never stalls on a slow network; "Again" puts it back at the end
     * of the queue so it is retried in the same session.
     */
    fun grade(grade: Int) {
        val card = _state.value.queue.firstOrNull() ?: return
        _state.update { current ->
            val rest = current.queue.drop(1)
            current.copy(
                queue = if (grade == 0) rest + card else rest,
                revealed = false,
                reviewed = current.reviewed + 1,
            )
        }
        viewModelScope.launch {
            runCatching { repository.grade(card.id, grade) }
                .onSuccess { result -> _state.update { it.copy(streakDays = result.streakDays) } }
                .onFailure {
                    _state.update { it.copy(error = "That review did not sync. It will be due again.") }
                }
        }
    }
}
