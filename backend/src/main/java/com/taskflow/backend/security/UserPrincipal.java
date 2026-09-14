package com.taskflow.backend.security;

public record UserPrincipal(Long id, String email, String role) {
}
