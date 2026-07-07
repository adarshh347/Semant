package com.semant.gallery

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.semant.data.PostRepository
import com.semant.data.remote.PostDto
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed interface PostDetailState {
    data object Loading : PostDetailState
    data class Loaded(val post: PostDto) : PostDetailState
    data class Error(val message: String) : PostDetailState
}

@HiltViewModel
class PostDetailViewModel @Inject constructor(
    private val repo: PostRepository,
    savedState: SavedStateHandle,
) : ViewModel() {
    private val postId: String = checkNotNull(savedState["postId"])
    private val _state = MutableStateFlow<PostDetailState>(PostDetailState.Loading)
    val state: StateFlow<PostDetailState> = _state

    init { load() }

    fun load() {
        _state.value = PostDetailState.Loading
        viewModelScope.launch {
            runCatching { repo.getPost(postId) }
                .onSuccess { _state.value = PostDetailState.Loaded(it) }
                .onFailure { _state.value = PostDetailState.Error(it.message ?: "Failed to load") }
        }
    }
}
