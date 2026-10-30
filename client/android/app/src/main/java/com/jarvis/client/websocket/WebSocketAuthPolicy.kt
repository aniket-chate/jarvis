package com.jarvis.client.websocket

/**
 * Resolves the only credential accepted for gateway authentication.
 *
 * A user identifier is not an authentication secret and must never be used as a fallback.
 */
internal object WebSocketAuthPolicy {
    fun resolveToken(authToken: String): String? =
        authToken.trim().takeIf { it.isNotEmpty() }
}
