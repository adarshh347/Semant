package com.semant.capture

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import com.semant.MainActivity
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class UploadNotifier @Inject constructor(@ApplicationContext private val context: Context) {
    private val manager = context.getSystemService(NotificationManager::class.java)

    init {
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL, "Uploads", NotificationManager.IMPORTANCE_DEFAULT))
    }

    fun notifyFailure(captureId: Long) {
        val intent = Intent(context, MainActivity::class.java).putExtra("open_queue", true)
        val pending = PendingIntent.getActivity(context, captureId.toInt(), intent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        runCatching {
            manager.notify(captureId.toInt(), NotificationCompat.Builder(context, CHANNEL)
                .setSmallIcon(android.R.drawable.stat_sys_warning)
                .setContentTitle("Semant upload failed")
                .setContentText("A captured image could not be uploaded. Tap to review.")
                .setContentIntent(pending)
                .setAutoCancel(true)
                .build())
        } // no POST_NOTIFICATIONS permission → silently skip; Queue screen still shows it
    }

    companion object { const val CHANNEL = "uploads" }
}
