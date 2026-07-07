package com.semant.capture

import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.semant.ui.theme.SemantTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class ShareActivity : ComponentActivity() {
    private val viewModel: ShareViewModel by viewModels()

    @OptIn(ExperimentalMaterial3Api::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        viewModel.init(intent)

        setContent {
            SemantTheme {
                val state by viewModel.state.collectAsState()
                val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)

                LaunchedEffect(state.done, state.error) {
                    if (state.done) {
                        Toast.makeText(this@ShareActivity, "Saved to Semant queue", Toast.LENGTH_SHORT).show()
                        finish()
                    }
                    state.error?.let {
                        Toast.makeText(this@ShareActivity, it, Toast.LENGTH_LONG).show()
                        if (state.payload == SharePayload.Invalid) finish()
                    }
                }

                ModalBottomSheet(onDismissRequest = { finish() }, sheetState = sheetState) {
                    Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 32.dp)) {
                        Text("Save to Semant", style = MaterialTheme.typography.titleLarge)
                        Spacer(Modifier.height(12.dp))

                        when (val p = state.payload) {
                            is SharePayload.Images -> LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                items(p.uris) { uri ->
                                    AsyncImage(model = uri, contentDescription = null,
                                        modifier = Modifier.size(96.dp), contentScale = ContentScale.Crop)
                                }
                            }
                            is SharePayload.Link -> Text(p.url, style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 2)
                            SharePayload.Invalid -> Text("Nothing shareable found")
                        }

                        Spacer(Modifier.height(16.dp))
                        OutlinedTextField(value = state.tags, onValueChange = viewModel::setTags,
                            label = { Text("Tags (comma-separated)") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
                        if (state.knownTags.isNotEmpty()) {
                            Spacer(Modifier.height(8.dp))
                            LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                items(state.knownTags.take(20)) { tag ->
                                    SuggestionChip(onClick = {
                                        val cur = state.tags.split(',').map { it.trim() }.filter { it.isNotEmpty() }
                                        if (tag !in cur) viewModel.setTags((cur + tag).joinToString(", "))
                                    }, label = { Text(tag) })
                                }
                            }
                        }
                        Spacer(Modifier.height(8.dp))
                        OutlinedTextField(value = state.note, onValueChange = viewModel::setNote,
                            label = { Text("Note (optional)") }, modifier = Modifier.fillMaxWidth())
                        Spacer(Modifier.height(16.dp))
                        Button(onClick = viewModel::save, enabled = !state.saving && state.payload != SharePayload.Invalid,
                            modifier = Modifier.fillMaxWidth()) {
                            Text(if (state.saving) "Saving…" else "Save")
                        }
                    }
                }
            }
        }
    }
}
