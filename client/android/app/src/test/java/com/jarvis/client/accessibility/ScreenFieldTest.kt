package com.jarvis.client.accessibility

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ScreenFieldTest {

    @Test
    fun passwordFieldNeverExposesItsText() {
        val result = ScreenField(
            description = "Password",
            text = "private-value",
            isPassword = true,
            isEditable = true
        ).toMap()

        assertFalse(result.containsKey("text"))
        assertEquals(true, result["password"])
        assertEquals(true, result["editable"])
    }

    @Test
    fun ordinaryFieldIncludesNonBlankText() {
        val result = ScreenField(
            description = "Search",
            text = "weather",
            isPassword = false,
            isEditable = true
        ).toMap()

        assertEquals("weather", result["text"])
        assertEquals(false, result["password"])
        assertEquals(true, result["editable"])
    }

    @Test
    fun blankOrdinaryFieldOmitsText() {
        val result = ScreenField(
            description = "Search",
            text = "   ",
            isPassword = false,
            isEditable = true
        ).toMap()

        assertFalse(result.containsKey("text"))
    }

    @Test
    fun passwordFieldRemainsRedactedWhenTextIsNull() {
        val result = ScreenField(
            description = "PIN",
            text = null,
            isPassword = true,
            isEditable = true
        ).toMap()

        assertTrue(result.containsKey("password"))
        assertFalse(result.containsKey("text"))
    }
}
