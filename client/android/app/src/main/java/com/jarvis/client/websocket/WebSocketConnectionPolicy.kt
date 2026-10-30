package com.jarvis.client.websocket

import com.jarvis.client.model.ConnectionState

/**
 * Prevents duplicate socket creation while a connection or reconnect attempt is active.
 */
internal object WebSocketConnectionPolicy {
    fun canStart(state: ConnectionState): Boolean = when (state) {
        ConnectionState.CONNECTING,
        ConnectionState.CONNECTED,
        ConnectionState.AUTHENTICATING,
        ConnectionState.AUTHENTICATED,
        ConnectionState.RECONNECTING -> false
        ConnectionState.DISCONNECTED,
        ConnectionState.ERROR -> true
    }
}
