package com.semant.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.TypeConverters

@Database(entities = [QueuedCapture::class], version = 1, exportSchema = false)
@TypeConverters(Converters::class)
abstract class SemantDatabase : RoomDatabase() {
    abstract fun captureDao(): CaptureDao
}
