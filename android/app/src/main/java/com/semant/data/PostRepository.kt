package com.semant.data

import com.semant.data.remote.PaginatedPostsDto
import com.semant.data.remote.PostDto
import com.semant.data.remote.SemantApi
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class PostRepository @Inject constructor(private val api: SemantApi) {
    suspend fun getPosts(page: Int, tag: String? = null): PaginatedPostsDto = api.getPosts(page = page, tag = tag)
    suspend fun getPost(id: String): PostDto = api.getPost(id)
    suspend fun getTags(): List<String> = api.getTags()
}
