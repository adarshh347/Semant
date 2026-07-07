package com.semant.data

import com.semant.data.remote.SemantApi
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.kotlinxserialization.asConverterFactory

class PostRepositoryTest {
    private lateinit var server: MockWebServer
    private lateinit var repo: PostRepository

    @Before fun setUp() {
        server = MockWebServer().apply { start() }
        val json = Json { ignoreUnknownKeys = true; coerceInputValues = true }
        val api = Retrofit.Builder()
            .baseUrl(server.url("/"))
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(SemantApi::class.java)
        repo = PostRepository(api)
    }

    @After fun tearDown() = server.shutdown()

    @Test fun `parses paginated posts and ignores unknown fields`() = runTest {
        server.enqueue(MockResponse().setBody(
            """{"posts":[{"id":"abc","photo_url":"https://x/y.jpg","photo_public_id":"posts/1",
                "general_tags":["saree"],"unknown_field":42}],
                "total_pages":3,"current_page":1}"""
        ).addHeader("Content-Type", "application/json"))

        val page = repo.getPosts(page = 1)

        assertEquals(1, page.posts.size)
        assertEquals("abc", page.posts[0].id)
        assertEquals(listOf("saree"), page.posts[0].generalTags)
        assertEquals(3, page.totalPages)
        val recorded = server.takeRequest()
        assertEquals("/api/v1/posts/?page=1&limit=30", recorded.path)
    }
}
