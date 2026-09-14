# Mock → 真实后端迁移状态

更新时间：W1

| 模块 | 状态 | W1 请求去向 | 说明 |
| --- | --- | --- | --- |
| Auth login | **REAL** | Spring Boot `/api/auth/login` | MySQL 用户、BCrypt、服务端 JWT |
| Auth me | **REAL** | Spring Boot `/api/auth/me` | 从已验签 JWT 的 `sub` 识别用户 |
| Auth register | **NOT IMPLEMENTED** | 无可用 UI 入口 | `/auth/register` 暂时重定向登录，避免产生假账号 |
| Projects | **MOCK** | browser Axios mock adapter | 数据仍在 `taskflow_pro_db_v1` |
| Tasks / Comments | **MOCK** | browser Axios mock adapter | 数据仍在 `taskflow_pro_db_v1` |
| Users directory | **MOCK** | browser Axios mock adapter | 不是数据库用户目录；W2 迁移 |
| Activity | **MOCK** | browser Axios mock adapter | 随 Mock 项目/任务写入 localStorage |

## W1 的两个 client

```text
auth/service.ts
  -> requestReal()
  -> realHttp
  -> browser network
  -> Spring Boot

projects/tasks/users/activity service
  -> request()
  -> mockHttp
  -> createMockAdapter()
  -> localStorage
```

`src/api/http.ts` 仍集中处理 token header、401、重试和错误归一化。差别只在最后选择真实 transport 还是 mock adapter。Auth 调用必须显式写 `requestReal`；旧模块继续用默认的 `request`，使迁移状态从代码调用点即可辨认。

Mock adapter 中原有的 login/register/me 路由已删除，Mock seed 也不再保存 demo 明文密码。`createDb()` 会在读取旧的 `taskflow_pro_db_v1` 后重写一份只含公开用户字段的数据，从而清理已有浏览器数据中的遗留密码。

本地开发可把 `.env.example` 复制为 `.env.local`，让真实 client 请求 `http://localhost:8080/api`。未配置时使用同源 `/api`，适合后续由反向代理统一入口。

## 真实 JWT 如何暂时驱动 Mock 页面

真实后端返回的 user ID 是数据库 ID，而 Mock 项目内保存的是浏览器 seed 的随机 ID，二者不能直接比较。W1 不让 Mock adapter 伪造验证 JWT，也不把 JWT payload 当可信授权信息。它只在收到 Bearer header 时，从已经由真实 `/me` 恢复的前端会话取 email，再映射到同 email 的 Mock seed 用户 ID；角色使用真实会话的角色。

这是明确的临时兼容层，只负责让 Projects/Kanban 继续演示。它不是安全边界；用户仍可修改浏览器代码与 localStorage。W2 迁移 Project/ProjectMember 后应删除这段映射。

## 会话恢复与 401

```text
启动
  -> 从 taskflow_pro_session_v1 读取 token
  -> 安装真实/Mock client 与 Router
  -> GET 真实 /api/auth/me
     -> 成功：用数据库最新 user 覆盖本地 user
     -> 401：清 session，并 replace 到 login
  -> 挂载页面
```

W1 logout 只清前端 token。JWT 到期前仍可独立使用，这是无状态 access token 的预期限制；本周不引入 Redis 黑名单或 refresh token，以免为一个 demo 登出增加不必要状态。

## 后续迁移纪律

每迁移一个模块：先在后端完成数据模型、鉴权和测试，再把对应 Service 改为 `requestReal`，最后删除该模块在 adapter/Mock DB 中的实现。不要一次删除整个 Mock 层。
