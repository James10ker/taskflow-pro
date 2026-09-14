# W1 上游前端审计

## 1. 审计范围与基线

- 上游：`https://github.com/Siggmond/taskflow-pro.git`
- 审计提交：`daf01f99564e2e5025584014cac03d03351e8cdd`
- 本地工作分支：`feat/w1-real-auth`
- Git remote：保留上游地址并命名为 `upstream`
- 许可证：MIT，原始 `LICENSE` 保留不动

上游 `package.json` 要求 Node.js `>=18`。本机 WSL 最终使用 Linux Node.js `v24.18.1` 和 npm `10.9.4` 安装及验证。Windows 版 npm 不能从 WSL UNC 工作目录执行 `esbuild` 安装脚本，因此不能把那次失败当作项目缺陷。

基线结果：

| 检查 | 命令 | 退出码/结果 |
| --- | --- | --- |
| 安装 | `npm install` | 0；安装 270 个包；npm 报告 18 个依赖漏洞 |
| 类型检查 | `npm run typecheck` | 0 |
| Lint | `npm run lint` | 0 |
| 生产构建 | `npm run build` | 0；Vite 产物生成成功 |
| 开发服务器 | `npm run dev -- --host 127.0.0.1 --port 4174` | 启动成功；`GET /` 返回 HTTP 200，随后主动终止 |

依赖漏洞和过期的 Browserslist 数据属于上游基线风险。W1 不运行 `npm audit fix --force`，避免引入与 Auth 迁移无关的破坏性升级。

## 2. 技术栈

- Vue 3 + Composition API
- TypeScript 5.5（严格模式）
- Vite 5
- Vue Router 4
- Pinia 2
- Axios 1
- Tailwind CSS 3
- `vuedraggable` Kanban 拖拽
- 自定义 Axios adapter 模拟 REST API
- `localStorage` 保存模拟数据库、登录会话和主题

这是一个前端演示项目：HTTP 调用形状是真实的，但请求不会离开浏览器，身份校验、授权和数据持久化都不具备可信的服务端边界。

## 3. 代码地图与职责边界

```text
src/main.ts
  -> 创建 Vue / Pinia
  -> authStore.hydrate() 恢复本地会话并注册 HTTP token/401 回调
  -> installMockApi() 把 mock adapter 装到共享 Axios 实例
  -> 安装 Router 并挂载应用

View / Component
  -> Pinia Store                 # 页面状态、loading/error、UI 业务动作
    -> Feature Service           # 描述 HTTP 方法、URL、payload/response 类型
      -> api/http.ts             # token、401、重试、错误归一化
        -> mock/mockAdapter.ts    # 当前实际“后端”：路由、校验、权限、CRUD
          -> mock/mockDb.ts       # 内存状态、seed、localStorage 读写
```

关键目录：

- `src/modules/auth/`：会话 Store、登录服务、权限表、登录/注册页。
- `src/modules/projects/`：项目 Store/Service、项目页以及项目活动 Store/Service。
- `src/modules/tasks/`：任务与评论的 Store/Service、Kanban 视图和编辑组件。
- `src/modules/users/`：用户目录 Store/Service 和管理员页面。
- `src/api/http.ts`：所有模块共享的 Axios client 和 `request<T>` 包装器。
- `src/api/mock/`：内存数据库、seed、localStorage 持久化与所有 Mock endpoint。

Store 与 Service 的边界总体清楚：Service 只表达 API 调用；Store 管理响应式状态、loading/error、乐观更新和部分客户端权限断言。当前真正的资源访问检查位于 mock adapter，但它仍是可被用户控制的浏览器代码。

## 4. Mock 与 localStorage 如何工作

### 4.1 Mock 如何拦截登录

`src/main.ts` 在挂载应用前调用 `installMockApi()`。该函数创建 mock DB，并执行：

```ts
http.defaults.adapter = createMockAdapter(db)
```

这会替换共享 Axios 实例 `http` 的 transport adapter。因此 `authService.login()` 虽然调用 `POST /api/auth/login` 的样式接口，但请求不会到网络层；adapter 将 URL 规范化为 `/auth/login` 后直接执行浏览器内的 `login()`。

Mock 登录用明文比较 `user.password !== password`，再用 `btoa(JSON.stringify({ userId }))` 生成一个可伪造 token；这不是 JWT，也不提供签名或过期校验。

### 4.2 Token/session 存在哪里

- Pinia 运行时状态：`auth` Store 的 `session` ref。
- 浏览器持久化：localStorage key `taskflow_pro_session_v1`，内容是完整 `AuthSession`（token + user）。
- 请求时：`authStore.hydrate()` 向 `api/http.ts` 注册 token provider；Axios request interceptor 自动添加 `Authorization: Bearer <token>`。
- 401 时：Axios response interceptor 调用 Store 注册的 handler，当前只清空 localStorage 和 Pinia session。

### 4.3 项目、任务、用户如何持久化

`mockDb.ts` 用单一 localStorage key `taskflow_pro_db_v1` 保存整个 `DbState`：

```text
users[] + projects[] + tasks[] + comments[] + activity[]
```

首次运行由 `seedDb()` 生成管理员、成员、一个项目和三条任务。mock adapter 每次产生写操作后调用 `db.save()`，一次性 JSON 序列化整个状态。项目成员关系目前内嵌为 `Project.memberIds[]`，不是独立关系表。

## 5. 主要调用链

### 5.1 登录

```text
LoginView.onSubmit
  -> authStore.login(email, password)
  -> authService.login
  -> request<AuthSession>
  -> shared Axios http
  -> mock adapter: POST /auth/login
  -> mock DB users 明文比对
  -> 返回伪 token + 去除 password 的 user
  -> Store 写入 taskflow_pro_session_v1
  -> authStore.refreshMe()
  -> mock adapter: GET /auth/me
  -> Router 进入 dashboard
```

页面刷新时 `main.ts -> authStore.hydrate()` 只恢复本地 session；随后受保护页面可以使用 token。当前 bootstrap 不主动调用 `/me`，所以本地保存的用户信息不会在页面挂载前经过重新验证。

### 5.2 项目

```text
ProjectsView / ProjectDetailsView
  -> projectsStore
  -> projectsService
  -> request()
  -> mock adapter /projects...
  -> 检查 token 对应用户与 memberIds
  -> 修改 db.state.projects
  -> db.save() -> taskflow_pro_db_v1
```

创建/更新/删除前，Store 还会调用 `assertPermission()`；列表和详情访问则由 mock adapter 的成员检查决定。

### 5.3 任务与评论

```text
KanbanView / Task components
  -> tasksStore（移动任务时先做乐观更新，失败则回滚）
  -> tasksService
  -> request()
  -> mock adapter /projects/:id/tasks 或 /tasks/:id...
  -> 校验项目成员、修改 task/comment/activity
  -> db.save()
```

## 6. 当前 RBAC 边界

RBAC 在三处执行：

1. `router/index.ts`：`meta.roles` 限制 `/app/users` 仅 admin 进入。
2. `permissions.ts` 和各组件/Store：用权限表隐藏按钮，并在部分写操作前 `assertPermission()`。
3. `mockAdapter.ts`：验证是否登录、是否是项目成员，但没有统一依据权限表校验所有管理操作。例如 `/users` 只要求登录，项目创建/修改也没有在 adapter 中核对 admin 权限。

这些检查都运行在浏览器中，因此只能改善 UX，不能代替后端鉴权。W2 迁移具体资源时，服务端必须重新验证角色和项目成员关系。

## 7. 只迁移 Auth 的最小方案

采用两个 Axios client：

- `realHttp`：base URL 仍为 `/api`，走浏览器默认网络 adapter，仅供 Auth 的 login/me。
- `mockHttp`：继续装载现有 mock adapter，供 Projects/Tasks/Users/Activity。

两个 client 共用同一套 token provider、401 handler、错误归一化和 request wrapper。Auth Service 显式使用 real client，其他 Service 保持 mock client。这样不会按 URL 在一个 adapter 内做隐式分流，阅读调用点即可知道请求去哪，也无需一次性改写全部业务 Service。

为了让真实 JWT 暂时驱动 Mock 资源，还需解决兼容边界：现有 Mock 只会解析它自制的 base64 `{ userId }`。W1 最小做法是在 Mock adapter 中只把真实登录 Store 中的当前用户作为过渡身份来源，或让 adapter 仅为非 Auth 请求从 JWT payload 读取标准 `sub`。后一种只用于维持 Mock 页面，不构成安全边界，并须在迁移文档中明确标记；真实后端不会信任这种前端解析。

同时修改 bootstrap：hydrate 后若有 token，应调用真实 `/auth/me` 完成服务器验证，再允许应用正常进入。401 handler 除清会话外还要跳转登录页（需避免循环依赖，可由 router 安装后绑定导航回调）。

## 8. 迁移风险

- **双 client 身份兼容**：真实 JWT 与旧 mock token 格式不同；若不显式兼容，旧模块会全部 401。
- **启动时序**：当前先 hydrate、后安装 router；刷新校验 `/me` 和 401 跳转需安排好 router 初始化顺序。
- **旧注册页**：W1 后端范围不含注册。若继续让注册走 Mock，它会产生只能存在浏览器的用户，却拿不到服务端 JWT，语义会误导。W1 应明确禁用或标注注册入口，而不是伪装为真实注册。
- **前端用户 ID 类型**：上游类型是 string；后端可使用 `BIGINT` 并以 JSON number 返回，但过渡期 mock 关系使用字符串 ID。为减少差异，API DTO 可把 ID 序列化为 string。
- **401 的影响范围**：Mock 与真实 client 若共享 handler，Mock 数据损坏也可能登出；这是 W1 可接受的显式过渡行为，但后续要随模块迁移收敛。
- **本地明文旧数据**：上游 `taskflow_pro_db_v1` 包含演示用户明文密码。审计后确认其他 Mock 模块并不需要这个字段，因此 W1 落地时已从 seed 删除，并在加载旧 localStorage 时清洗掉密码字段。
- **依赖基线**：npm 当前报告 18 个漏洞；未经逐项分析不能用 force fix。

## 9. W1 最小迁移结论

1. 保持 Vue 源码位置与旧模块 Service/Store 不动。
2. 新增单体 Spring Boot 后端、MySQL/Redis Compose 和 Flyway schema/seed。
3. 后端只完成 health、login、me、JWT 与统一错误；不实现项目/任务业务。
4. 前端把 Auth Service 改走真实 client；其余模块显式走 mock client。
5. 使用服务端 BCrypt seed 用户，沿用上游两个 demo 账号。
6. 启动时用 `/me` 验证已保存 token；任何真实 Auth 401 清理状态并返回登录页。
7. 在迁移状态文档中明确 Auth=REAL，其余=MOCK，并在 W1 结束后停止。
