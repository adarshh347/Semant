package com.semant.gallery

import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import coil.compose.AsyncImage
import com.semant.data.remote.PostDto
import com.semant.ui.theme.Terracotta

@Composable
fun PostDetailScreen(viewModel: PostDetailViewModel = hiltViewModel()) {
    when (val s = viewModel.state.collectAsState().value) {
        PostDetailState.Loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
        is PostDetailState.Error -> Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center) {
            Text(s.message); Spacer(Modifier.height(8.dp))
            Button(onClick = viewModel::load) { Text("Retry") }
        }
        is PostDetailState.Loaded -> PostDetail(s.post)
    }
}

@Composable
private fun PostDetail(post: PostDto) {
    var scale by remember { mutableFloatStateOf(1f) }
    var offset by remember { mutableStateOf(Offset.Zero) }
    val transformState = rememberTransformableState { zoom, pan, _ ->
        scale = (scale * zoom).coerceIn(1f, 5f)
        offset += pan
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        AsyncImage(
            model = post.photoUrl,
            contentDescription = null,
            contentScale = ContentScale.FillWidth,
            modifier = Modifier
                .fillMaxWidth()
                .graphicsLayer(scaleX = scale, scaleY = scale, translationX = offset.x, translationY = offset.y)
                .transformable(transformState),
        )
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            post.generalTags?.takeIf { it.isNotEmpty() }?.let { tags ->
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    tags.take(6).forEach { AssistChip(onClick = {}, label = { Text(it) }) }
                }
            }
            (post.instagramHandles ?: listOfNotNull(post.instagramHandle)).takeIf { it.isNotEmpty() }?.let {
                Text("@" + it.joinToString(", @"), style = MaterialTheme.typography.bodyMedium, color = Terracotta)
            }
            post.textBlocks.forEach { block ->
                Text(block.content, style = when (block.type) {
                    "h1" -> MaterialTheme.typography.headlineMedium
                    "quote" -> MaterialTheme.typography.titleLarge
                    else -> MaterialTheme.typography.bodyLarge
                })
            }
            post.boundingBoxTags?.takeIf { it.isNotEmpty() }?.let { boxes ->
                Text("Regions", style = MaterialTheme.typography.titleMedium)
                boxes.keys.forEach { Text("· $it", style = MaterialTheme.typography.bodyMedium) }
            }
            post.localContext?.get("commentary")?.let {
                Text("Unconcealment", style = MaterialTheme.typography.titleMedium)
                Text(it.toString().trim('"'), style = MaterialTheme.typography.bodyLarge)
            }
        }
    }
}
