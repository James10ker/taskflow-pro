package com.taskflow.backend.project;

import java.util.List;

import com.taskflow.backend.common.error.BadRequestException;
import com.taskflow.backend.common.error.ForbiddenException;
import com.taskflow.backend.common.error.NotFoundException;
import com.taskflow.backend.security.UserPrincipal;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ProjectService {

    private static final String ADMIN_ROLE = "admin";
    private static final String ACTIVE_STATUS = "active";

    private final ProjectMapper projectMapper;

    public ProjectService(ProjectMapper projectMapper) {
        this.projectMapper = projectMapper;
    }

    @Transactional(readOnly = true)
    public List<ProjectResponse> list(UserPrincipal principal) {
        return projectMapper.findAllForMember(principal.id()).stream()
                .map(this::toResponse)
                .toList();
    }

    @Transactional
    public ProjectResponse create(UserPrincipal principal, CreateProjectRequest request) {
        if (!ADMIN_ROLE.equals(principal.role())) {
            throw new ForbiddenException("Only global administrators can create projects.");
        }

        ProjectEntity project = new ProjectEntity(
                request.name(),
                request.description(),
                ACTIVE_STATUS,
                principal.id()
        );
        projectMapper.insert(project);
        projectMapper.insertOwnerMembership(project.getId(), principal.id());

        return toResponse(requireProject(project.getId()));
    }

    @Transactional(readOnly = true)
    public ProjectResponse get(Long projectId, UserPrincipal principal) {
        requireValidId(projectId);
        ProjectEntity project = requireProject(projectId);
        requireMembership(projectId, principal.id());
        return toResponse(project);
    }

    @Transactional
    public ProjectResponse update(Long projectId, UserPrincipal principal, UpdateProjectRequest request) {
        requireValidId(projectId);
        ProjectEntity project = requireProject(projectId);
        requireOwner(project, principal.id(), "Only the project owner can modify this project.");

        projectMapper.update(projectId, request.name(), request.description(), request.status());
        return toResponse(requireProject(projectId));
    }

    @Transactional
    public DeleteProjectResponse delete(Long projectId, UserPrincipal principal) {
        requireValidId(projectId);
        ProjectEntity project = requireProject(projectId);
        requireOwner(project, principal.id(), "Only the project owner can delete this project.");

        // V1 declares ON DELETE CASCADE from project_members, tasks (and their
        // comments), and activity_logs, so deleting the aggregate root is atomic.
        int deleted = projectMapper.deleteById(projectId);
        if (deleted != 1) {
            throw new NotFoundException("Project not found.");
        }
        return new DeleteProjectResponse(true);
    }

    private ProjectResponse toResponse(ProjectEntity project) {
        return ProjectResponse.from(project, projectMapper.findMemberIds(project.getId()));
    }

    private ProjectEntity requireProject(Long projectId) {
        ProjectEntity project = projectMapper.findById(projectId);
        if (project == null) {
            throw new NotFoundException("Project not found.");
        }
        return project;
    }

    private void requireMembership(Long projectId, Long userId) {
        if (projectMapper.countMembership(projectId, userId) == 0) {
            throw new ForbiddenException("You do not have permission to access this project.");
        }
    }

    private void requireOwner(ProjectEntity project, Long userId, String message) {
        if (!project.getOwnerId().equals(userId)) {
            throw new ForbiddenException(message);
        }
    }

    private void requireValidId(Long projectId) {
        if (projectId == null || projectId <= 0) {
            throw new BadRequestException("Project id must be a positive integer.");
        }
    }
}
