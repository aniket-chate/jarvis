package com.jarvis.client.accessibility

import org.junit.Assert.assertEquals
import org.junit.Test

class UiActionPolicyTest {

    @Test
    fun ordinaryTapIsAllowed() {
        assertEquals(
            UiActionPolicy.Decision.ALLOW,
            UiActionPolicy.evaluateTap("Open settings", humanApproved = false)
        )
    }

    @Test
    fun finalSubmitRequiresHumanApproval() {
        assertEquals(
            UiActionPolicy.Decision.REQUIRE_HUMAN_APPROVAL,
            UiActionPolicy.evaluateTap("Submit", humanApproved = false)
        )
        assertEquals(
            UiActionPolicy.Decision.ALLOW,
            UiActionPolicy.evaluateTap("Submit", humanApproved = true)
        )
    }

    @Test
    fun biometricActionsNeverBecomeRemoteAutomation() {
        assertEquals(
            UiActionPolicy.Decision.DENY_HUMAN_INPUT,
            UiActionPolicy.evaluateTap("Use fingerprint", humanApproved = true)
        )
    }

    @Test
    fun passwordAndOtpFieldsAreHumanOnly() {
        assertEquals(
            UiActionPolicy.Decision.DENY_HUMAN_INPUT,
            UiActionPolicy.evaluateTextInput(
                isPassword = true,
                hint = "Password",
                resourceId = "login_password",
                target = "Password"
            )
        )
        assertEquals(
            UiActionPolicy.Decision.DENY_HUMAN_INPUT,
            UiActionPolicy.evaluateTextInput(
                isPassword = false,
                hint = "One time password",
                resourceId = "otp",
                target = "Verification code"
            )
        )
    }

    @Test
    fun ordinaryTextFieldIsAllowed() {
        assertEquals(
            UiActionPolicy.Decision.ALLOW,
            UiActionPolicy.evaluateTextInput(
                isPassword = false,
                hint = "Search",
                resourceId = "search_box",
                target = "Search"
            )
        )
    }
}
