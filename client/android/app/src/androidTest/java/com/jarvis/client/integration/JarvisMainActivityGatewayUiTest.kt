package com.jarvis.client.integration

import android.Manifest
import android.content.Intent
import android.os.SystemClock
import androidx.test.core.app.ActivityScenario
import androidx.test.espresso.Espresso.onView
import androidx.test.espresso.action.ViewActions.click
import androidx.test.espresso.action.ViewActions.closeSoftKeyboard
import androidx.test.espresso.action.ViewActions.replaceText
import androidx.test.espresso.assertion.ViewAssertions.matches
import androidx.test.espresso.matcher.ViewMatchers.isDisplayed
import androidx.test.espresso.matcher.ViewMatchers.withId
import androidx.test.espresso.matcher.ViewMatchers.withText
import androidx.test.rule.GrantPermissionRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.jarvis.client.JarvisApp
import com.jarvis.client.device.JarvisConnectionService
import com.jarvis.client.ui.MainActivity
import org.junit.Assert.assertFalse
import org.junit.Assert.fail
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

/**
 * Real UI-level smoke test: launches MainActivity, opens and closes Settings,
 * then sends a message through the visible chat controls to the live sandbox gateway.
 */
@RunWith(AndroidJUnit4::class)
class JarvisMainActivityGatewayUiTest {

    @get:Rule
    val permissions: GrantPermissionRule = GrantPermissionRule.grant(
        Manifest.permission.POST_NOTIFICATIONS,
        Manifest.permission.RECORD_AUDIO
    )

    @Test
    fun appLaunchesSettingsAndSendsChatThroughVisibleUi() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val app = context.applicationContext as JarvisApp
        val settings = app.settingsManager
        val args = InstrumentationRegistry.getArguments()

        settings.backendBaseUrl = requiredArgument(args, "backendUrl")
        settings.userId = requiredArgument(args, "userId")
        settings.deviceId = "android_ui_audit_${UUID.randomUUID().toString().take(8)}"
        settings.deviceName = requiredArgument(args, "deviceName")
        settings.authToken = requiredArgument(args, "authToken")

        try {
            ActivityScenario.launch(MainActivity::class.java).use { scenario ->
                // This exercises the actual Settings button and dialog instead of only testing the repository.
                onView(withId(com.jarvis.client.R.id.btnOpenSettings)).perform(click())
                onView(withId(com.jarvis.client.R.id.etBackendUrl)).check(matches(isDisplayed()))
                onView(withId(android.R.id.button2)).perform(click())
                scenario.onActivity { activity ->
                    assertFalse("Settings should not close the app", activity.isFinishing)
                }

                // Send a real request using the app's message input and Send button.
                onView(withId(com.jarvis.client.R.id.etMessageInput))
                    .perform(replaceText("stop"), closeSoftKeyboard())
                onView(withId(com.jarvis.client.R.id.btnSendMessage)).perform(click())
                waitForVisibleText("Stopped.", 30_000L)
            }
        } finally {
            app.repository.stop()
            context.stopService(Intent(context, JarvisConnectionService::class.java))
            settings.authToken = ""
        }
    }

    private fun requiredArgument(args: android.os.Bundle, key: String): String =
        args.getString(key)?.takeIf { it.isNotBlank() }
            ?: error("Missing instrumentation argument: $key")

    private fun waitForVisibleText(text: String, timeoutMs: Long) {
        val deadline = SystemClock.elapsedRealtime() + timeoutMs
        var lastError: Throwable? = null
        while (SystemClock.elapsedRealtime() < deadline) {
            try {
                onView(withText(text)).check(matches(isDisplayed()))
                return
            } catch (error: Throwable) {
                lastError = error
                SystemClock.sleep(250)
            }
        }
        fail("JARVIS did not show the expected UI response '$text' within ${timeoutMs}ms. Last error: $lastError")
    }
}
