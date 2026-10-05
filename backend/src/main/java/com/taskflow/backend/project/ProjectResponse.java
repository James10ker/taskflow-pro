package com.taskflow.backend.project;

import java.time.format.DateTimeFormatter;
import java.util.List;

public record ProjectResponse(
        String id,
        String name,
        String description,
        String status,
        String ownerId,
        List<String> memberIds,
        String createdAt,
        String updatedAt
) {
    private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ISO_LOCAL_DATE_TIME;

    static ProjectResponse from(ProjectEntity project, List<Long> memberIds) {
        return new ProjectResponse(
                project.getId().toString(),
                project.getName(),
                project.getDescription(),
                project.getStatus(),
                project.getOwnerId().toString(),
                memberIds.stream().map(String::valueOf).toList(),
                DATE_TIME_FORMATTER.format(project.getCreatedAt()),
                DATE_TIME_FORMATTER.format(project.getUpdatedAt())
        );
    }
}
