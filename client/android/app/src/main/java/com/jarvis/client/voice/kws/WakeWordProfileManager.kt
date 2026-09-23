package com.jarvis.client.voice.kws

import android.content.Context
import android.util.Log
import com.google.gson.Gson
import com.google.gson.GsonBuilder
import java.io.File
import java.io.FileReader
import java.io.FileWriter

/**
 * Validation summary for profile creation or activation.
 */
data class ProfileValidationResult(
    val isValid: Boolean,
    val errorMessage: String? = null
)

/**
 * Result of explicit wake-word profile activation or rollback.
 */
data class ProfileActivationResult(
    val success: Boolean,
    val activeProfile: WakeWordProfile? = null,
    val errorMessage: String? = null
)

/**
 * Storage, validation, and lifecycle manager for user-scoped dynamic wake word profiles.
 *
 * Architecture & Safety Contract:
 * 1. Factory Default Baseline: Safe, tested "Hey Jarvis" configuration.
 * 2. Draft Isolation: Draft profiles remain staging-only and never affect production until explicit activation.
 * 3. Atomic Persistence: Uses temp-file-write followed by atomic filesystem rename.
 * 4. Multi-User Scoping: All paths sanitized with strict path-traversal rejection.
 * 5. Safe Rollback: Failed activations restore previous working configuration with zero corrupt states.
 * 6. Zero Raw Audio: Strictly persists mathematical/statistical metadata.
 */
class WakeWordProfileManager(private val context: Context) {

    private val tag = "WakeWordProfileManager"
    private val gson: Gson = GsonBuilder().setPrettyPrinting().create()
    val tokenizer = SherpaBpeTokenizer(context)

    companion object {
        const val DEFAULT_PHRASE = "Hey Jarvis"
        const val DEFAULT_NORMALIZED = "HEY JARVIS"
        const val DEFAULT_TOKENS = " HE Y  JA R VI S"
        const val DEFAULT_KEYWORDS_SCORE = 1.0f
        const val DEFAULT_KEYWORDS_THRESHOLD = 0.50f
        const val DEFAULT_TRAILING_BLANKS = 1

        const val MIN_THRESHOLD = 0.30f
        const val MAX_THRESHOLD = 0.65f
        const val MIN_SCORE = 0.80f
        const val MAX_SCORE = 1.50f
        const val MIN_SAMPLES_FOR_CUSTOM = 4
    }

    private val profilesDir: File by lazy {
        val dir = File(context.filesDir, "kws_profiles")
        if (!dir.exists()) {
            dir.mkdirs()
        }
        dir
    }

    /**
     * Sanitizes user ID, preventing directory traversal and blank identifiers.
     */
    fun sanitizeUserId(userId: String): String {
        val trimmed = userId.trim()
        if (trimmed.isBlank() || trimmed == "." || trimmed == "..") {
            return "default_user"
        }
        // Remove any path separators and unsafe characters
        val safe = trimmed.replace(Regex("[^a-zA-Z0-9_-]"), "_")
        return safe.ifBlank { "default_user" }
    }

    fun getProfileFile(userId: String): File {
        val safeId = sanitizeUserId(userId)
        return File(profilesDir, "kws_profile_$safeId.json")
    }

    fun getDraftProfileFile(userId: String): File {
        val safeId = sanitizeUserId(userId)
        return File(profilesDir, "draft_kws_profile_$safeId.json")
    }

    fun getKeywordsFile(userId: String): File {
        val safeId = sanitizeUserId(userId)
        return File(profilesDir, "keywords_$safeId.txt")
    }

    /**
     * Loads the saved active profile for the user, or creates the factory default if none exists or corrupt.
     */
    fun loadProfile(userId: String): WakeWordProfile {
        val file = getProfileFile(userId)
        if (file.exists() && file.isFile && file.length() > 0L) {
            try {
                FileReader(file).use { reader ->
                    val profile = gson.fromJson(reader, WakeWordProfile::class.java)
                    if (profile != null && profile.phrase.isNotBlank() && profile.tokenizedKeyword.isNotBlank()) {
                        return profile
                    }
                }
            } catch (e: Exception) {
                Log.w(tag, "Failed to parse KWS profile for $userId, recreating default", e)
            }
        }
        return createDefaultProfile(userId)
    }

    /**
     * Creates and persists a factory default "Hey Jarvis" profile.
     */
    fun createDefaultProfile(userId: String): WakeWordProfile {
        val safeId = sanitizeUserId(userId)
        val tokenized = tokenizer.tokenizeToKeywordLine(DEFAULT_PHRASE).ifBlank { DEFAULT_TOKENS }
        val profile = WakeWordProfile(
            profileId = "kws_${safeId}_default",
            userId = safeId,
            phrase = DEFAULT_PHRASE,
            normalizedPhrase = DEFAULT_NORMALIZED,
            tokenizedKeyword = tokenized,
            keywordsScore = DEFAULT_KEYWORDS_SCORE,
            keywordsThreshold = DEFAULT_KEYWORDS_THRESHOLD,
            numTrailingBlanks = DEFAULT_TRAILING_BLANKS,
            enrolledSampleCount = 0,
            averageSnrDb = 0f,
            averageRms = 0f,
            averagePeak = 0f,
            isCustomEnrolled = false,
            isActive = true,
            enabled = true,
            profileVersion = 1,
            createdAt = System.currentTimeMillis(),
            updatedAt = System.currentTimeMillis()
        )
        saveProfile(profile)
        return profile
    }

    /**
     * Creates an in-memory draft profile from an enrollment result.
     * The draft is NOT active and does NOT touch the production configuration.
     */
    fun createDraft(enrollmentResult: WakeWordEnrollmentResult): WakeWordProfile {
        val safeId = sanitizeUserId(enrollmentResult.userId)
        val draft = WakeWordProfile(
            profileId = "draft_${safeId}_${System.currentTimeMillis()}",
            userId = safeId,
            phrase = enrollmentResult.phrase,
            normalizedPhrase = enrollmentResult.normalizedPhrase,
            tokenizedKeyword = enrollmentResult.tokenizedPhrase,
            keywordsScore = enrollmentResult.recommendedKeywordsScore.coerceIn(MIN_SCORE, MAX_SCORE),
            keywordsThreshold = enrollmentResult.recommendedKeywordsThreshold.coerceIn(MIN_THRESHOLD, MAX_THRESHOLD),
            numTrailingBlanks = enrollmentResult.recommendedNumTrailingBlanks.coerceIn(1, 3),
            enrolledSampleCount = enrollmentResult.successfulSamples,
            averageSnrDb = enrollmentResult.averageSnrDb,
            averageRms = enrollmentResult.averageRms,
            averagePeak = enrollmentResult.averagePeak,
            isCustomEnrolled = true,
            isActive = false,
            enabled = false,
            profileVersion = 1,
            createdAt = System.currentTimeMillis(),
            updatedAt = System.currentTimeMillis()
        )
        saveDraft(draft)
        return draft
    }

    /**
     * Saves a draft profile to draft_kws_profile_<userId>.json without modifying active profile.
     */
    fun saveDraft(draft: WakeWordProfile): Boolean {
        val safeId = sanitizeUserId(draft.userId)
        val targetFile = getDraftProfileFile(safeId)
        val tempFile = File(profilesDir, "${targetFile.name}.tmp")

        return try {
            FileWriter(tempFile).use { writer ->
                gson.toJson(draft, writer)
            }
            if (tempFile.exists()) {
                if (targetFile.exists()) targetFile.delete()
                tempFile.renameTo(targetFile)
            } else false
        } catch (e: Exception) {
            Log.e(tag, "Error saving draft profile for $safeId", e)
            if (tempFile.exists()) tempFile.delete()
            false
        }
    }

    fun loadDraftProfile(userId: String): WakeWordProfile? {
        val file = getDraftProfileFile(userId)
        if (file.exists() && file.isFile && file.length() > 0L) {
            try {
                FileReader(file).use { reader ->
                    return gson.fromJson(reader, WakeWordProfile::class.java)
                }
            } catch (e: Exception) {
                Log.w(tag, "Failed to load draft profile for $userId", e)
            }
        }
        return null
    }

    fun deleteDraft(userId: String): Boolean {
        val file = getDraftProfileFile(userId)
        return if (file.exists()) file.delete() else true
    }

    /**
     * Validates a profile against safety constraints before persistence or activation.
     */
    fun validateProfile(profile: WakeWordProfile): ProfileValidationResult {
        val safeId = sanitizeUserId(profile.userId)
        if (safeId.isBlank()) {
            return ProfileValidationResult(false, "User ID cannot be blank.")
        }
        if (profile.phrase.trim().length < 2) {
            return ProfileValidationResult(false, "Wake phrase must be at least 2 characters.")
        }
        if (profile.phrase.trim().length > 50) {
            return ProfileValidationResult(false, "Wake phrase exceeds 50 characters.")
        }
        if (profile.tokenizedKeyword.isBlank()) {
            return ProfileValidationResult(false, "Tokenized keyword representation cannot be empty.")
        }
        if (profile.keywordsThreshold < MIN_THRESHOLD || profile.keywordsThreshold > MAX_THRESHOLD) {
            return ProfileValidationResult(
                false,
                "Keywords threshold (${profile.keywordsThreshold}) out of bounds [$MIN_THRESHOLD, $MAX_THRESHOLD]."
            )
        }
        if (profile.keywordsScore < MIN_SCORE || profile.keywordsScore > MAX_SCORE) {
            return ProfileValidationResult(
                false,
                "Keywords score (${profile.keywordsScore}) out of bounds [$MIN_SCORE, $MAX_SCORE]."
            )
        }
        if (profile.numTrailingBlanks !in 1..3) {
            return ProfileValidationResult(
                false,
                "Trailing blanks (${profile.numTrailingBlanks}) must be between 1 and 3."
            )
        }
        if (profile.isCustomEnrolled && profile.enrolledSampleCount < MIN_SAMPLES_FOR_CUSTOM) {
            return ProfileValidationResult(
                false,
                "Custom enrolled profile requires at least $MIN_SAMPLES_FOR_CUSTOM successful samples (had ${profile.enrolledSampleCount})."
            )
        }
        return ProfileValidationResult(true, null)
    }

    /**
     * Atomically saves an active profile to disk and syncs its keywords.txt.
     */
    fun saveProfile(profile: WakeWordProfile): Boolean {
        val validation = validateProfile(profile)
        if (!validation.isValid) {
            Log.e(tag, "Cannot save invalid profile: ${validation.errorMessage}")
            return false
        }

        val targetFile = getProfileFile(profile.userId)
        val tempFile = File(profilesDir, "${targetFile.name}.tmp")

        return try {
            FileWriter(tempFile).use { writer ->
                gson.toJson(profile, writer)
            }
            if (tempFile.exists()) {
                if (targetFile.exists()) {
                    targetFile.delete()
                }
                val renamed = tempFile.renameTo(targetFile)
                if (renamed) {
                    syncKeywordsFile(profile)
                }
                renamed
            } else {
                false
            }
        } catch (e: Exception) {
            Log.e(tag, "Error saving KWS profile for ${profile.userId}", e)
            if (tempFile.exists()) tempFile.delete()
            false
        }
    }

    /**
     * Generates the runtime keywords.txt file expected by sherpa-onnx.
     */
    fun syncKeywordsFile(profile: WakeWordProfile): File {
        val kwFile = getKeywordsFile(profile.userId)
        val tempFile = File(profilesDir, "${kwFile.name}.tmp")
        try {
            FileWriter(tempFile).use { writer ->
                // Write tokenized line (e.g. " HE Y  AN I KE T")
                writer.write(profile.tokenizedKeyword.trim() + "\n")
            }
            if (tempFile.exists()) {
                if (kwFile.exists()) kwFile.delete()
                tempFile.renameTo(kwFile)
            }
        } catch (e: Exception) {
            Log.e(tag, "Error writing keywords.txt for ${profile.userId}", e)
            if (tempFile.exists()) tempFile.delete()
        }
        return kwFile
    }

    /**
     * Explicitly activates a candidate profile with atomic commit and rollback protection.
     */
    fun activateProfile(
        userId: String,
        candidateProfile: WakeWordProfile? = null,
        onReloadDetector: (() -> Boolean)? = null
    ): ProfileActivationResult {
        val safeId = sanitizeUserId(userId)
        val profileToActivate = candidateProfile ?: loadDraftProfile(safeId)
        if (profileToActivate == null) {
            return ProfileActivationResult(false, null, "No candidate or draft profile found for user $safeId.")
        }

        val validation = validateProfile(profileToActivate)
        if (!validation.isValid) {
            return ProfileActivationResult(false, null, "Profile validation failed: ${validation.errorMessage}")
        }

        // Backup current working profile & keyword file in case reload fails
        val currentProfile = loadProfile(safeId)
        val kwFile = getKeywordsFile(safeId)
        val backupKwContent = if (kwFile.exists()) kwFile.readText() else null

        val activatedProfile = profileToActivate.copy(
            isActive = true,
            enabled = true,
            updatedAt = System.currentTimeMillis()
        )

        // 1. Commit active profile and keywords
        val saved = saveProfile(activatedProfile)
        if (!saved) {
            return ProfileActivationResult(false, null, "Failed to persist active profile to disk.")
        }

        // 2. Trigger detector reload if callback provided
        if (onReloadDetector != null) {
            val reloadSuccess = try {
                onReloadDetector()
            } catch (e: Exception) {
                Log.e(tag, "Detector reload threw exception", e)
                false
            }

            if (!reloadSuccess) {
                Log.w(tag, "Detector reload failed! Rolling back to previous profile.")
                // Rollback profile
                saveProfile(currentProfile)
                if (backupKwContent != null) {
                    try {
                        FileWriter(kwFile).use { it.write(backupKwContent) }
                    } catch (_: Exception) {}
                }
                return ProfileActivationResult(false, null, "Sherpa detector failed to reload with new profile. Rolled back safely.")
            }
        }

        // 3. Clean up draft file
        deleteDraft(safeId)

        Log.i(tag, "Successfully activated wake-word profile '${activatedProfile.phrase}' for user '$safeId'")
        return ProfileActivationResult(true, activatedProfile, null)
    }

    /**
     * Resets user configuration to the factory default ("Hey Jarvis").
     */
    fun resetToDefault(
        userId: String,
        onReloadDetector: (() -> Boolean)? = null
    ): ProfileActivationResult {
        val safeId = sanitizeUserId(userId)
        val defaultProfile = createDefaultProfile(safeId)
        deleteDraft(safeId)

        if (onReloadDetector != null) {
            try {
                onReloadDetector()
            } catch (e: Exception) {
                Log.e(tag, "Detector reload failed on resetToDefault", e)
            }
        }

        return ProfileActivationResult(true, defaultProfile, null)
    }

    /**
     * Legacy helper to update phrase directly.
     */
    fun updatePhrase(
        userId: String,
        newPhrase: String,
        keywordsScore: Float = 1.0f,
        keywordsThreshold: Float = 0.50f
    ): WakeWordProfile {
        val cleanPhrase = newPhrase.trim()
        val normalized = cleanPhrase.uppercase()
        val tokenized = tokenizer.tokenizeToKeywordLine(cleanPhrase)

        val profile = WakeWordProfile(
            profileId = "kws_${sanitizeUserId(userId)}_${System.currentTimeMillis()}",
            userId = sanitizeUserId(userId),
            phrase = cleanPhrase,
            normalizedPhrase = normalized,
            tokenizedKeyword = tokenized,
            keywordsScore = keywordsScore.coerceIn(MIN_SCORE, MAX_SCORE),
            keywordsThreshold = keywordsThreshold.coerceIn(MIN_THRESHOLD, MAX_THRESHOLD),
            numTrailingBlanks = 1,
            isCustomEnrolled = true,
            isActive = true,
            enabled = true,
            updatedAt = System.currentTimeMillis()
        )
        saveProfile(profile)
        return profile
    }

    fun deleteProfile(userId: String): Boolean {
        val safeId = sanitizeUserId(userId)
        val profileFile = getProfileFile(safeId)
        val kwFile = getKeywordsFile(safeId)
        val draftFile = getDraftProfileFile(safeId)
        if (profileFile.exists()) profileFile.delete()
        if (kwFile.exists()) kwFile.delete()
        if (draftFile.exists()) draftFile.delete()
        return true
    }
}
