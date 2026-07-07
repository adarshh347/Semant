package com.semant.data.di

import android.content.Context
import androidx.room.Room
import com.semant.data.local.CaptureDao
import com.semant.data.local.SemantDatabase
import com.semant.data.remote.ApiKeyInterceptor
import com.semant.data.remote.BaseUrlInterceptor
import com.semant.data.remote.SemantApi
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinxserialization.asConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {
    @Provides @Singleton
    fun provideJson(): Json = Json { ignoreUnknownKeys = true; coerceInputValues = true }

    @Provides @Singleton
    fun provideOkHttp(baseUrl: BaseUrlInterceptor, apiKey: ApiKeyInterceptor): OkHttpClient =
        OkHttpClient.Builder()
            .addInterceptor(baseUrl)
            .addInterceptor(apiKey)
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(120, TimeUnit.SECONDS)
            .build()

    @Provides @Singleton
    fun provideApi(client: OkHttpClient, json: Json): SemantApi =
        Retrofit.Builder()
            .baseUrl("http://localhost/") // always rewritten by BaseUrlInterceptor
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(SemantApi::class.java)

    @Provides @Singleton
    fun provideDb(@ApplicationContext context: Context): SemantDatabase =
        Room.databaseBuilder(context, SemantDatabase::class.java, "semant.db").build()

    @Provides
    fun provideCaptureDao(db: SemantDatabase): CaptureDao = db.captureDao()
}
