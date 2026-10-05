package com.taskflow.backend.project;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record CreateProjectRequest(
        @NotBlank(message = "Project name is required.")
        @Size(max = 150, message = "Project name must be at most 150 characters.")
        String name,

        @NotNull(message = "Project description is required.")
        String description
) {
    public CreateProjectRequest {
        if (name != null) {
            name = name.trim();
        }
        if (description != null) {
            description = description.trim();
        }
    }
}
