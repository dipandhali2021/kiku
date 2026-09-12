package com.kiku.data.remote

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/*
 * Wire models.
 *
 * Field names are snake_case on the server (FastAPI/Pydantic) and camelCase
 * here, bridged with @SerialName rather than a global naming strategy so each
 * mapping is explicit and greppable.
 */

@Serializable
data class WordChipDto(
    val surface: String,
    val lemma: String,
    val reading: String? = null,
    val romaji: String? = null,
    val meaning: String = "",
    val pos: String = "",
    val jlpt: String? = null,
    val note: String? = null,
    /** True when this lemma is already in the learner's saved words. */
    val known: Boolean = false,
    /** Punctuation and particles are rendered but not tappable. */
    val teachable: Boolean = true,
)

@Serializable
data class LessonLineDto(
    val index: Int = 0,
    val japanese: String,
    val romaji: String = "",
    val english: String = "",
    val note: String? = null,
    val speaker: String? = null,
    @SerialName("start_ms") val startMs: Long = 0,
    @SerialName("end_ms") val endMs: Long = 0,
    val words: List<WordChipDto> = emptyList(),
)

@Serializable
data class LessonDto(
    @SerialName("clip_id") val clipId: String,
    val title: String,
    val level: String = "N5",
    @SerialName("line_count") val lineCount: Int = 0,
    @SerialName("known_ratio") val knownRatio: Double = 0.0,
    @SerialName("new_word_count") val newWordCount: Int = 0,
    val engine: String? = null,
    val lines: List<LessonLineDto> = emptyList(),
)

@Serializable
data class LessonCreateDto(
    val subtitles: String,
    val title: String? = null,
    @SerialName("local_media_uri") val localMediaUri: String? = null,
    @SerialName("max_lines") val maxLines: Int? = null,
)

@Serializable
data class WordCreateDto(
    val lemma: String,
    val surface: String,
    val reading: String? = null,
    val romaji: String? = null,
    val meaning: String? = null,
    val jlpt: String? = null,
    @SerialName("context_japanese") val contextJapanese: String? = null,
    @SerialName("context_english") val contextEnglish: String? = null,
    @SerialName("clip_id") val clipId: String? = null,
    @SerialName("start_ms") val startMs: Long? = null,
    @SerialName("end_ms") val endMs: Long? = null,
)

@Serializable
data class WordDto(
    val id: Long,
    val lemma: String,
    val surface: String,
    val reading: String? = null,
    val romaji: String? = null,
    val meaning: String? = null,
    val jlpt: String? = null,
    @SerialName("context_japanese") val contextJapanese: String? = null,
    @SerialName("context_english") val contextEnglish: String? = null,
    @SerialName("clip_id") val clipId: String? = null,
    @SerialName("start_ms") val startMs: Long? = null,
    @SerialName("end_ms") val endMs: Long? = null,
    @SerialName("due_at") val dueAt: String? = null,
    val reps: Int = 0,
    val lapses: Int = 0,
)

@Serializable
data class ReviewCreateDto(
    @SerialName("word_id") val wordId: Long,
    /** 0 again, 1 hard, 2 good, 3 easy. */
    val grade: Int,
    @SerialName("elapsed_ms") val elapsedMs: Long? = null,
)

@Serializable
data class ReviewResultDto(
    @SerialName("word_id") val wordId: Long,
    @SerialName("due_at") val dueAt: String? = null,
    @SerialName("interval_days") val intervalDays: Double = 0.0,
    @SerialName("streak_days") val streakDays: Int = 0,
)

@Serializable
data class ProgressDto(
    @SerialName("saved_words") val savedWords: Int = 0,
    @SerialName("due_now") val dueNow: Int = 0,
    @SerialName("reviews_today") val reviewsToday: Int = 0,
    @SerialName("streak_days") val streakDays: Int = 0,
    @SerialName("clips_imported") val clipsImported: Int = 0,
)

@Serializable
data class ClipDto(
    val id: String,
    val title: String,
    val difficulty: String? = null,
    @SerialName("line_count") val lineCount: Int = 0,
    @SerialName("local_media_uri") val localMediaUri: String? = null,
)

/** Retrofit surface. One function per backend endpoint, nothing else. */
interface KikuApi {

    @POST("lessons")
    suspend fun createLesson(@Body body: LessonCreateDto): LessonDto

    @GET("lessons/{clipId}")
    suspend fun getLesson(@Path("clipId") clipId: String): LessonDto

    @GET("lessons")
    suspend fun listClips(): List<ClipDto>

    @POST("words")
    suspend fun saveWord(@Body body: WordCreateDto): WordDto

    @GET("words")
    suspend fun listWords(@Query("limit") limit: Int = 200): List<WordDto>

    @DELETE("words/{wordId}")
    suspend fun deleteWord(@Path("wordId") wordId: Long)

    @GET("reviews")
    suspend fun dueWords(@Query("limit") limit: Int = 20): List<WordDto>

    @POST("reviews")
    suspend fun submitReview(@Body body: ReviewCreateDto): ReviewResultDto

    @GET("progress")
    suspend fun progress(): ProgressDto
}
