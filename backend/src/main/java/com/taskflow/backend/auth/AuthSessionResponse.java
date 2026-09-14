package com.taskflow.backend.auth;

public record AuthSessionResponse(AuthTokenResponse token, UserResponse user) {
}
