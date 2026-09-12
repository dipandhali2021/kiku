package com.kiku.ui.words

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

data class WordsUiState(
    val loading: Boolean = true,
    val words: List<WordDto> = emptyList(),
    val error: String? = null,
)

@HiltViewModel
class WordsViewModel @Inject constructor(
    private val repository: LessonRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(WordsUiState())
    val state: StateFlow<WordsUiState> = _state.asStateFlow()

    init {
        load()
    }

    fun load() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            runCatching { repository.listWords() }
                .onSuccess { words -> _state.update { it.copy(loading = false, words = words) } }
                .onFailure { error ->
                    _state.update {
                        it.copy(loading = false, error = error.message ?: "Could not load words.")
                    }
                }
        }
    }
}
