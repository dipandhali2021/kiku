package com.kiku.data.local

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import kotlinx.coroutines.flow.Flow

/**
 * Offline cache.
 *
 * A lesson is stored as the raw JSON payload the server returned. It is an
 * immutable artifact keyed by content hash, so there is nothing to gain from
 * shredding it into relational tables, and keeping it whole means an imported
 * clip opens instantly on a train with no signal.
 */
@Entity(tableName = "cached_lessons")
data class CachedLesson(
    @PrimaryKey val clipId: String,
    val title: String,
    val level: String,
    val lineCount: Int,
    val localMediaUri: String?,
    val payload: String,
    val importedAt: Long = System.currentTimeMillis(),
)

@Dao
interface LessonDao {

    @Query("SELECT * FROM cached_lessons ORDER BY importedAt DESC LIMIT :limit")
    fun observeRecent(limit: Int = 30): Flow<List<CachedLesson>>

    @Query("SELECT * FROM cached_lessons WHERE clipId = :clipId")
    suspend fun find(clipId: String): CachedLesson?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(lesson: CachedLesson)

    @Query("UPDATE cached_lessons SET localMediaUri = :uri WHERE clipId = :clipId")
    suspend fun setMediaUri(clipId: String, uri: String?)

    @Query("DELETE FROM cached_lessons WHERE clipId = :clipId")
    suspend fun delete(clipId: String)
}

@Database(entities = [CachedLesson::class], version = 1, exportSchema = true)
abstract class KikuDatabase : RoomDatabase() {
    abstract fun lessonDao(): LessonDao
}
