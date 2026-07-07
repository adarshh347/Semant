package com.semant.capture

import android.content.Intent
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.semant.data.PostRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

sealed interface SharePayload {
    data class Images(val uris: List<Uri>) : SharePayload
    data class Link(val url: String) : SharePayload
    data object Invalid : SharePayload
}

data class ShareUiState(
    val payload: SharePayload = SharePayload.Invalid,
    val tags: String = "",
    val note: String = "",
    val knownTags: List<String> = emptyList(),
    val saving: Boolean = false,
    val done: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class ShareViewModel @Inject constructor(
    private val captures: CaptureRepository,
    private val posts: PostRepository,
) : ViewModel() {
    private val _state = MutableStateFlow(ShareUiState())
    val state: StateFlow<ShareUiState> = _state

    fun init(intent: Intent) {
        _state.value = _state.value.copy(payload = parse(intent))
        viewModelScope.launch {
            runCatching { posts.getTags() }.onSuccess {
                _state.value = _state.value.copy(knownTags = it.filterNotNull())
            } // offline is fine — autocomplete is a nicety
        }
    }

    fun setTags(v: String) { _state.value = _state.value.copy(tags = v) }
    fun setNote(v: String) { _state.value = _state.value.copy(note = v) }

    fun save() {
        val s = _state.value
        _state.value = s.copy(saving = true)
        viewModelScope.launch {
            runCatching {
                when (val p = s.payload) {
                    is SharePayload.Images -> p.uris.forEach { captures.enqueueImage(it, s.tags, s.note) }
                    is SharePayload.Link -> captures.enqueueUrl(p.url, s.tags, s.note)
                    SharePayload.Invalid -> error("Nothing shareable found")
                }
            }.onSuccess { _state.value = _state.value.copy(saving = false, done = true) }
             .onFailure { _state.value = _state.value.copy(saving = false, error = it.message) }
        }
    }

    private fun parse(intent: Intent): SharePayload = when (intent.action) {
        Intent.ACTION_SEND -> {
            @Suppress("DEPRECATION")
            val uri = intent.getParcelableExtra<Uri>(Intent.EXTRA_STREAM)
            val text = intent.getStringExtra(Intent.EXTRA_TEXT)
            when {
                uri != null -> SharePayload.Images(listOf(uri))
                text != null -> URL_REGEX.find(text)?.let { SharePayload.Link(it.value) } ?: SharePayload.Invalid
                else -> SharePayload.Invalid
            }
        }
        Intent.ACTION_SEND_MULTIPLE -> {
            @Suppress("DEPRECATION")
            val uris = intent.getParcelableArrayListExtra<Uri>(Intent.EXTRA_STREAM).orEmpty()
            if (uris.isEmpty()) SharePayload.Invalid else SharePayload.Images(uris)
        }
        else -> SharePayload.Invalid
    }

    companion object { val URL_REGEX = Regex("""https?://\S+""") }
}
