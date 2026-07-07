package com.semant.data.local

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class CaptureDaoTest {
    private lateinit var db: SemantDatabase
    private lateinit var dao: CaptureDao

    @Before fun setUp() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(context, SemantDatabase::class.java).build()
        dao = db.captureDao()
    }

    @After fun tearDown() = db.close()

    @Test fun `insert and observe pending captures`() = runTest {
        val id = dao.insert(QueuedCapture(localFilePath = "/x/a.jpg", tags = "saree", createdAt = 1000L))
        val all = dao.observeAll().first()
        assertEquals(1, all.size)
        assertEquals(CaptureStatus.PENDING, all[0].status)
        assertEquals(1, dao.observeActiveCount().first())

        dao.update(all[0].copy(status = CaptureStatus.DONE))
        assertEquals(0, dao.observeActiveCount().first())
        dao.delete(id)
        assertEquals(0, dao.observeAll().first().size)
    }
}
