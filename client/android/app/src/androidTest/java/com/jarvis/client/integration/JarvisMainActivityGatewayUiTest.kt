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
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.jarvis.client.JarvisApp
import com.jarvis.client.device.JarvisConnectionService
import com.jarvis.client.ui.MainActivity
import org.junit.Assert.assertFalse
import org.junit.Assert.fail
import org.junit.Test
import org.junit.runner.RunWith
import java.util.UUID

/**
 * Real UI-level smoke test: launches MainActivity, opens and closes Settings,
 * then sends a message through the visible chat controls to the live sandbox gateway.
 */
@RunWith(AndroidJUnit4::class)
class JarvisMainActivityGatewayUiTest {

    @Test
    fun appLaunchesSettingsAndSendsChatThroughVisibleUi() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        // Grant runtime permissions through the emulator's instrumentation shell.
        instrumentation.uiAutomation.grantRuntimePermission(context.packageName, Manifest.permission.POST_NOTIFICATIONS)
        instrumentation.uiAutomation.grantRuntimePermission(context.packageName, Manifest.permission.RECORD_AUDIO)
        // CI emulators can boot with the display/keyguard unfocused; wake and unlock before Espresso.
        instrumentation.uiAutomation.executeShellCommand("input keyevent KEYCODE_WAKEUP").close()
        instrumentation.uiAutomation.executeShellCommand("wm dismiss-keyguard").close()
        instrumentation.uiAutomation.executeShellCommand("input keyevent KEYCODE_HOME").close()
        SystemClock.sleep(500)

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
                // Ensure the launched app owns a focused window before Espresso injects touch events.
                scenario.onActivity { activity ->
                    activity.window.decorView.requestFocus()
                    activity.window.decorView.isFocusableInTouchMode = true
                }
                SystemClock.sleep(750)
                // Invoke the real Settings view listener on the UI thread. This avoids
                // emulator-coordinate flakiness while still exercising the visible app control.
                scenario.onActivity { activity ->
                    val settingsButton = activity.findViewById<android.view.View>(com.jarvis.client.R.id.btnOpenSettings)
                    check(settingsButton.isShown && settingsButton.isEnabled) { "Settings control is not visible/enabled" }
                    settingsButton.performClick()
                }
                onView(withId(com.jarvis.client.R.id.etBackendUrl)).check(matches(isDisplayed()))
                instrumentation.uiAutomation.executeShellCommand("input keyevent KEYCODE_BACK").close()
                SystemClock.sleep(300)
                scenario.onActivity { activity ->
                    assertFalse("Settings should not close the app", activity.isFinishing)
                    val messageInput = activity.findViewById<android.widget.EditText>(com.jarvis.client.R.id.etMessageInput)
                    messageInput.setText("stop")
                    val sendButton = activity.findViewById<android.view.View>(com.jarvis.client.R.id.btnSendMessage)
                    check(sendButton.isShown && sendButton.isEnabled) { "Send control is not visible/enabled" }
                    sendButton.performClick()
                }
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
