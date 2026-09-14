package com.taskflow.backend.auth;

import com.taskflow.backend.user.UserEntity;

public record UserResponse(
        String id,
        String email,
        String name,
        String role,
        String avatarColor
) {
    public static UserResponse from(UserEntity user) {
        return new UserResponse(
                user.id().toString(),
                user.email(),
                user.displayName(),
                user.role(),
                user.avatarColor()
        );
    }
}
