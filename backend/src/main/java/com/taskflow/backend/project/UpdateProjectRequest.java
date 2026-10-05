package com.taskflow.backend.project;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record UpdateProjectRequest(
        @NotBlank(message = "Project name is required.")
        @Size(max = 150, message = "Project name must be at most 150 characters.")
        String name,

        @NotNull(message = "Project description is required.")
        String description,

        @NotBlank(message = "Project status is required.")
        @Pattern(
                regexp = "active|paused|completed",
                message = "Project status must be one of: active, paused, completed."
        )
        String status
) {
    public UpdateProjectRequest {
        if (name != null) {
            name = name.trim();
        }
        if (description != null) {
            description = description.trim();
        }
        if (status != null) {
            status = status.trim();
        }
    }
}
