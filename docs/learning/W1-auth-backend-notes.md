# W1 学习笔记：从登录按钮到 MySQL 与 JWT

这份笔记只解释 W1 的真实认证闭环。Projects、Tasks、Users、Activity 仍在浏览器中的 Mock API；它们不是本周的后端实现。

## 1. 点击登录之后发生了什么

```text
LoginView.vue
  -> authStore.login(email, password)
  -> authService.login(payload)
  -> realHttp POST /api/auth/login
  -> Spring Security 放行登录路径
  -> AuthController.login(request)
  -> AuthService.login(request)
  -> UserMapper.findByEmail(email)
  -> MySQL users 表
  -> BCrypt 校验密码
  -> JwtService.generateToken(user)
  -> JSON { token, user }
  -> Pinia 保存 session，并写入 localStorage
  -> 路由进入 Dashboard
```

`LoginView` 只处理表单和页面跳转，不直接写 HTTP。Store 持有当前会话状态，Service 描述远端 API，HTTP Client 负责 base URL、Bearer Token 和通用错误。这几层看起来多了一点，但每层只有一个清晰理由，调试时也能很快判断错误发生在哪一段。

页面刷新时，Pinia 先从 `taskflow_pro_session_v1` 恢复 Token，再调用真实的 `GET /api/auth/me`。后端验证 JWT、从数据库重新读取用户，然后前端用返回值更新当前用户。这样浏览器里过期或伪造的用户资料不会被当成真相。

## 2. Controller、Service、Mapper 分别做什么

- **Controller** 是 HTTP 边界：接收 JSON、触发参数校验、调用业务方法并返回响应。它不应该包含 SQL 或密码算法。
- **Service** 是业务边界：决定登录的规则，例如邮箱规范化、用户是否存在、账号是否启用、密码是否匹配，以及成功后签发 Token。
- **Mapper** 是数据库边界：把一个明确的 Java 方法变成一条 SQL，并将结果列映射为 Java 对象。它不应该决定“密码错时返回 401”这类业务规则。

本项目当前调用链很短，这是刻意的。W1 不需要 Repository 包装 Mapper，也不需要为了“分层”再增加没有职责的接口和实现类。

## 3. DTO 与数据库 Entity 为什么不要混用

DTO 是接口契约，Entity 是数据库形状，两者的变化原因不同。

`UserEntity` 包含 `passwordHash`，因为登录校验需要从 `users` 表读取它；`UserResponse` 永远不包含密码哈希，因为浏览器不需要也不应该看到它。若直接把 Entity 返回给前端，很容易在增加字段时意外泄露敏感数据。反过来，登录请求只需要邮箱和密码，也不应该伪装成一整行数据库记录。

因此 W1 使用了三类对象：

- `LoginRequest`：浏览器允许提交什么；
- `UserEntity`：数据库实际读到了什么；
- `UserResponse` / `AuthSessionResponse`：浏览器允许收到什么。

## 4. BCrypt 为什么不能“解密”

BCrypt 是单向密码哈希，不是加密。注册或 seed 时，明文密码经过 BCrypt 得到带随机盐的哈希；登录时调用 `passwordEncoder.matches(明文, 哈希)`，算法重新计算并判断是否匹配。系统没有、也不需要“解密数据库密码”的能力。

相同明文多次生成的 BCrypt 字符串通常不同，因为盐不同。这正是预期行为。数据库泄露时，攻击者不能直接反解出密码，但弱密码仍可能被暴力猜测，所以真实生产系统还需要密码策略、限流和告警；这些不属于 W1。

## 5. JWT 如何生成和校验

JWT 由 `header.payload.signature` 三段组成。W1 的 payload 只放必要声明：

- `sub`：用户 ID；
- `role`：角色，供后续 RBAC 使用；
- `iss`：签发者；
- `iat` / `exp`：签发与过期时间。

登录成功后，`JwtService` 用服务端环境变量中的 HMAC 密钥生成签名。JWT 默认只是 Base64URL 编码，不是加密，不能在里面放密码或秘密。

请求 `/me` 时，`JwtAuthenticationFilter` 读取 `Authorization: Bearer <token>`，验证签名、签发者和过期时间，并取出 `sub`。过滤器再按该 ID 查询数据库，确认用户仍存在且启用，然后把认证对象放进 Spring Security 上下文。签名不对、过期、用户不存在或已停用时，都不能建立登录身份。

W1 没有 refresh token 或服务端黑名单。退出登录只是前端删除 Token；已签发 Token 会在到期前保持有效。这是明确的 W1 简化，而不是完整生产方案。

## 6. Spring Security 在链路里做了什么

`SecurityConfig` 定义了规则：

- `/api/health` 和 `POST /api/auth/login` 可以匿名访问；
- 其他接口必须已经认证；
- 服务端不创建 HTTP Session，使用无状态 Bearer Token；
- API 不使用浏览器表单 CSRF 流程；
- CORS 只允许配置中的本地前端来源，并明确允许 credentials，没有使用危险的 `* + credentials`；
- 未认证返回统一 JSON 401，已认证但无权限返回统一 JSON 403。

过滤器负责“这个请求是谁”，Controller 负责“该请求要做什么”。后续 W2 的服务端 RBAC 应继续在 Security/Service 边界校验，而不是相信页面有没有隐藏按钮。

## 7. MyBatis 如何把 Java 调用变成 SQL

`UserMapper` 是一个接口，方法上写了 `@Select`。应用启动时，MyBatis 为接口生成代理对象。调用 `findByEmail(email)` 时，代理执行对应的参数化 SQL，把 `#{email}` 作为绑定参数交给 JDBC，而不是拼接字符串；数据库返回的 snake_case 列通过配置映射到 camelCase 的 `UserEntity` 字段。

参数绑定既更容易阅读，也能避免把用户输入直接拼进 SQL 导致 SQL 注入。Mapper 返回 `Optional<UserEntity>`，让 Service 明确处理“没有该用户”的情况。

## 8. 为什么 `/me` 不接收前端传来的 userId

浏览器完全受用户控制。攻击者可以把 `userId=2` 改成 `userId=1`，因此 `/me?userId=...` 不能证明调用者是谁。

W1 用已签名 JWT 的 `sub` 识别用户。客户端只能提交 Token，服务端验证签名后决定身份，再从 MySQL 读取最新用户。即使前端 localStorage 中的 `user` 被手工修改，也不会改变后端识别出的身份。

## 9. 为什么前端 RBAC 不能替代后端鉴权

前端 RBAC 的价值是用户体验：成员不应看到自己不能用的按钮。但隐藏按钮并不会隐藏 HTTP 接口，攻击者可以用 curl 或浏览器开发者工具直接发请求。真正的权限边界必须在服务端按当前认证用户、角色和项目成员关系检查。

目前 Projects/Tasks 仍由 Mock 驱动，所以旧页面上的 RBAC 仍是过渡期的客户端行为。W2 把这些写操作迁到后端时，必须同时实现服务端角色与 `project_members` 校验。

## 10. 当前测试依赖与局限

`AuthFlowIntegrationTest` 使用 Spring Boot 完整上下文、MockMvc、Flyway 和 H2 的 MySQL 兼容模式，覆盖成功登录、错误密码、无 Token、有效 Token 和参数校验。它速度快，也不要求每次测试都启动 Docker。

局限是 H2 不能完全代表 MySQL 的 SQL 方言、索引行为和字符集。本周通过 Docker 中的真实 MySQL 8.4 启动后端并执行了 Flyway 与真实登录作为补充。W1 没有引入 Testcontainers；等数据库查询和权限规则增多后，再评估是否值得加入。

## 11. 最值得亲手重写的 3 个小方法

1. `AuthService.login`：先不看原代码，自己写出“规范化邮箱 → 查用户 → 检查状态 → BCrypt matches → 生成响应”的顺序。这是最小业务用例。
2. `JwtAuthenticationFilter.doFilterInternal`：亲手处理 Bearer 头、校验 Token、查用户、写入 SecurityContext，并保证任何失败都不会伪造身份。
3. `authStore.refreshMe`：从已有 Token 调 `/me`，成功更新 session，失败清空登录态。它能帮你理解前后端会话恢复的边界。

## 12. 我必须能解释的文件清单（10 个）

1. `src/modules/auth/views/LoginView.vue`：采集登录表单、调用 Store，并在成功后导航。
2. `src/modules/auth/store.ts`：管理前端 session、Token 持久化以及刷新失败时的登出。
3. `src/api/http.ts`：隔离真实 Auth Client 与旧 Mock Client，并统一注入 Bearer Token 和处理 401。
4. `backend/src/main/java/com/taskflow/backend/security/SecurityConfig.java`：定义公开/受保护路径、无状态安全策略与本地 CORS。
5. `backend/src/main/java/com/taskflow/backend/security/JwtAuthenticationFilter.java`：从请求 Token 恢复经过数据库确认的当前用户。
6. `backend/src/main/java/com/taskflow/backend/security/JwtService.java`：生成和验证最小声明 JWT。
7. `backend/src/main/java/com/taskflow/backend/auth/AuthController.java`：暴露登录与 `/me` HTTP 接口。
8. `backend/src/main/java/com/taskflow/backend/auth/AuthService.java`：实现用户查询、状态/密码校验与会话组装。
9. `backend/src/main/java/com/taskflow/backend/user/UserMapper.java`：用参数化 SQL 从 MySQL 查询用户。
10. `backend/src/main/resources/db/migration/V1__create_core_tables.sql`：定义 W1 数据模型、约束、索引和外键。
