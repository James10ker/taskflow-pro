package com.taskflow.backend.auth;

import java.util.Locale;

import com.taskflow.backend.common.error.NotFoundException;
import com.taskflow.backend.common.error.UnauthorizedException;
import com.taskflow.backend.security.JwtService;
import com.taskflow.backend.user.UserEntity;
import com.taskflow.backend.user.UserMapper;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class AuthService {

    private final UserMapper userMapper;
    private final PasswordEncoder passwordEncoder;
    private final JwtService jwtService;

    public AuthService(UserMapper userMapper, PasswordEncoder passwordEncoder, JwtService jwtService) {
        this.userMapper = userMapper;
        this.passwordEncoder = passwordEncoder;
        this.jwtService = jwtService;
    }

    public AuthSessionResponse login(LoginRequest request) {
        String normalizedEmail = request.email().trim().toLowerCase(Locale.ROOT);
        UserEntity user = userMapper.findByEmail(normalizedEmail);

        if (user == null || !user.active() || !passwordEncoder.matches(request.password(), user.passwordHash())) {
            throw new UnauthorizedException("Invalid email or password.");
        }

        String accessToken = jwtService.generateToken(user);
        return new AuthSessionResponse(new AuthTokenResponse(accessToken), UserResponse.from(user));
    }

    public UserResponse currentUser(Long authenticatedUserId) {
        UserEntity user = userMapper.findById(authenticatedUserId);
        if (user == null || !user.active()) {
            throw new NotFoundException("Authenticated user no longer exists.");
        }
        return UserResponse.from(user);
    }
}
