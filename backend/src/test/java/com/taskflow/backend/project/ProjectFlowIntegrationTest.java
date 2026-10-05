package com.taskflow.backend.project;

import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasItem;
import static org.hamcrest.Matchers.not;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.Map;
import java.util.UUID;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

@SpringBootTest
@AutoConfigureMockMvc
class ProjectFlowIntegrationTest {

    private static final String ADMIN_EMAIL = "admin@taskflow.pro";
    private static final String ADMIN_PASSWORD = "Admin123!";
    private static final String MEMBER_EMAIL = "member@taskflow.pro";
    private static final String MEMBER_PASSWORD = "Member123!";
    private static final String OUTSIDER_ADMIN_EMAIL = "junit-outsider-admin@taskflow.test";
    private static final String OUTSIDER_ADMIN_PASSWORD = "JUnitOutsider123!";
    private static final String PROJECT_NAME_PREFIX = "junit-project-";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @AfterEach
    void removeTestRows() {
        jdbcTemplate.update("DELETE FROM projects WHERE name LIKE ?", PROJECT_NAME_PREFIX + "%");
        jdbcTemplate.update("DELETE FROM users WHERE email = ?", OUTSIDER_ADMIN_EMAIL);
    }

    @Test
    void adminCreatePersistsProjectAndOwnerMembershipTogether() throws Exception {
        String token = login(ADMIN_EMAIL, ADMIN_PASSWORD);
        JsonNode project = createProject(token, uniqueName(), "  integration description  ");

        long projectId = project.path("id").asLong();
        long ownerId = project.path("ownerId").asLong();

        org.junit.jupiter.api.Assertions.assertEquals("integration description", project.path("description").asText());
        org.junit.jupiter.api.Assertions.assertEquals("active", project.path("status").asText());
        org.junit.jupiter.api.Assertions.assertEquals(
                1,
                jdbcTemplate.queryForObject(
                        "SELECT COUNT(*) FROM projects WHERE id = ? AND owner_id = ?",
                        Integer.class,
                        projectId,
                        ownerId
                )
        );
        org.junit.jupiter.api.Assertions.assertEquals(
                "owner",
                jdbcTemplate.queryForObject("""
                        SELECT member_role
                        FROM project_members
                        WHERE project_id = ? AND user_id = ?
                        """, String.class, projectId, ownerId)
        );
    }

    @Test
    void nonAdminCannotCreateProject() throws Exception {
        String memberToken = login(MEMBER_EMAIL, MEMBER_PASSWORD);

        mockMvc.perform(post("/api/projects")
                        .header(HttpHeaders.AUTHORIZATION, bearer(memberToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(Map.of("name", uniqueName(), "description", "denied"))))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("FORBIDDEN"));
    }

    @Test
    void memberCanReadWhileNonMemberAdminHasNoGlobalOverride() throws Exception {
        String ownerToken = login(ADMIN_EMAIL, ADMIN_PASSWORD);
        String memberToken = login(MEMBER_EMAIL, MEMBER_PASSWORD);
        JsonNode project = createProject(ownerToken, uniqueName(), "membership rules");
        long projectId = project.path("id").asLong();
        long memberId = userId(MEMBER_EMAIL);
        jdbcTemplate.update("""
                INSERT INTO project_members (project_id, user_id, member_role)
                VALUES (?, ?, 'member')
                """, projectId, memberId);

        mockMvc.perform(get("/api/projects/{id}", projectId)
                        .header(HttpHeaders.AUTHORIZATION, bearer(memberToken)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(String.valueOf(projectId)))
                .andExpect(jsonPath("$.memberIds", hasItem(String.valueOf(memberId))));

        mockMvc.perform(get("/api/projects")
                        .header(HttpHeaders.AUTHORIZATION, bearer(memberToken)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[*].id", hasItem(String.valueOf(projectId))));

        insertOutsiderAdmin();
        String outsiderAdminToken = login(OUTSIDER_ADMIN_EMAIL, OUTSIDER_ADMIN_PASSWORD);

        mockMvc.perform(get("/api/projects/{id}", projectId)
                        .header(HttpHeaders.AUTHORIZATION, bearer(outsiderAdminToken)))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("FORBIDDEN"));

        mockMvc.perform(get("/api/projects")
                        .header(HttpHeaders.AUTHORIZATION, bearer(outsiderAdminToken)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[*].id", not(hasItem(String.valueOf(projectId)))));
    }

    @Test
    void memberCannotUpdateOrDeleteAndProjectRemainsUnchanged() throws Exception {
        String ownerToken = login(ADMIN_EMAIL, ADMIN_PASSWORD);
        String memberToken = login(MEMBER_EMAIL, MEMBER_PASSWORD);
        String originalName = uniqueName();
        JsonNode project = createProject(ownerToken, originalName, "original");
        long projectId = project.path("id").asLong();
        jdbcTemplate.update("""
                INSERT INTO project_members (project_id, user_id, member_role)
                VALUES (?, ?, 'member')
                """, projectId, userId(MEMBER_EMAIL));

        mockMvc.perform(put("/api/projects/{id}", projectId)
                        .header(HttpHeaders.AUTHORIZATION, bearer(memberToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(Map.of(
                                "name", uniqueName(),
                                "description", "unauthorized change",
                                "status", "paused"
                        ))))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("FORBIDDEN"));

        mockMvc.perform(delete("/api/projects/{id}", projectId)
                        .header(HttpHeaders.AUTHORIZATION, bearer(memberToken)))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.code").value("FORBIDDEN"));

        mockMvc.perform(get("/api/projects/{id}", projectId)
                        .header(HttpHeaders.AUTHORIZATION, bearer(ownerToken)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.name").value(originalName))
                .andExpect(jsonPath("$.description").value("original"))
                .andExpect(jsonPath("$.status").value("active"));
    }

    @Test
    void ownerCanUpdateOnlyAllowedProjectFields() throws Exception {
        String ownerToken = login(ADMIN_EMAIL, ADMIN_PASSWORD);
        JsonNode project = createProject(ownerToken, uniqueName(), "before");
        long projectId = project.path("id").asLong();
        String updatedName = uniqueName();

        mockMvc.perform(put("/api/projects/{id}", projectId)
                        .header(HttpHeaders.AUTHORIZATION, bearer(ownerToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(Map.of(
                                "name", "  " + updatedName + "  ",
                                "description", "  after  ",
                                "status", "paused"
                        ))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.name").value(updatedName))
                .andExpect(jsonPath("$.description").value("after"))
                .andExpect(jsonPath("$.status").value("paused"));

        mockMvc.perform(get("/api/projects/{id}", projectId)
                        .header(HttpHeaders.AUTHORIZATION, bearer(ownerToken)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.name").value(updatedName))
                .andExpect(jsonPath("$.status").value("paused"));

        mockMvc.perform(put("/api/projects/{id}", projectId)
                        .header(HttpHeaders.AUTHORIZATION, bearer(ownerToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(Map.of(
                                "name", updatedName,
                                "description", "after",
                                "status", "paused",
                                "ownerId", "999999",
                                "memberIds", new String[] {"999999"}
                        ))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_REQUEST"));
    }

    @Test
    void ownerDeleteCascadesAllExistingProjectAssociations() throws Exception {
        String ownerToken = login(ADMIN_EMAIL, ADMIN_PASSWORD);
        JsonNode project = createProject(ownerToken, uniqueName(), "cascade delete");
        long projectId = project.path("id").asLong();
        long adminId = userId(ADMIN_EMAIL);

        jdbcTemplate.update("""
                INSERT INTO tasks (
                    project_id, title, description, status, priority, creator_id
                ) VALUES (?, 'dependent task', '', 'todo', 'medium', ?)
                """, projectId, adminId);
        long taskId = jdbcTemplate.queryForObject(
                "SELECT id FROM tasks WHERE project_id = ?",
                Long.class,
                projectId
        );
        jdbcTemplate.update("""
                INSERT INTO task_comments (task_id, author_id, body)
                VALUES (?, ?, 'dependent comment')
                """, taskId, adminId);
        long commentId = jdbcTemplate.queryForObject(
                "SELECT id FROM task_comments WHERE task_id = ?",
                Long.class,
                taskId
        );
        jdbcTemplate.update("""
                INSERT INTO activity_logs (
                    project_id, actor_id, action, entity_type, entity_id, description
                ) VALUES (?, ?, 'test', 'task', ?, 'dependent activity')
                """, projectId, adminId, taskId);

        mockMvc.perform(delete("/api/projects/{id}", projectId)
                        .header(HttpHeaders.AUTHORIZATION, bearer(ownerToken)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));

        assertCountIsZero("SELECT COUNT(*) FROM projects WHERE id = ?", projectId);
        assertCountIsZero("SELECT COUNT(*) FROM project_members WHERE project_id = ?", projectId);
        assertCountIsZero("SELECT COUNT(*) FROM tasks WHERE id = ?", taskId);
        assertCountIsZero("SELECT COUNT(*) FROM task_comments WHERE id = ?", commentId);
        assertCountIsZero("SELECT COUNT(*) FROM activity_logs WHERE project_id = ?", projectId);

        mockMvc.perform(get("/api/projects/{id}", projectId)
                        .header(HttpHeaders.AUTHORIZATION, bearer(ownerToken)))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("NOT_FOUND"));
    }

    @Test
    void validationMalformedJsonAndInvalidPathHaveStableNon500Errors() throws Exception {
        String ownerToken = login(ADMIN_EMAIL, ADMIN_PASSWORD);

        mockMvc.perform(post("/api/projects")
                        .header(HttpHeaders.AUTHORIZATION, bearer(ownerToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(Map.of("name", "   ", "description", "invalid"))))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.code").value("VALIDATION_ERROR"))
                .andExpect(jsonPath("$.details.name").exists());

        mockMvc.perform(post("/api/projects")
                        .header(HttpHeaders.AUTHORIZATION, bearer(ownerToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(Map.of("name", "x".repeat(151), "description", "invalid"))))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.details.name").exists());

        mockMvc.perform(post("/api/projects")
                        .header(HttpHeaders.AUTHORIZATION, bearer(ownerToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_REQUEST"));

        mockMvc.perform(get("/api/projects/not-a-number")
                        .header(HttpHeaders.AUTHORIZATION, bearer(ownerToken)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_REQUEST"));

        mockMvc.perform(get("/api/projects/{id}", -1)
                        .header(HttpHeaders.AUTHORIZATION, bearer(ownerToken)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("INVALID_REQUEST"));
    }

    @Test
    void absentProjectIs404AndUnauthenticatedProjectRequestsAre401() throws Exception {
        String ownerToken = login(ADMIN_EMAIL, ADMIN_PASSWORD);

        mockMvc.perform(get("/api/projects/{id}", 987654321L)
                        .header(HttpHeaders.AUTHORIZATION, bearer(ownerToken)))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("NOT_FOUND"));

        mockMvc.perform(get("/api/projects"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("UNAUTHORIZED"));
    }

    @Test
    void unsupportedMethodMediaTypeAndUnknownApiPathHaveExplicitErrors() throws Exception {
        String ownerToken = login(ADMIN_EMAIL, ADMIN_PASSWORD);

        mockMvc.perform(patch("/api/projects/1")
                        .header(HttpHeaders.AUTHORIZATION, bearer(ownerToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isMethodNotAllowed())
                .andExpect(jsonPath("$.code").value("METHOD_NOT_ALLOWED"));

        mockMvc.perform(post("/api/projects")
                        .header(HttpHeaders.AUTHORIZATION, bearer(ownerToken))
                        .contentType(MediaType.TEXT_PLAIN)
                        .content("{}"))
                .andExpect(status().isUnsupportedMediaType())
                .andExpect(jsonPath("$.code").value("UNSUPPORTED_MEDIA_TYPE"));

        mockMvc.perform(get("/api/not-a-real-resource")
                        .header(HttpHeaders.AUTHORIZATION, bearer(ownerToken)))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("NOT_FOUND"));
    }

    private JsonNode createProject(String token, String name, String description) throws Exception {
        MvcResult result = mockMvc.perform(post("/api/projects")
                        .header(HttpHeaders.AUTHORIZATION, bearer(token))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(Map.of("name", "  " + name + "  ", "description", description))))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").isString())
                .andExpect(jsonPath("$.ownerId").isString())
                .andExpect(jsonPath("$.memberIds", contains(org.hamcrest.Matchers.any(String.class))))
                .andReturn();
        return objectMapper.readTree(result.getResponse().getContentAsString());
    }

    private String login(String email, String password) throws Exception {
        MvcResult result = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(json(Map.of("email", email, "password", password))))
                .andExpect(status().isOk())
                .andReturn();
        return objectMapper.readTree(result.getResponse().getContentAsString())
                .at("/token/accessToken")
                .asText();
    }

    private void insertOutsiderAdmin() {
        jdbcTemplate.update("""
                INSERT INTO users (
                    email, password_hash, display_name, role, avatar_color, is_active
                ) VALUES (?, ?, 'JUnit Outsider Admin', 'admin', '#dc2626', TRUE)
                """, OUTSIDER_ADMIN_EMAIL, passwordEncoder.encode(OUTSIDER_ADMIN_PASSWORD));
    }

    private long userId(String email) {
        return jdbcTemplate.queryForObject(
                "SELECT id FROM users WHERE email = ?",
                Long.class,
                email
        );
    }

    private void assertCountIsZero(String sql, long id) {
        org.junit.jupiter.api.Assertions.assertEquals(
                0,
                jdbcTemplate.queryForObject(sql, Integer.class, id)
        );
    }

    private String uniqueName() {
        return PROJECT_NAME_PREFIX + UUID.randomUUID();
    }

    private String json(Object body) throws Exception {
        return objectMapper.writeValueAsString(body);
    }

    private String bearer(String token) {
        return "Bearer " + token;
    }
}
