package com.semant.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.semant.data.SettingsRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val settings: SettingsRepository,
    private val client: OkHttpClient,
) : ViewModel() {
    val baseUrl = settings.baseUrl.stateIn(viewModelScope, SharingStarted.Eagerly, SettingsRepository.DEFAULT_BASE_URL)
    val apiKey = settings.apiKey.stateIn(viewModelScope, SharingStarted.Eagerly, "")

    private val _testResult = MutableStateFlow<String?>(null)
    val testResult: StateFlow<String?> = _testResult

    fun saveBaseUrl(v: String) = viewModelScope.launch { settings.setBaseUrl(v) }
    fun saveApiKey(v: String) = viewModelScope.launch { settings.setApiKey(v) }

    fun testConnection() {
        _testResult.value = "Testing…"
        viewModelScope.launch {
            _testResult.value = withContext(Dispatchers.IO) {
                runCatching {
                    // BaseUrlInterceptor rewrites the host; path is what matters
                    val res = client.newCall(Request.Builder().url("http://localhost/health").build()).execute()
                    if (res.isSuccessful) "Connected ✓" else "Server said ${res.code}"
                }.getOrElse { "Failed: ${it.message}" }
            }
        }
    }
}
