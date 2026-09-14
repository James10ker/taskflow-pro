package com.taskflow.backend.user;

import java.time.LocalDateTime;

public record UserEntity(
        Long id,
        String email,
        String passwordHash,
        String displayName,
        String role,
        String avatarColor,
        boolean active,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
}
