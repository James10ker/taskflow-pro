# W1 数据模型设计

## 设计原则

- 使用一个 MySQL schema 和一个 Spring Boot 单体，不做微服务拆分。
- 主键统一为自增 `BIGINT`，便于初学阶段直接观察和排查数据。
- 全局角色只保留 `admin` / `member`；项目内身份单独放在 `project_members.member_role`。
- W1 只写 users 的 Mapper 和 Auth 业务；六张目标表先由 Flyway 建出第一版，W2 再实现项目侧代码。
- API 把 `BIGINT` ID 返回为字符串，避免 JavaScript 超过安全整数范围后的精度风险，也兼容上游 string ID 类型。

## 关系图

```text
users 1 ----< projects.owner_id
  |               |
  |               +----< project_members >---- users
  |               |
  |               +----< tasks
  |                         |  \
  |                         |   +---- assignee_id / creator_id ---- users
  |                         +----< task_comments >---- users
  |
  +----< activity_logs >---- projects
```

## users

存在原因：保存可信登录身份、BCrypt 密码摘要、全局角色和启用状态。前端 localStorage 中的用户不再是身份来源。

- 主键：`id BIGINT AUTO_INCREMENT`
- 唯一约束：`email`；登录前统一转小写，避免大小写造成重复身份
- 关键字段：`password_hash`、`display_name`、`role`、`is_active`
- 检查约束：role 只能为 `admin` 或 `member`
- 初步索引：唯一 email 索引已经覆盖登录查询；W1 不额外堆索引

## projects

存在原因：项目是任务、成员关系和活动日志的权限边界。

- 主键：`id`
- 外键：`owner_id -> users.id`
- 检查约束：status 为 `active` / `paused` / `completed`，与上游前端的 `ProjectStatus` 保持一致
- 初步索引：`(owner_id, status)`，支持按负责人筛选项目
- 删除策略：不能在仍拥有项目时直接删除 owner；业务层以后应停用用户而非物理删除

## project_members

存在原因：project 与 user 是多对多关系——一个项目有多个用户，一个用户也可参与多个项目。若继续使用前端的 `memberIds[]`，数据库无法可靠建立外键、唯一约束和成员查询索引。

- 复合主键：`(project_id, user_id)`，天然阻止同一用户重复加入项目
- 外键：分别指向 projects 和 users
- 关键字段：`member_role` 表示项目内 owner/member，与 users.role 的全局 admin/member 含义不同
- 初步索引：主键适合从项目查成员；额外 `(user_id, project_id)` 支持从用户查项目
- 约定：项目 owner 也必须有一条 `member_role='owner'` 的成员记录；由 W2 Service 事务维护该不变量

## tasks

存在原因：保存 Kanban 工作项及其项目、负责人、创建人、状态和优先级。

- 主键：`id`
- 外键：`project_id -> projects`、`assignee_id -> users`（可空）、`creator_id -> users`
- 检查约束：status 为 todo/in_progress/done；priority 为 low/medium/high
- 初步索引：`(project_id, status)` 支持看板列；`(assignee_id, status)` 支持个人任务；`due_date` 支持到期筛选
- 删除策略：项目删除时级联删除任务；用户不物理删除，避免破坏负责人/创建人历史

## task_comments

存在原因：评论有独立作者与时间线，不能嵌入 tasks 的 JSON 字段而失去查询和外键能力。

- 主键：`id`
- 外键：`task_id -> tasks`、`author_id -> users`
- 初步索引：`(task_id, created_at)` 支持按时间读取任务评论
- 删除策略：任务删除时级联删除评论

## activity_logs

存在原因：记录项目关键操作，供审计与活动时间线展示；它不替代应用日志。

- 主键：`id`
- 外键：`project_id -> projects`、`actor_id -> users`（允许为空，保留未来系统事件能力）
- 关键字段：`action`、可选 entity 类型/ID、面向用户的 description、扩展用 metadata JSON 文本
- 初步索引：`(project_id, created_at)` 支持项目时间线；`(actor_id, created_at)` 支持按操作者审计
- 删除策略：项目删除时级联清理其活动；W2 需要重新评估正式审计数据是否改为软删除/长期保留

## 当前边界与待 W2 验证项

- 数据库约束能保证引用存在，但“assignee 必须是该项目成员”需要 Service 层事务校验。
- `owner_id` 与 project_members 的 owner 行是有意保留的少量冗余：前者让所有权查询直接，后者让统一成员授权简单；W2 必须在同一事务内维护一致。
- 当前 migration 只 seed 用户，不 seed 项目与任务；旧页面在 W1 继续读取 Mock seed。
- `updated_at` 由应用在更新语句中维护，避免隐藏在数据库触发器里，便于学习和测试。
