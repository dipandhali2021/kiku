package com.kiku.ui

import android.net.Uri
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Bookmark
import androidx.compose.material.icons.outlined.PlayCircle
import androidx.compose.material.icons.outlined.Today
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.kiku.ui.lesson.LessonScreen
import com.kiku.ui.review.ReviewScreen
import com.kiku.ui.today.TodayScreen
import com.kiku.ui.words.WordsScreen

/**
 * Three destinations, no more. The app has exactly three jobs: start something
 * today, watch a clip, and review what you saved. Anything else belongs behind
 * one of those.
 */
private enum class Tab(val route: String, val label: String, val icon: ImageVector) {
    Today("today", "Today", Icons.Outlined.Today),
    Review("review", "Review", Icons.Outlined.PlayCircle),
    Words("words", "Words", Icons.Outlined.Bookmark),
}

@Composable
fun KikuApp(sharedMediaUri: Uri? = null) {
    val navController = rememberNavController()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination

    // The lesson player is full-screen: a bottom bar there would compete with
    // the video and the word sheet.
    val showBottomBar = Tab.entries.any { tab ->
        currentRoute?.hierarchy?.any { it.route == tab.route } == true
    }

    Scaffold(
        bottomBar = {
            if (showBottomBar) {
                NavigationBar {
                    Tab.entries.forEach { tab ->
                        val selected = currentRoute?.hierarchy?.any { it.route == tab.route } == true
                        NavigationBarItem(
                            selected = selected,
                            onClick = {
                                navController.navigate(tab.route) {
                                    popUpTo(Tab.Today.route) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = { Icon(tab.icon, contentDescription = null) },
                            label = { Text(tab.label) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = Tab.Today.route,
            modifier = Modifier.padding(padding),
        ) {
            composable(Tab.Today.route) {
                TodayScreen(
                    sharedMediaUri = sharedMediaUri,
                    onOpenLesson = { clipId -> navController.navigate("lesson/$clipId") },
                    onStartReview = { navController.navigate(Tab.Review.route) },
                )
            }
            composable(Tab.Review.route) {
                ReviewScreen(onFinished = { navController.popBackStack() })
            }
            composable(Tab.Words.route) {
                WordsScreen(onOpenLesson = { clipId -> navController.navigate("lesson/$clipId") })
            }
            composable("lesson/{clipId}") { entry ->
                LessonScreen(
                    clipId = entry.arguments?.getString("clipId").orEmpty(),
                    onClose = { navController.popBackStack() },
                )
            }
        }
    }
}
