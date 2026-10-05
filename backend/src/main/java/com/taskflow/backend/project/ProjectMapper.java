package com.taskflow.backend.project;

import java.util.List;

import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface ProjectMapper {

    @Select("""
            SELECT p.id,
                   p.name,
                   p.description,
                   p.status,
                   p.owner_id AS ownerId,
                   p.created_at AS createdAt,
                   p.updated_at AS updatedAt
            FROM projects p
            INNER JOIN project_members pm ON pm.project_id = p.id
            WHERE pm.user_id = #{userId}
            ORDER BY p.updated_at DESC, p.id DESC
            """)
    List<ProjectEntity> findAllForMember(Long userId);

    @Select("""
            SELECT id,
                   name,
                   description,
                   status,
                   owner_id AS ownerId,
                   created_at AS createdAt,
                   updated_at AS updatedAt
            FROM projects
            WHERE id = #{id}
            """)
    ProjectEntity findById(Long id);

    @Select("""
            SELECT user_id
            FROM project_members
            WHERE project_id = #{projectId}
            ORDER BY CASE WHEN member_role = 'owner' THEN 0 ELSE 1 END,
                     joined_at,
                     user_id
            """)
    List<Long> findMemberIds(Long projectId);

    @Select("""
            SELECT COUNT(*)
            FROM project_members
            WHERE project_id = #{projectId}
              AND user_id = #{userId}
            """)
    int countMembership(@Param("projectId") Long projectId, @Param("userId") Long userId);

    @Insert("""
            INSERT INTO projects (name, description, status, owner_id)
            VALUES (#{name}, #{description}, #{status}, #{ownerId})
            """)
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(ProjectEntity project);

    @Insert("""
            INSERT INTO project_members (project_id, user_id, member_role)
            VALUES (#{projectId}, #{ownerId}, 'owner')
            """)
    int insertOwnerMembership(@Param("projectId") Long projectId, @Param("ownerId") Long ownerId);

    @Update("""
            UPDATE projects
            SET name = #{name},
                description = #{description},
                status = #{status},
                updated_at = CURRENT_TIMESTAMP
            WHERE id = #{id}
            """)
    int update(
            @Param("id") Long id,
            @Param("name") String name,
            @Param("description") String description,
            @Param("status") String status
    );

    @Delete("DELETE FROM projects WHERE id = #{id}")
    int deleteById(Long id);
}
