package com.kiku

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.kiku.ui.KikuApp
import com.kiku.ui.theme.KikuTheme
import dagger.hilt.android.AndroidEntryPoint

/**
 * Single activity host.
 *
 * Accepts a shared video from any player or file app (see the SEND filter in
 * the manifest) so the user can start from the clip they are already watching
 * instead of hunting for it inside Kiku.
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val sharedMediaUri = sharedUri(intent)
        setContent {
            KikuTheme {
                KikuApp(sharedMediaUri = sharedMediaUri)
            }
        }
    }

    private fun sharedUri(intent: Intent?): Uri? = when (intent?.action) {
        Intent.ACTION_SEND -> intent.getParcelableExtra(Intent.EXTRA_STREAM)
        Intent.ACTION_VIEW -> intent.data
        else -> null
    }
}
