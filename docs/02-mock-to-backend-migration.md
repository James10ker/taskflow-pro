# Mock → 真实后端迁移状态

更新时间：W2（2026-10-05）

| 模块 | 当前状态 | 请求去向 | 说明 |
| --- | --- | --- | --- |
| Health | **REAL** | Spring Boot `/api/health` | 静态存活检查，不单独证明数据库可用 |
| Auth login | **REAL** | Spring Boot `/api/auth/login` | 数据库用户、BCrypt、服务端 JWT |
| Auth me | **REAL** | Spring Boot `/api/auth/me` | 从已验签 JWT principal 识别用户 |
| Auth register | **NOT IMPLEMENTED** | 无入口 | `/auth/register` 重定向登录，不创建假账号 |
| Projects | **REAL** | Spring Boot `/api/projects/**` | MyBatis + `projects/project_members`；服务端资源权限 |
| Tasks / Comments | **NOT OPEN** | 无真实业务入口 | 遗留 Mock 源码保留，但路由不再暴露，Project 详情不加载 |
| Members management | **NOT IMPLEMENTED** | 无生产接口 | 只有隔离测试 profile 可准备 owner/member 前置数据 |
| Users directory | **NOT OPEN** | 无真实业务入口 | 旧 `/app/users` 重定向 Projects |
| Activity | **NOT OPEN** | 无真实业务入口 | Project 详情明确提示未迁移，不显示虚假 0 条 |

## W2 的真实客户端边界

```text
auth/service.ts -----------\
                             -> requestReal() -> realHttp -> HTTP -> Spring Boot
projects/service.ts -------/

tasks/users/activity service -> 遗留源码；当前 Router/Projects 页面不触发
mock adapter                 -> 源码保留，但 main.ts 不安装
```

真实 Projects 请求失败时只显示统一错误，不会自动回退 localStorage。登录成功、根路径、旧 Dashboard 都进入 `/app/projects`；旧 Kanban/用户目录路径重定向到 Projects。

Vite 开发环境使用同源 `/api` 代理，目标由 `VITE_DEV_API_PROXY_TARGET` 设置。生产默认同源；只有明确的跨域部署才设置 `VITE_API_BASE_URL`。

## 权限迁移结果

- 只有全局 admin 可以创建；owner 始终来自已验证 principal。
- 创建 `projects` 与 owner `project_members` 行在同一事务。
- 列表只按当前用户成员关系过滤；owner/member 可以查询详情。
- 修改、删除只允许项目 owner。全局 admin 对他人项目没有隐式权限。
- 资源存在但无权返回 403，不存在返回 404。
- 前端 owner 按钮只是 UX；后端仍执行全部权限。

## 仍保留的迁移债务

- V2 仍在主 Flyway 路径播种 demo 用户，尚未完成生产种子隔离/历史库治理。
- Tasks、Comments、Activity、成员管理和用户目录没有真实接口。
- Redis 依赖/配置仍存在，但没有业务调用。
- 没有 Playwright 回归套件；临时浏览器验收不能替代可重复 E2E。

详细实现和运行证据见 [w2-projects-verification.md](w2-projects-verification.md)。
