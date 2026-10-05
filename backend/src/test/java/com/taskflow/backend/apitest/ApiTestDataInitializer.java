package com.taskflow.backend.apitest;

import java.sql.Connection;
import java.sql.SQLException;
import java.util.List;
import java.util.Locale;

import javax.sql.DataSource;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Deterministic prerequisites for black-box API tests.
 *
 * <p>This configuration lives under {@code src/test}, is guarded by the
 * {@code api-test} profile, and refuses to touch a database that is not clearly
 * isolated. It is therefore unavailable from the production application jar.</p>
 */
@Configuration(proxyBeanMethods = false)
@Profile("api-test")
public class ApiTestDataInitializer {

    public static final String OWNER_ADMIN_EMAIL = "api-owner-admin@taskflow.test";
    public static final String MEMBER_EMAIL = "api-member@taskflow.test";
    public static final String OUTSIDER_EMAIL = "api-outsider@taskflow.test";
    public static final String OUTSIDER_ADMIN_EMAIL = "api-outsider-admin@taskflow.test";
    public static final String SHARED_PROJECT_NAME = "API Test Shared Member Project";

    @Bean
    ApplicationRunner initializeApiTestData(
            DataSource dataSource,
            JdbcTemplate jdbcTemplate,
            PasswordEncoder passwordEncoder,
            TransactionTemplate transactionTemplate,
            @Value("${app.api-test.password:}") String testPassword
    ) {
        return arguments -> {
            requireIsolatedDatabase(dataSource);
            if (testPassword == null || testPassword.isBlank()) {
                throw new IllegalStateException(
                        "APP_API_TEST_PASSWORD is required when the api-test profile is active."
                );
            }

            String passwordHash = passwordEncoder.encode(testPassword);
            transactionTemplate.executeWithoutResult(status -> {
                Long ownerId = upsertUser(
                        jdbcTemplate,
                        OWNER_ADMIN_EMAIL,
                        "API Owner Admin",
                        "admin",
                        "#6d28d9",
                        passwordHash
                );
                Long memberId = upsertUser(
                        jdbcTemplate,
                        MEMBER_EMAIL,
                        "API Project Member",
                        "member",
                        "#0284c7",
                        passwordHash
                );
                upsertUser(
                        jdbcTemplate,
                        OUTSIDER_EMAIL,
                        "API Non-member",
                        "member",
                        "#059669",
                        passwordHash
                );
                upsertUser(
                        jdbcTemplate,
                        OUTSIDER_ADMIN_EMAIL,
                        "API Non-member Admin",
                        "admin",
                        "#dc2626",
                        passwordHash
                );

                Long projectId = upsertSharedProject(jdbcTemplate, ownerId);
                upsertMembership(jdbcTemplate, projectId, ownerId, "owner");
                upsertMembership(jdbcTemplate, projectId, memberId, "member");
            });
        };
    }

    private static Long upsertUser(
            JdbcTemplate jdbcTemplate,
            String email,
            String displayName,
            String role,
            String avatarColor,
            String passwordHash
    ) {
        int updated = jdbcTemplate.update("""
                UPDATE users
                SET password_hash = ?,
                    display_name = ?,
                    role = ?,
                    avatar_color = ?,
                    is_active = TRUE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE email = ?
                """, passwordHash, displayName, role, avatarColor, email);

        if (updated == 0) {
            jdbcTemplate.update("""
                    INSERT INTO users (
                        email,
                        password_hash,
                        display_name,
                        role,
                        avatar_color,
                        is_active
                    )
                    VALUES (?, ?, ?, ?, ?, TRUE)
                    """, email, passwordHash, displayName, role, avatarColor);
        }

        return jdbcTemplate.queryForObject(
                "SELECT id FROM users WHERE email = ?",
                Long.class,
                email
        );
    }

    private static Long upsertSharedProject(JdbcTemplate jdbcTemplate, Long ownerId) {
        List<Long> existingIds = jdbcTemplate.queryForList("""
                SELECT id
                FROM projects
                WHERE name = ? AND owner_id = ?
                ORDER BY id
                """, Long.class, SHARED_PROJECT_NAME, ownerId);

        if (existingIds.isEmpty()) {
            jdbcTemplate.update("""
                    INSERT INTO projects (name, description, status, owner_id)
                    VALUES (?, ?, 'active', ?)
                    """,
                    SHARED_PROJECT_NAME,
                    "Stable owner/member prerequisite for isolated black-box API tests.",
                    ownerId
            );
            existingIds = jdbcTemplate.queryForList("""
                    SELECT id
                    FROM projects
                    WHERE name = ? AND owner_id = ?
                    ORDER BY id
                    """, Long.class, SHARED_PROJECT_NAME, ownerId);
        } else {
            jdbcTemplate.update("""
                    UPDATE projects
                    SET description = ?, status = 'active', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    "Stable owner/member prerequisite for isolated black-box API tests.",
                    existingIds.getFirst()
            );
        }

        return existingIds.getFirst();
    }

    private static void upsertMembership(
            JdbcTemplate jdbcTemplate,
            Long projectId,
            Long userId,
            String memberRole
    ) {
        int updated = jdbcTemplate.update("""
                UPDATE project_members
                SET member_role = ?
                WHERE project_id = ? AND user_id = ?
                """, memberRole, projectId, userId);
        if (updated == 0) {
            jdbcTemplate.update("""
                    INSERT INTO project_members (project_id, user_id, member_role)
                    VALUES (?, ?, ?)
                    """, projectId, userId, memberRole);
        }
    }

    private static void requireIsolatedDatabase(DataSource dataSource) throws SQLException {
        try (Connection connection = dataSource.getConnection()) {
            String url = connection.getMetaData().getURL().toLowerCase(Locale.ROOT);
            boolean inMemoryH2 = url.startsWith("jdbc:h2:mem:");
            String databaseProduct = connection.getMetaData()
                    .getDatabaseProductName()
                    .toLowerCase(Locale.ROOT);
            String catalog = connection.getCatalog();
            boolean isolatedMySql = databaseProduct.contains("mysql")
                    && catalog != null
                    && "taskflow_api_test".equalsIgnoreCase(catalog);
            if (!inMemoryH2 && !isolatedMySql) {
                throw new IllegalStateException(
                        "The api-test profile only initializes an in-memory H2 database "
                                + "or the MySQL catalog named 'taskflow_api_test'."
                );
            }
        }
    }
}
