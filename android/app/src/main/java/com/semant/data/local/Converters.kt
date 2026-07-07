package com.semant.data.local

import androidx.room.TypeConverter

/**
 * Room has no built-in enum support, so persist [CaptureStatus] as its stable
 * name string. The DAO's status queries (e.g. IN ('PENDING','UPLOADING',...))
 * match these exact values.
 */
class Converters {
    @TypeConverter
    fun fromStatus(status: CaptureStatus): String = status.name

    @TypeConverter
    fun toStatus(value: String): CaptureStatus = CaptureStatus.valueOf(value)
}
