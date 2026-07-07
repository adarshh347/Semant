package com.semant.capture

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.work.ListenableWorker.Result
import androidx.work.testing.TestListenableWorkerBuilder
import androidx.work.WorkerFactory
import androidx.work.WorkerParameters
import com.semant.data.local.CaptureStatus
import com.semant.data.local.QueuedCapture
import com.semant.data.local.SemantDatabase
import com.semant.data.remote.SemantApi
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import retrofit2.Retrofit
import retrofit2.converter.kotlinxserialization.asConverterFactory
import java.io.File

@RunWith(RobolectricTestRunner::class)
class UploadWorkerTest {
    private lateinit var context: Context
    private lateinit var server: MockWebServer
    private lateinit var db: SemantDatabase
    private lateinit var api: SemantApi
    private lateinit var notifier: UploadNotifier

    private val postJson = """{"id":"p1","photo_url":"https://x/y.jpg","photo_public_id":"posts/1"}"""

    @Before fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        server = MockWebServer().apply { start() }
        db = Room.inMemoryDatabaseBuilder(context, SemantDatabase::class.java).build()
        val json = Json { ignoreUnknownKeys = true; coerceInputValues = true }
        api = Retrofit.Builder().baseUrl(server.url("/"))
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build().create(SemantApi::class.java)
        notifier = UploadNotifier(context)
    }

    @After fun tearDown() { server.shutdown(); db.close() }

    private fun buildWorker(captureId: Long): UploadWorker =
        TestListenableWorkerBuilder<UploadWorker>(context)
            .setInputData(androidx.work.workDataOf(UploadWorker.KEY_CAPTURE_ID to captureId))
            .setWorkerFactory(object : WorkerFactory() {
                override fun createWorker(c: Context, cls: String, p: WorkerParameters) =
                    UploadWorker(c, p, db.captureDao(), api, notifier)
            }).build() as UploadWorker

    @Test fun `file upload success marks DONE and deletes local file`() = runTest {
        server.enqueue(MockResponse().setResponseCode(201).setBody(postJson)
            .addHeader("Content-Type", "application/json"))
        val file = File(context.filesDir, "t.img").apply { writeBytes(byteArrayOf(1, 2, 3)) }
        val id = db.captureDao().insert(QueuedCapture(localFilePath = file.absolutePath, tags = "saree", createdAt = 1L))

        val result = buildWorker(id).doWork()

        assertEquals(Result.success(), result)
        assertEquals(CaptureStatus.DONE, db.captureDao().byId(id)!!.status)
        assertTrue(!file.exists())
        assertTrue(server.takeRequest().headers["Content-Type"]!!.startsWith("multipart/"))
    }

    @Test fun `url upload hits upload-from-url`() = runTest {
        server.enqueue(MockResponse().setResponseCode(201).setBody(postJson)
            .addHeader("Content-Type", "application/json"))
        val id = db.captureDao().insert(QueuedCapture(sourceUrl = "https://img.example/a.jpg", tags = "", createdAt = 1L))

        val result = buildWorker(id).doWork()

        assertEquals(Result.success(), result)
        assertEquals("/api/v1/posts/upload-from-url", server.takeRequest().path)
    }

    @Test fun `server 500 retries and keeps PENDING`() = runTest {
        server.enqueue(MockResponse().setResponseCode(500))
        val file = File(context.filesDir, "t2.img").apply { writeBytes(byteArrayOf(1)) }
        val id = db.captureDao().insert(QueuedCapture(localFilePath = file.absolutePath, createdAt = 1L))

        val result = buildWorker(id).doWork()

        assertEquals(Result.retry(), result)
        assertEquals(CaptureStatus.PENDING, db.captureDao().byId(id)!!.status)
        assertTrue(file.exists())  // kept for retry
    }

    @Test fun `client 4xx fails permanently`() = runTest {
        server.enqueue(MockResponse().setResponseCode(422).setBody("bad"))
        val id = db.captureDao().insert(QueuedCapture(sourceUrl = "https://img.example/a.jpg", createdAt = 1L))

        val result = buildWorker(id).doWork()

        assertEquals(Result.failure(), result)
        assertEquals(CaptureStatus.FAILED, db.captureDao().byId(id)!!.status)
    }
}
