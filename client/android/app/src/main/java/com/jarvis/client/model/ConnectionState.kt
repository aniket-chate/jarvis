package com.jarvis.client.model

/**
 * Enumeration of Android client connection states with Jarvis backend.
 */
enum class ConnectionState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    AUTHENTICATING,
    AUTHENTICATED,
    RECONNECTING,
    ERROR;

    val isOnline: Boolean
        get() = this == CONNECTED || this == AUTHENTICATED
}
