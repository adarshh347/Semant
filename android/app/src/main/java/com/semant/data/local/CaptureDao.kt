package com.semant.data.local

import androidx.room.*
import kotlinx.coroutines.flow.Flow

@Dao
interface CaptureDao {
    @Insert suspend fun insert(capture: QueuedCapture): Long
    @Update suspend fun update(capture: QueuedCapture)
    @Query("SELECT * FROM queued_captures WHERE id = :id") suspend fun byId(id: Long): QueuedCapture?
    @Query("SELECT * FROM queued_captures ORDER BY createdAt DESC") fun observeAll(): Flow<List<QueuedCapture>>
    @Query("SELECT COUNT(*) FROM queued_captures WHERE status IN ('PENDING','UPLOADING','FAILED')")
    fun observeActiveCount(): Flow<Int>
    @Query("DELETE FROM queued_captures WHERE id = :id") suspend fun delete(id: Long)
    @Query("DELETE FROM queued_captures WHERE status = 'DONE' AND createdAt < :olderThan")
    suspend fun pruneDone(olderThan: Long)
}
