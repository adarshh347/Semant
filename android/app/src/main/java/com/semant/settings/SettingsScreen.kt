package com.semant.settings

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@Composable
fun SettingsScreen(viewModel: SettingsViewModel = hiltViewModel()) {
    val savedBaseUrl by viewModel.baseUrl.collectAsState()
    val savedApiKey by viewModel.apiKey.collectAsState()
    val testResult by viewModel.testResult.collectAsState()

    var baseUrl by remember(savedBaseUrl) { mutableStateOf(savedBaseUrl) }
    var apiKey by remember(savedApiKey) { mutableStateOf(savedApiKey) }

    Column(Modifier.fillMaxSize().padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Settings", style = MaterialTheme.typography.headlineMedium)
        OutlinedTextField(value = baseUrl, onValueChange = { baseUrl = it },
            label = { Text("Backend URL") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(value = apiKey, onValueChange = { apiKey = it },
            label = { Text("API key") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { viewModel.saveBaseUrl(baseUrl); viewModel.saveApiKey(apiKey) }) { Text("Save") }
            OutlinedButton(onClick = { viewModel.saveBaseUrl(baseUrl); viewModel.saveApiKey(apiKey); viewModel.testConnection() }) {
                Text("Test connection")
            }
        }
        testResult?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
    }
}
