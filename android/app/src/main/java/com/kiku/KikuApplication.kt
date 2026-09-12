package com.kiku

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

/** Hilt entry point. Kept empty on purpose: startup work belongs in the screens. */
@HiltAndroidApp
class KikuApplication : Application()
