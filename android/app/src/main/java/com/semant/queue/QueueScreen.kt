package com.semant.queue

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import coil.compose.AsyncImage
import com.semant.data.local.CaptureStatus
import java.io.File

@Composable
fun QueueScreen(viewModel: QueueViewModel = hiltViewModel()) {
    val items by viewModel.items.collectAsState()

    Column(Modifier.fillMaxSize()) {
        Text("Queue", style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(start = 20.dp, top = 16.dp, bottom = 8.dp))

        if (items.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("Nothing queued — share an image to Semant from any app",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            return
        }

        LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(items, key = { it.id }) { capture ->
                Card {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        AsyncImage(
                            model = capture.localFilePath?.let { File(it) } ?: capture.sourceUrl,
                            contentDescription = null,
                            contentScale = ContentScale.Crop,
                            modifier = Modifier.size(56.dp).clip(MaterialTheme.shapes.small),
                        )
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(capture.tags.ifBlank { "untagged" }, style = MaterialTheme.typography.titleMedium)
                            Text(
                                when (capture.status) {
                                    CaptureStatus.PENDING -> "Waiting for network…"
                                    CaptureStatus.UPLOADING -> "Uploading…"
                                    CaptureStatus.DONE -> "Uploaded"
                                    CaptureStatus.FAILED -> "Failed: ${capture.lastError ?: "unknown error"}"
                                },
                                style = MaterialTheme.typography.bodyMedium,
                                color = if (capture.status == CaptureStatus.FAILED) MaterialTheme.colorScheme.error
                                        else MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        if (capture.status == CaptureStatus.FAILED) {
                            IconButton(onClick = { viewModel.retry(capture.id) }) {
                                Icon(Icons.Default.Refresh, contentDescription = "Retry")
                            }
                        }
                        IconButton(onClick = { viewModel.remove(capture) }) {
                            Icon(Icons.Default.Delete, contentDescription = "Delete")
                        }
                    }
                }
            }
        }
    }
}
