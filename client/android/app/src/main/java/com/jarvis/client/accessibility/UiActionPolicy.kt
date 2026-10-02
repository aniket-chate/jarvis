package com.jarvis.client.accessibility

/**
 * Defense-in-depth policy for semantic UI automation.
 *
 * The backend remains responsible for planning and requesting human confirmation, but the
 * Android agent must independently prevent credential/biometric entry and require an explicit
 * human approval marker before high-impact final actions.
 */
object UiActionPolicy {

    enum class Decision {
        ALLOW,
        REQUIRE_HUMAN_APPROVAL,
        DENY_HUMAN_INPUT
    }

    fun evaluateTap(target: String, humanApproved: Boolean): Decision {
        val normalized = normalize(target)

        if (containsAny(normalized, BIOMETRIC_TERMS)) {
            return Decision.DENY_HUMAN_INPUT
        }

        if (containsAny(normalized, HIGH_IMPACT_TERMS)) {
            return if (humanApproved) Decision.ALLOW else Decision.REQUIRE_HUMAN_APPROVAL
        }

        return Decision.ALLOW
    }

    fun evaluateTextInput(
        isPassword: Boolean,
        hint: String?,
        resourceId: String?,
        target: String?
    ): Decision {
        val searchable = normalize(
            listOfNotNull(hint, resourceId, target)
                .joinToString(" ")
        )

        if (isPassword || containsAny(searchable, SECRET_INPUT_TERMS)) {
            return Decision.DENY_HUMAN_INPUT
        }

        return Decision.ALLOW
    }

    private fun normalize(value: String): String =
        value.trim().lowercase().replace(Regex("[^a-z0-9]+"), " ").trim()

    private fun containsAny(value: String, terms: Set<String>): Boolean =
        terms.any { term -> value.split(' ').contains(term) || value.contains(term) }

    private val SECRET_INPUT_TERMS = setOf(
        "password",
        "passwd",
        "passcode",
        "pin",
        "otp",
        "one time password",
        "verification code",
        "security code",
        "captcha",
        "cvv",
        "cvc"
    )

    private val BIOMETRIC_TERMS = setOf(
        "fingerprint",
        "face id",
        "face unlock",
        "biometric",
        "touch id"
    )

    private val HIGH_IMPACT_TERMS = setOf(
        "submit",
        "pay",
        "purchase",
        "buy",
        "place order",
        "transfer",
        "send",
        "delete",
        "remove",
        "confirm",
        "approve",
        "authorize",
        "sign in",
        "login",
        "log in"
    )
}
