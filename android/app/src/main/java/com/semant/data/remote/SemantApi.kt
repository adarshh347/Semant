package com.semant.data.remote

import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.http.*

interface SemantApi {
    @GET("api/v1/posts/")
    suspend fun getPosts(
        @Query("page") page: Int,
        @Query("limit") limit: Int = 30,
        @Query("tag") tag: String? = null,
    ): PaginatedPostsDto

    @GET("api/v1/posts/{id}")
    suspend fun getPost(@Path("id") id: String): PostDto

    @GET("api/v1/posts/tags/")
    suspend fun getTags(): List<String>

    @Multipart
    @POST("api/v1/posts/")
    suspend fun uploadImage(
        @Part file: MultipartBody.Part,
        @Part("general_tags_str") generalTagsStr: RequestBody?,
    ): PostDto

    @POST("api/v1/posts/upload-from-url")
    suspend fun uploadFromUrl(@Body body: UrlUploadRequestDto): PostDto
}
