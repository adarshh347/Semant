package com.semant.capture

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.semant.data.local.CaptureDao
import com.semant.data.local.CaptureStatus
import com.semant.data.remote.SemantApi
import com.semant.data.remote.UrlUploadRequestDto
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.HttpException
import java.io.File

@HiltWorker
class UploadWorker @AssistedInject constructor(
    @Assisted context: Context,
    @Assisted params: WorkerParameters,
    private val dao: CaptureDao,
    private val api: SemantApi,
    private val notifier: UploadNotifier,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val id = inputData.getLong(KEY_CAPTURE_ID, -1)
        val capture = dao.byId(id) ?: return Result.success()
        if (capture.status == CaptureStatus.DONE) return Result.success()

        dao.update(capture.copy(status = CaptureStatus.UPLOADING, attemptCount = capture.attemptCount + 1))
        return try {
            if (capture.sourceUrl != null) {
                api.uploadFromUrl(UrlUploadRequestDto(
                    imageUrl = capture.sourceUrl,
                    generalTags = capture.tags.split(',').map { it.trim() }.filter { it.isNotEmpty() },
                ))
            } else {
                val file = File(requireNotNull(capture.localFilePath))
                val part = MultipartBody.Part.createFormData(
                    "file", "capture.jpg", file.asRequestBody("image/*".toMediaType()))
                val tagsBody = capture.tags.takeIf { it.isNotBlank() }?.toRequestBody("text/plain".toMediaType())
                api.uploadImage(part, tagsBody)
                file.delete()
            }
            dao.update(requireNotNull(dao.byId(id)).copy(status = CaptureStatus.DONE, lastError = null))
            Result.success()
        } catch (e: Exception) {
            val permanent = e is HttpException && e.code() in 400..499 && e.code() != 429
            val giveUp = permanent || runAttemptCount >= MAX_ATTEMPTS
            dao.update(requireNotNull(dao.byId(id)).copy(
                status = if (giveUp) CaptureStatus.FAILED else CaptureStatus.PENDING,
                lastError = e.message ?: e.javaClass.simpleName,
            ))
            if (giveUp) { notifier.notifyFailure(id); Result.failure() } else Result.retry()
        }
    }

    companion object {
        const val KEY_CAPTURE_ID = "capture_id"
        const val MAX_ATTEMPTS = 5
    }
}
