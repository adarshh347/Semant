package com.semant.capture

import android.content.Context
import android.net.Uri
import androidx.work.*
import com.semant.data.local.CaptureDao
import com.semant.data.local.CaptureStatus
import com.semant.data.local.QueuedCapture
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import java.util.UUID
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class CaptureRepository @Inject constructor(
    @ApplicationContext private val context: Context,
    private val dao: CaptureDao,
) {
    /** Copy shared bytes into app-private storage (content URIs die with the sender). */
    fun copyToLocal(uri: Uri): File {
        val dir = File(context.filesDir, "captures").apply { mkdirs() }
        val dest = File(dir, "${UUID.randomUUID()}.img")
        context.contentResolver.openInputStream(uri).use { input ->
            requireNotNull(input) { "Cannot read shared content" }
            dest.outputStream().use { input.copyTo(it) }
        }
        require(dest.length() in 1..MAX_BYTES) { "Image is empty or larger than 25MB" }
        return dest
    }

    suspend fun enqueueImage(uri: Uri, tags: String, note: String, now: Long = System.currentTimeMillis()): Long {
        val file = copyToLocal(uri)
        val id = dao.insert(QueuedCapture(localFilePath = file.absolutePath, tags = tags, note = note, createdAt = now))
        scheduleUpload(id)
        return id
    }

    suspend fun enqueueUrl(url: String, tags: String, note: String, now: Long = System.currentTimeMillis()): Long {
        val id = dao.insert(QueuedCapture(sourceUrl = url, tags = tags, note = note, createdAt = now))
        scheduleUpload(id)
        return id
    }

    suspend fun retry(id: Long) {
        dao.byId(id)?.let { dao.update(it.copy(status = CaptureStatus.PENDING, attemptCount = 0, lastError = null)) }
        scheduleUpload(id)
    }

    suspend fun remove(capture: QueuedCapture) {
        capture.localFilePath?.let { File(it).delete() }
        dao.delete(capture.id)
    }

    fun scheduleUpload(id: Long) {
        val request = OneTimeWorkRequestBuilder<UploadWorker>()
            .setInputData(workDataOf(UploadWorker.KEY_CAPTURE_ID to id))
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork("upload-$id", ExistingWorkPolicy.KEEP, request)
    }

    companion object { const val MAX_BYTES = 25L * 1024 * 1024 }
}
