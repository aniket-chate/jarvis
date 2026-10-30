package com.jarvis.client.websocket

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class WebSocketAuthPolicyTest {

    @Test
    fun missingTokenIsRejected() {
        assertNull(WebSocketAuthPolicy.resolveToken(""))
    }

    @Test
    fun whitespaceOnlyTokenIsRejected() {
        assertNull(WebSocketAuthPolicy.resolveToken("   \t\n"))
    }

    @Test
    fun configuredTokenIsTrimmedWithoutChangingItsValue() {
        assertEquals("configured-secret", WebSocketAuthPolicy.resolveToken("  configured-secret  "))
    }
}
