package com.kiku.di

import android.content.Context
import androidx.room.Room
import com.google.firebase.auth.FirebaseAuth
import com.kiku.data.local.KikuDatabase
import com.kiku.data.local.LessonDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun firebaseAuth(): FirebaseAuth = FirebaseAuth.getInstance()

    @Provides
    @Singleton
    fun database(@ApplicationContext context: Context): KikuDatabase =
        Room.databaseBuilder(context, KikuDatabase::class.java, "kiku.db")
            // The local database is a cache of server state, so a destructive
            // migration is acceptable until the schema stabilises.
            .fallbackToDestructiveMigration()
            .build()

    @Provides
    fun lessonDao(db: KikuDatabase): LessonDao = db.lessonDao()
}
