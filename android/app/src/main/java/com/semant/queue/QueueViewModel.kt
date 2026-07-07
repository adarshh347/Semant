package com.semant.queue

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.semant.capture.CaptureRepository
import com.semant.data.local.CaptureDao
import com.semant.data.local.QueuedCapture
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class QueueViewModel @Inject constructor(
    dao: CaptureDao,
    private val captures: CaptureRepository,
) : ViewModel() {
    val items = dao.observeAll().stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
    val activeCount = dao.observeActiveCount().stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), 0)

    fun retry(id: Long) = viewModelScope.launch { captures.retry(id) }
    fun remove(capture: QueuedCapture) = viewModelScope.launch { captures.remove(capture) }
}
