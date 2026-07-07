package com.semant.gallery

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.paging.LoadState
import androidx.paging.compose.collectAsLazyPagingItems
import androidx.paging.compose.itemKey
import coil.compose.AsyncImage
import com.semant.data.remote.PostDto

@Composable
fun GalleryScreen(
    onOpenPost: (String) -> Unit,
    viewModel: GalleryViewModel = hiltViewModel(),
) {
    val posts = viewModel.posts.collectAsLazyPagingItems()
    val tags by viewModel.tags.collectAsState()
    val selected by viewModel.selectedTag.collectAsState()

    Column(Modifier.fillMaxSize()) {
        Text("Gallery", style = MaterialTheme.typography.headlineMedium,
            modifier = Modifier.padding(start = 20.dp, top = 16.dp, bottom = 8.dp))

        if (tags.isNotEmpty()) {
            LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp),
                contentPadding = PaddingValues(horizontal = 20.dp)) {
                items(tags) { tag ->
                    FilterChip(selected = tag == selected,
                        onClick = { viewModel.selectTag(if (tag == selected) null else tag) },
                        label = { Text(tag) })
                }
            }
        }

        when (posts.loadState.refresh) {
            is LoadState.Error -> Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center) {
                Text("Couldn't reach Semant", style = MaterialTheme.typography.titleMedium)
                Text("Check the base URL and API key in Settings",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(12.dp))
                Button(onClick = { posts.retry() }) { Text("Retry") }
            }
            is LoadState.Loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            else -> LazyVerticalGrid(
                columns = GridCells.Adaptive(minSize = 110.dp),
                contentPadding = PaddingValues(12.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                items(count = posts.itemCount, key = posts.itemKey { it.id }) { index ->
                    posts[index]?.let { post: PostDto ->
                        AsyncImage(
                            model = post.photoUrl,
                            contentDescription = post.generalTags?.joinToString(),
                            contentScale = ContentScale.Crop,
                            modifier = Modifier
                                .aspectRatio(1f)
                                .clip(MaterialTheme.shapes.medium)
                                .clickable { onOpenPost(post.id) },
                        )
                    }
                }
            }
        }
    }
}
