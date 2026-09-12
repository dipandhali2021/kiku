package com.kiku.di

import android.content.ContentResolver
import android.content.Context
import com.kiku.BuildConfig
import com.kiku.data.auth.AuthRepository
import com.kiku.data.remote.KikuApi
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import java.util.concurrent.TimeUnit
import javax.inject.Singleton
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun json(): Json = Json {
        ignoreUnknownKeys = true // server may add fields; old clients must not break
        encodeDefaults = false
        explicitNulls = false
    }

    @Provides
    @Singleton
    fun okHttp(auth: AuthRepository): OkHttpClient = OkHttpClient.Builder()
        // Lesson building runs MeCab plus an optional LLM call, and the free
        // backend tier cold-starts, so the read timeout is deliberately long.
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(90, TimeUnit.SECONDS)
        .addInterceptor { chain ->
            val request = chain.request()
            // The interceptor runs off the main thread already; runBlocking is
            // the sanctioned bridge to the suspending token getter.
            val token = runBlocking { auth.idToken() }
            val authorized = if (token == null) {
                request
            } else {
                request.newBuilder().header("Authorization", "Bearer $token").build()
            }
            chain.proceed(authorized)
        }
        .apply {
            if (BuildConfig.DEBUG) {
                addInterceptor(
                    HttpLoggingInterceptor().apply {
                        level = HttpLoggingInterceptor.Level.BASIC
                    },
                )
            }
        }
        .build()

    @Provides
    @Singleton
    fun retrofit(client: OkHttpClient, json: Json): Retrofit = Retrofit.Builder()
        .baseUrl(BuildConfig.API_BASE_URL)
        .client(client)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()

    @Provides
    @Singleton
    fun api(retrofit: Retrofit): KikuApi = retrofit.create(KikuApi::class.java)

    @Provides
    fun contentResolver(@ApplicationContext context: Context): ContentResolver =
        context.contentResolver
}
