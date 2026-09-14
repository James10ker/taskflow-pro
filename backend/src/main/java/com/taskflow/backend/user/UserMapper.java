package com.taskflow.backend.user;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface UserMapper {

    @Select("""
            SELECT id,
                   email,
                   password_hash,
                   display_name,
                   role,
                   avatar_color,
                   is_active AS active,
                   created_at,
                   updated_at
            FROM users
            WHERE email = #{email}
            LIMIT 1
            """)
    UserEntity findByEmail(String email);

    @Select("""
            SELECT id,
                   email,
                   password_hash,
                   display_name,
                   role,
                   avatar_color,
                   is_active AS active,
                   created_at,
                   updated_at
            FROM users
            WHERE id = #{id}
            """)
    UserEntity findById(Long id);
}
