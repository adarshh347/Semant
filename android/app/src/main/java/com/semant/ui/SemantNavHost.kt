package com.semant.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudUpload
import androidx.compose.material.icons.filled.GridView
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.compose.*
import com.semant.gallery.GalleryScreen
import com.semant.gallery.PostDetailScreen
import com.semant.queue.QueueScreen
import com.semant.queue.QueueViewModel
import com.semant.settings.SettingsScreen

private data class Dest(val route: String, val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector)

@Composable
fun SemantNavHost(startOnQueue: Boolean = false) {
    val nav = rememberNavController()
    val dests = listOf(
        Dest("gallery", "Gallery", Icons.Default.GridView),
        Dest("queue", "Queue", Icons.Default.CloudUpload),
        Dest("settings", "Settings", Icons.Default.Settings),
    )
    val queueViewModel: QueueViewModel = hiltViewModel()
    val activeCount by queueViewModel.activeCount.collectAsState()

    Scaffold(bottomBar = {
        NavigationBar {
            val backStack by nav.currentBackStackEntryAsState()
            val current = backStack?.destination?.route
            dests.forEach { dest ->
                NavigationBarItem(
                    selected = current == dest.route,
                    onClick = { nav.navigate(dest.route) { popUpTo("gallery"); launchSingleTop = true } },
                    label = { Text(dest.label) },
                    icon = {
                        if (dest.route == "queue" && activeCount > 0)
                            BadgedBox(badge = { Badge { Text("$activeCount") } }) { Icon(dest.icon, dest.label) }
                        else Icon(dest.icon, dest.label)
                    },
                )
            }
        }
    }) { padding ->
        NavHost(nav, startDestination = if (startOnQueue) "queue" else "gallery", Modifier.padding(padding)) {
            composable("gallery") { GalleryScreen(onOpenPost = { nav.navigate("post/$it") }) }
            composable("post/{postId}") { PostDetailScreen() }
            composable("queue") { QueueScreen() }
            composable("settings") { SettingsScreen() }
        }
    }
}
