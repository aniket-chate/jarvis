package com.jarvis.client.voice.calibration

import android.content.Context
import android.util.Log
import com.google.gson.Gson
import com.google.gson.GsonBuilder
import java.io.File
import java.io.FileReader
import java.io.FileWriter

/**
 * Manages user-scoped local persistence of calibration profiles in private app storage.
 * Performs atomic writes to prevent file corruption.
 */
class CalibrationStorageManager(
    private val context: Context,
    private val gson: Gson = GsonBuilder().setPrettyPrinting().create()
) {

    private val tag = "CalibrationStorage"

    private val calibrationDir: File by lazy {
        val dir = File(context.filesDir, "calibration")
        if (!dir.exists()) {
            dir.mkdirs()
        }
        dir
    }

    private fun getProfileFile(userId: String): File {
        val safeUserId = userId.trim().replace(Regex("[^a-zA-Z0-9_-]"), "_").ifBlank { "default_user" }
        return File(calibrationDir, "profile_$safeUserId.json")
    }

    /**
     * Loads the saved calibration profile for a specific user ID.
     */
    fun loadProfile(userId: String): CalibrationProfile? {
        val file = getProfileFile(userId)
        if (!file.exists() || !file.isFile) {
            return null
        }

        return try {
            FileReader(file).use { reader ->
                gson.fromJson(reader, CalibrationProfile::class.java)
            }
        } catch (e: Exception) {
            Log.e(tag, "Failed to load calibration profile for user '$userId': ${e.message}", e)
            null
        }
    }

    /**
     * Atomically saves a calibration profile for the user.
     */
    fun saveProfile(profile: CalibrationProfile): Boolean {
        val targetFile = getProfileFile(profile.userId)
        val tempFile = File(calibrationDir, "${targetFile.name}.tmp")

        return try {
            FileWriter(tempFile).use { writer ->
                gson.toJson(profile, writer)
            }
            if (tempFile.exists()) {
                if (targetFile.exists()) {
                    targetFile.delete()
                }
                val success = tempFile.renameTo(targetFile)
                if (success) {
                    Log.i(tag, "Saved calibration profile for user '${profile.userId}' (samples: ${profile.sampleSummaries.size}, thr: ${profile.recommendation.recommendedThreshold})")
                    true
                } else {
                    Log.e(tag, "Failed to rename temp file to ${targetFile.name}")
                    false
                }
            } else {
                false
            }
        } catch (e: Exception) {
            Log.e(tag, "Failed to save calibration profile for user '${profile.userId}': ${e.message}", e)
            try {
                if (tempFile.exists()) tempFile.delete()
            } catch (_: Exception) {}
            false
        }
    }

    /**
     * Deletes the calibration profile for a specific user ID.
     */
    fun deleteProfile(userId: String): Boolean {
        val file = getProfileFile(userId)
        return if (file.exists()) {
            file.delete()
        } else {
            true
        }
    }

    /**
     * Lists all saved calibration profiles across users.
     */
    fun listProfiles(): List<CalibrationProfile> {
        val files = calibrationDir.listFiles { _, name -> name.startsWith("profile_") && name.endsWith(".json") }
            ?: return emptyList()

        val profiles = mutableListOf<CalibrationProfile>()
        for (f in files) {
            try {
                FileReader(f).use { reader ->
                    val p = gson.fromJson(reader, CalibrationProfile::class.java)
                    if (p != null) {
                        profiles.add(p)
                    }
                }
            } catch (e: Exception) {
                Log.w(tag, "Error reading profile from ${f.name}: ${e.message}")
            }
        }
        return profiles
    }
}
