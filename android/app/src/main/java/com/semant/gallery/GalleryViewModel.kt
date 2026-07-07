package com.semant.gallery

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.paging.Pager
import androidx.paging.PagingConfig
import androidx.paging.cachedIn
import com.semant.data.PostRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import javax.inject.Inject

@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class GalleryViewModel @Inject constructor(private val repo: PostRepository) : ViewModel() {
    private val _selectedTag = MutableStateFlow<String?>(null)
    val selectedTag: StateFlow<String?> = _selectedTag

    private val _tags = MutableStateFlow<List<String>>(emptyList())
    val tags: StateFlow<List<String>> = _tags

    val posts = _selectedTag.flatMapLatest { tag ->
        Pager(PagingConfig(pageSize = 30, initialLoadSize = 30)) { PostPagingSource(repo, tag) }.flow
    }.cachedIn(viewModelScope)

    init {
        viewModelScope.launch { runCatching { repo.getTags() }.onSuccess { _tags.value = it.filterNotNull() } }
    }

    fun selectTag(tag: String?) { _selectedTag.value = tag }
}
