package com.jarvis.client.websocket

import com.jarvis.client.model.ConnectionState
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WebSocketConnectionPolicyTest {

    @Test
    fun activeOrPendingConnectionStatesRejectDuplicateStarts() {
        val states = listOf(
            ConnectionState.CONNECTING,
            ConnectionState.CONNECTED,
            ConnectionState.AUTHENTICATING,
            ConnectionState.AUTHENTICATED,
            ConnectionState.RECONNECTING
        )

        states.forEach { state ->
            assertFalse("Expected $state to reject a duplicate connect", WebSocketConnectionPolicy.canStart(state))
        }
    }

    @Test
    fun disconnectedAndErrorStatesAllowANewConnection() {
        assertTrue(WebSocketConnectionPolicy.canStart(ConnectionState.DISCONNECTED))
        assertTrue(WebSocketConnectionPolicy.canStart(ConnectionState.ERROR))
    }
}
