package com.semant.gallery

import androidx.paging.PagingSource
import androidx.paging.PagingState
import com.semant.data.PostRepository
import com.semant.data.remote.PostDto

class PostPagingSource(
    private val repo: PostRepository,
    private val tag: String?,
) : PagingSource<Int, PostDto>() {
    override suspend fun load(params: LoadParams<Int>): LoadResult<Int, PostDto> = try {
        val page = params.key ?: 1
        val result = repo.getPosts(page = page, tag = tag)
        LoadResult.Page(
            data = result.posts,
            prevKey = if (page > 1) page - 1 else null,
            nextKey = if (page < result.totalPages) page + 1 else null,
        )
    } catch (e: Exception) {
        LoadResult.Error(e)
    }

    override fun getRefreshKey(state: PagingState<Int, PostDto>): Int? =
        state.anchorPosition?.let { state.closestPageToPosition(it)?.prevKey?.plus(1) ?: 1 }
}
