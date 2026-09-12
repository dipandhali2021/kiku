package com.kiku.data

import android.content.ContentResolver
import android.net.Uri
import com.kiku.data.auth.AuthRepository
import com.kiku.data.local.CachedLesson
import com.kiku.data.local.LessonDao
import com.kiku.data.remote.KikuApi
import com.kiku.data.remote.LessonCreateDto
import com.kiku.data.remote.LessonDto
import com.kiku.data.remote.ProgressDto
import com.kiku.data.remote.ReviewCreateDto
import com.kiku.data.remote.ReviewResultDto
import com.kiku.data.remote.WordCreateDto
import com.kiku.data.remote.WordDto
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json

/** Single entry point for lesson data. Cache first, network second. */
@Singleton
class LessonRepository @Inject constructor(
    private val api: KikuApi,
    private val dao: LessonDao,
    private val auth: AuthRepository,
    private val json: Json,
    private val contentResolver: ContentResolver,
) {

    fun observeRecent(): Flow<List<CachedLesson>> = dao.observeRecent()

    /**
     * Imports a subtitle file and returns the built lesson.
     *
     * Only the subtitle text is uploaded. [mediaUri] is persisted locally so
     * the player can find the video again; it is never sent to the server.
     */
    suspend fun importSubtitles(
        subtitleUri: Uri,
        title: String?,
        mediaUri: Uri?,
    ): LessonDto = withContext(Dispatchers.IO) {
        auth.ensureSignedIn()
        val text = readText(subtitleUri)
        require(text.isNotBlank()) { "That subtitle file is empty." }

        val lesson = api.createLesson(
            LessonCreateDto(
                subtitles = text,
                title = title,
                localMediaUri = mediaUri?.toString(),
            ),
        )
        cache(lesson, mediaUri?.toString())
        lesson
    }

    /** Reads from cache immediately, then refreshes known-word marks online. */
    suspend fun lesson(clipId: String): LessonDto = withContext(Dispatchers.IO) {
        val cached = dao.find(clipId)?.let { json.decodeFromString<LessonDto>(it.payload) }
        runCatching { api.getLesson(clipId) }
            .onSuccess { cache(it, dao.find(clipId)?.localMediaUri) }
            .getOrNull()
            ?: cached
            ?: error("That lesson is not available offline yet.")
    }

    suspend fun saveWord(word: WordCreateDto): WordDto = withContext(Dispatchers.IO) {
        api.saveWord(word)
    }

    suspend fun dueWords(limit: Int = 20): List<WordDto> = withContext(Dispatchers.IO) {
        api.dueWords(limit)
    }

    suspend fun grade(wordId: Long, grade: Int): ReviewResultDto = withContext(Dispatchers.IO) {
        api.submitReview(ReviewCreateDto(wordId = wordId, grade = grade))
    }

    suspend fun progress(): ProgressDto = withContext(Dispatchers.IO) { api.progress() }

    suspend fun attachMedia(clipId: String, uri: Uri) = dao.setMediaUri(clipId, uri.toString())

    private suspend fun cache(lesson: LessonDto, mediaUri: String?) {
        dao.upsert(
            CachedLesson(
                clipId = lesson.clipId,
                title = lesson.title,
                level = lesson.level,
                lineCount = lesson.lineCount,
                localMediaUri = mediaUri,
                payload = json.encodeToString(LessonDto.serializer(), lesson),
            ),
        )
    }

    private fun readText(uri: Uri): String {
        // Subtitle files in the wild are often Shift_JIS rather than UTF-8;
        // decoding blind produces mojibake, so sniff before trusting UTF-8.
        val bytes = contentResolver.openInputStream(uri)?.use { it.readBytes() }
            ?: error("Could not open that file.")
        val utf8 = bytes.toString(Charsets.UTF_8)
        return if (utf8.contains('\uFFFD')) {
            bytes.toString(charset("Shift_JIS"))
        } else {
            utf8.removePrefix("\uFEFF")
        }
    }
}
