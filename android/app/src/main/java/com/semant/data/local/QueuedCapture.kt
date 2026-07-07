package com.semant.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

enum class CaptureStatus { PENDING, UPLOADING, FAILED, DONE }

@Entity(tableName = "queued_captures")
data class QueuedCapture(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val localFilePath: String? = null,   // set for shared image bytes
    val sourceUrl: String? = null,       // set for shared URLs (Chrome)
    val tags: String = "",               // comma-separated
    val note: String = "",
    val status: CaptureStatus = CaptureStatus.PENDING,
    val attemptCount: Int = 0,
    val lastError: String? = null,
    val createdAt: Long,
)
