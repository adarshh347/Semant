package com.semant.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.runBlocking
import javax.inject.Inject
import javax.inject.Singleton

private val Context.dataStore by preferencesDataStore(name = "settings")

@Singleton
class SettingsRepository @Inject constructor(@ApplicationContext private val context: Context) {
    private val BASE_URL = stringPreferencesKey("base_url")
    private val API_KEY = stringPreferencesKey("api_key")

    companion object { const val DEFAULT_BASE_URL = "https://sharirasutra.onrender.com" }

    val baseUrl: Flow<String> = context.dataStore.data.map { it[BASE_URL] ?: DEFAULT_BASE_URL }
    val apiKey: Flow<String> = context.dataStore.data.map { it[API_KEY] ?: "" }

    // Called from OkHttp interceptors on IO threads; DataStore read is fast.
    fun baseUrlBlocking(): String = runBlocking { baseUrl.first() }
    fun apiKeyBlocking(): String = runBlocking { apiKey.first() }

    suspend fun setBaseUrl(value: String) = context.dataStore.edit { it[BASE_URL] = value.trimEnd('/') }
    suspend fun setApiKey(value: String) = context.dataStore.edit { it[API_KEY] = value.trim() }
}
