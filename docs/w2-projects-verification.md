# W2 Projects 与 W3 MySQL 发布准备验证记录

日期：2026-10-05（Asia/Shanghai）

开发基线分支为 `feat/w1-real-auth`，基线 HEAD 为 `103c54763f4d146237c8a884c5ae0eeafe4a6243`。本页记录 W2/W3 的实现和本地验证证据；发布目标为个人公开 fork `James10ker/taskflow-pro` 的 `feat/w2-projects-mysql-ci` 分支。最终远端提交与 Actions run 属于外部运行证据，以仓库 Actions 历史和最终验收回复为准，不反写进提交制造循环。

## 1. 真实接口与关键文件

| 方法 | 路径 | 实现 | 主要契约 |
| --- | --- | --- | --- |
| GET | `/api/projects` | `ProjectController.list` → `ProjectService.list` → `ProjectMapper.findAllForMember` | 只返回当前 principal 的成员项目 |
| POST | `/api/projects` | `ProjectController.create` → `ProjectService.create` | global admin；owner 来自 principal；201 |
| GET | `/api/projects/{id}` | `ProjectController.get` → `ProjectService.get` | owner/member；存在但无权 403，不存在 404 |
| PUT | `/api/projects/{id}` | `ProjectController.update` → `ProjectService.update` | 仅 owner；只接收 name/description/status |
| DELETE | `/api/projects/{id}` | `ProjectController.delete` → `ProjectService.delete` | 仅 owner；200 `{success:true}` |

关键文件：

- `backend/src/main/java/com/taskflow/backend/project/ProjectController.java`
- `backend/src/main/java/com/taskflow/backend/project/ProjectService.java`
- `backend/src/main/java/com/taskflow/backend/project/ProjectMapper.java`
- `backend/src/main/java/com/taskflow/backend/project/{CreateProjectRequest,UpdateProjectRequest,ProjectResponse}.java`
- `backend/src/main/java/com/taskflow/backend/common/error/GlobalExceptionHandler.java`
- `src/modules/projects/{service,store}.ts`
- `src/modules/projects/views/{ProjectsView,ProjectDetailsView}.vue`
- `src/modules/projects/components/ProjectFormModal.vue`
- `src/router/index.ts`、`vite.config.ts`

Projects JSON 的 ID 字段与上游 TypeScript 类型对齐为字符串。名称在服务端 trim 后不能为空且最长 150；状态只允许 `active/paused/completed`。Jackson 拒绝 ownerId/memberIds 等未知写字段。校验为 422，畸形 JSON和非法路径类型为 400，不支持的方法为 405，错误 Content-Type 为 415。

## 2. 一条真实请求链路

创建项目的实际链路：

```text
ProjectsView / ProjectFormModal
  -> useProjectsStore.create()
  -> projects/service.createProject()
  -> requestReal(realHttp)
  -> POST /api/projects + Bearer token
  -> JwtAuthenticationFilter（验签并建立 UserPrincipal）
  -> ProjectController.create(principal, CreateProjectRequest)
  -> ProjectService.create() @Transactional
  -> ProjectMapper.insert(ProjectEntity)
  -> projects
  -> ProjectMapper.insertOwnerMembership(projectId, principal.id)
  -> project_members(member_role='owner')
  -> 重新查询 ProjectEntity + memberIds
  -> ProjectResponse（id/ownerId/memberIds 为字符串）
  -> Pinia 写入列表并跳转 /app/projects/{id}
```

Controller 不接收 ownerId；权限和事务在 Service，SQL 在 MyBatis Mapper。项目详情页不再调用 tasks、activity 或 users Mock service。

## 3. 项目与 owner 成员行的事务设计

`ProjectService.create` 使用单一 `@Transactional`：先插入 `projects` 取得数据库生成 ID，再插入 `(project_id, principal.id, 'owner')`。任一步抛异常都会回滚，避免“有项目、无 owner 成员关系”。

列表以 `project_members.user_id` join 过滤，而不是只看 `projects.owner_id`。详情先确认项目存在，再确认成员关系；修改、删除先确认存在，再比较 `projects.owner_id`。因此 403/404 与本轮约定一致，global admin 也没有他人项目的隐式权限。

删除使用 V1 已有外键：`project_members`、`tasks`、`activity_logs` 对 project 级联，`task_comments` 对 task 级联。JUnit 在插入 task/comment/activity 后实际删除并逐表确认 0 行。本轮没有修改或 repair V1/V2。

仅 test classpath 的 `ApiTestDataInitializer` 也使用 `TransactionTemplate` 原子准备四个测试账号、共享项目和 owner/member 关系；启动前只允许 H2 内存库，或数据库产品为 MySQL 且当前 catalog 精确等于 `taskflow_api_test`。

## 4. 自动化场景、命令与结果

### Java 集成测试

默认 `/usr/bin/java` 是缺少 `javac/ct.sym` 的裁剪 Java 21 runtime，上一轮用 compiler 参数完成过兼容验证。W3 找到并使用了本机完整 Temurin JDK 21.0.12.1；Maven 4.0.0-rc-5 的 runtime 与 `JAVA_HOME` 一致，使用 pom 的正常 `release=21`，没有任何 compiler 覆盖：

```bash
export JAVA_HOME=/home/james/.local/share/zhuqin/temurin-21
export PATH="$JAVA_HOME/bin:$PATH"
mvn --batch-mode --file backend/pom.xml clean verify
```

W3 退出码 0，JAR 组装和 Spring Boot repackage 均成功：14 tests，0 failures，0 errors，0 skipped。

- `AuthFlowIntegrationTest`：5。
- `ProjectFlowIntegrationTest`：9。

覆盖事务 owner 行、合法 member、非成员 global admin、member 拒绝后数据不变、owner 更新、关联级联删除、未知写字段，以及 401/403/404/422/400/405/415。

### Pytest + Requests（H2 基线）

```bash
./scripts/run-api-tests-h2.sh 3
```

测试目录含 21 个测试函数；参数化展开后每轮收集 28 个用例，其中认证 8、Projects/权限 20。公共客户端有连接/读取 timeout，可创建匿名、非法 token 和四种身份客户端；没有手抄 token 或固定业务项目 ID。

四个 test-only 身份：

- admin owner：`api-owner-admin@taskflow.test`
- 合法普通 member：`api-member@taskflow.test`
- 普通非成员：`api-outsider@taskflow.test`
- 非成员 global admin：`api-outsider-admin@taskflow.test`

共享 member 项目只用于权限前置条件；正常 CRUD 均通过真实 HTTP。动态创建响应在断言前登记，fixture teardown 会用可能的 owner 身份尝试删除，因此失败断言也尽量不遗留。权限拒绝后会由 owner 再查，验证数据未被修改或删除。

最终同一 H2 后端、无手工清库的连续结果：

| 运行 | tests | passed | failed | errors | skipped | JUnit time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 28 | 28 | 0 | 0 | 0 | 0.993s |
| 2 | 28 | 28 | 0 | 0 | 0 | 0.925s |
| 3 | 28 | 28 | 0 | 0 | 0 | 0.862s |

JUnit XML 位于 `.artifacts/api-tests-h2/pytest-h2-run-{1,2,3}.xml`。后端日志明确记录：

- `jdbc:h2:mem:taskflow_api_test`；
- Flyway 成功执行 2 个 migration，到 V2；
- 登录和 `/auth/me` 就绪探测成功；
- 结束时 Hikari shutdown completed，18080 无残留监听。

W3 另外从 `/tmp` 下全新 `--without-pip` venv 开始，经 PyPA 官方 bootstrap 安装 pip，再从 `tests/api/requirements.txt` 安装固定依赖；没有读取系统全局包、旧 venv 或使用 `--break-system-packages`。重构后的共用 runner 以 H2 额外烟测 1 轮，结果为 28 passed、0 failed、0 errors、0 skipped（1.021s）。当前系统仍缺 `ensurepip/python3.12-venv`；标准 Ubuntu 环境应先安装 `python3.12-venv`。

### Pytest + Requests（真实 MySQL 8.4）

W3 使用现有 Docker Desktop daemon，但没有复用或停止原有 `taskflow-ai-mysql-1`、Redis 或其他容器。命令创建唯一名称、随机 host port、`tmpfs /var/lib/mysql` 且无共享 volume 的临时容器：

```bash
export JAVA_HOME=/home/james/.local/share/zhuqin/temurin-21
export PATH="$JAVA_HOME/bin:$PATH"
export TASKFLOW_API_TEST_VENV=/tmp/taskflow-w3-clean-venv
./scripts/run-api-tests-mysql.sh 3
```

实际数据库与启动证据：

- `SELECT VERSION(), DATABASE()`：MySQL `8.4.11`、`taskflow_api_test`；
- 后端日志：`jdbc:mysql://127.0.0.1:<ephemeral-port>/taskflow_api_test (MySQL 8.4)`；
- Flyway 在该库从空 schema 实际执行 V1、V2，最终为 V2；
- 仅 test classpath 的 initializer 通过 MySQL product + 精确 catalog 守卫后准备四身份与共享 member 项目；
- 真实登录和 `/auth/me` 成功后才进入 Pytest。

容器、数据库和后端各只启动一次；轮次之间没有重建数据库、清空全表或手工清理：

| 运行 | tests | passed | failed | errors | skipped | JUnit time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 28 | 28 | 0 | 0 | 0 | 1.385s |
| 2 | 28 | 28 | 0 | 0 | 0 | 1.158s |
| 3 | 28 | 28 | 0 | 0 | 0 | 1.058s |

三轮后，`verify-taskflow-mysql.py` 又通过真实 HTTP 创建临时 project，并用独立 PyMySQL 连接观察到 `projects` 行及唯一 owner membership。脚本直接加入一条 task、comment、activity，再通过 owner 的真实 DELETE API 删除项目；随后直接查询确认：`projects=0`、`project_members=0`、`tasks=0`、`task_comments=0`、`activity_logs=0`。这使“后端实际连接 MySQL”“owner 行同事务写入”和“关联删除在 MySQL 生效”都有独立于 API 响应的数据库证据。

最终 JUnit XML、后端日志和去敏后的数据库直证位于 `.artifacts/w3-mysql-final/`。脚本退出后只删除自己创建的临时容器；复查没有 `taskflow-w3-mysql-*` 残留，原有容器和端口保持不变。

### 前端

| 命令 | 退出码 | 结果 |
| --- | ---: | --- |
| `npm ci` | 0 | Node 24.21.0 / npm 11.19.0；从 lockfile 安装 270 packages |
| `npm run typecheck` | 0 | 无 TypeScript/Vue 错误 |
| `npm run lint` | 0 | 0 warnings / 0 errors |
| `npm run build` | 0 | Vite 5.4.21，117 modules transformed |

Build 只有 `caniuse-lite` 数据过期提示，不影响退出状态。`npm ci` 同时报告上游较旧依赖树的 29 项 advisory（1 low、4 moderate、24 high）；本轮没有执行会改变依赖范围的 `npm audit fix` 或强制升级。

## 5. 浏览器真实请求与独立 API 复查

本轮临时启动 test-classpath Spring Boot（18080）、隔离 H2 和 Vite（5173，代理明确指向 18080），使用独立 Edge 临时 profile + DevTools Protocol 操作页面。临时脚本/profile 已删除，Vite、Spring Boot、Edge 均已停止。

浏览器捕获到：

| 请求 | HTTP |
| --- | ---: |
| `POST /api/auth/login` | 200 |
| `GET /api/auth/me` | 200 |
| `GET /api/projects` | 200 |
| `POST /api/projects` | 201 |
| `GET /api/projects/{generatedId}` | 200 |
| `PUT /api/projects/{generatedId}` | 200 |
| 再次 `GET /api/projects/{generatedId}` | 200 |
| `DELETE /api/projects/{generatedId}` | 200 |
| 返回列表 `GET /api/projects` | 200 |

浏览器外的独立 Node HTTP 客户端读取同一 JWT 但直接访问后端，对同一动态 ID 得到：创建后 200 且 owner/memberIds 正确；修改后 200 且名称/status 已改变；删除后 404。最终浏览器路径为 `/app/projects`，页面不再显示被删项目。这同时排除了 localStorage Mock 持久化作为证据。

## 6. H2、MySQL 与 CI 状态

| 项目 | 状态 | 证据/边界 |
| --- | --- | --- |
| H2 Java 集成测试 | 已实际验证 | 14/14，Flyway V1/V2 |
| H2 真实 HTTP Pytest | 已实际验证 | 28/28 × 3，同一进程、独立准备/清理 |
| H2 浏览器 Projects | 已实际验证 | 浏览器网络 + 独立 API 查询 |
| 标准 JDK 构建 | 已实际验证 | Temurin 21.0.12.1，正常 `clean verify`，JAR/repackage 成功，14/14 |
| Python 干净环境 | 已实际验证 | Python 3.12.3，全新临时 venv，固定依赖；未用全局包或 `--break-system-packages` |
| 本地 Docker | 已实际验证（替代 CLI） | WSL shim 仍阻塞；Docker Desktop Windows CLI 连接 daemon 成功，未触碰既有容器 |
| 本地 MySQL | 已实际验证 | MySQL 8.4.11，28/28 × 3，同库同后端；API→DB 直证与关联级联通过 |
| CI 配置 | 已完成本地核对 | YAML 可解析；共用 runner、完整 JDK、项目 venv、MySQL 8.4、三轮、直证、artifact |
| 远端 MySQL / CI | 以 Actions 证据为准 | 必须核对目标分支最终提交对应的 run URL、必要 job、三轮 XML 与直证 artifact |

Frontend job 已与本地验证环境对齐为 Node 24，并先输出 Node/npm 实际版本。后端 job 也输出 java、javac、Maven 和 Python 版本；Java `clean verify` 先使用 H2 集成测试，黑盒阶段再启动 test-classpath 主程序连接 MySQL。`SPRING_DATASOURCE_DRIVER_CLASS_NAME` 显式设置为 MySQL driver，初始化器检查 product/catalog，runner 要求日志匹配 `jdbc:mysql:...taskflow_api_test`，直证脚本再查询版本/catalog/业务行，避免在旁边启动 MySQL 却实际测试 H2。CI job 直接运行在 Ubuntu runner，故 service 地址使用 `127.0.0.1:3306`；Redis 未启动。

## 7. 一个真实问题修复案例

问题：`requestReal` 的通用策略会对网络错误/5xx重试两次，Projects 的 POST/PUT/DELETE 原先未覆盖该默认值。如果 POST 已在服务端提交但响应丢失，自动重试可能重复创建；DELETE 已成功但响应丢失，重试可能得到 404 并让 UI 误报失败。

修复：`src/modules/projects/service.ts` 对三个写请求显式设置 `{ retries: 0 }`，读取请求仍保留恢复性重试。服务端事务负责原子性，客户端不再假设非幂等写入可安全重放。

同轮还修正了两个测试基础设施风险：隔离库从 URL 子串判断改为 MySQL product + 精确 catalog；测试 fixture 多步写入加入事务。

W3 的实际验证又发现：H2 runner 刚关闭后立即启动 MySQL runner，18080 已无监听进程，但旧端口探测会因短暂 TCP socket 状态误报“端口占用”，从而在进入测试前安全退出。修复是在 bind 探测上设置 `SO_REUSEADDR`；真实监听者仍会使 bind 失败，而本轮刚退出服务不会阻塞下一种数据库验证。第一次 MySQL 容器已由 trap 正确删除，不计入三轮结果。端口修复后三轮通过；最终又收紧 API/JDBC 目标守卫和失败清理，并在一个全新的隔离 MySQL 生命周期按上表完整三轮一次通过。

## 8. 需要掌握的三个核心实现点

1. **认证角色不等于资源权限**：global admin 只决定能否创建；项目查询取决于 `project_members`，修改/删除取决于 owner。principal 永远来自已验签 JWT，不接受客户端 userId。
2. **事务与关系一致性**：项目和 owner 成员行必须同事务；列表以成员关系过滤；删除前要读真实外键，测试包含已有 task/comment/activity 的聚合删除。
3. **黑盒测试的隔离与可重复性**：测试账号只在 test classpath/profile 中准备，目标数据库有硬守卫；token 动态登录，ID 动态创建，拒绝后查状态，finally/fixture teardown 清理，并在同一 MySQL 生命周期连续三次验证；独立 SQL 观察防止把 H2 或假响应当成 MySQL 证据。

## 9. 简历成果与仍缺证据事项

当前有代码和运行证据支撑：

- 在既有 Vue + Spring Boot 项目上完成 Projects 五接口、MyBatis 数据访问、owner/member 资源权限和事务一致性。
- 建立 28-case Pytest + Requests 黑盒接口套件，覆盖四身份、CRUD、错误契约、拒绝无副作用与重复执行；在同一 MySQL 8.4 生命周期三轮共 84 case executions 全通过。
- 增加 9 个 Projects/异常 MockMvc 集成测试，与原 5 个认证测试合计 14/14；验证多表级联删除。
- 实现本地/CI 共用 runner、隔离 MySQL 容器和 API→DB 直证，确认 owner 关系与五表关联删除在 MySQL 8.4 生效。
- 编写 GitHub Actions 配置，包含前端检查、Java/H2、MySQL 8.4 真实后端、三轮 Pytest、JUnit XML 和失败日志归档；远端成果必须附对应最终提交的 run URL。

仍不能写成已完成：

- Tasks、Comments、Activity、成员管理产品接口或管理员用户目录；
- Playwright 套件、Redis 缓存/限流/token 撤销、refresh token；
- “从零设计整个前端/六张表”。前端源自上游，V1/V2 在 W2 前已存在。

远端 CI/MySQL 是否完成不能从本页静态内容推断，必须检查个人 fork 目标分支最终提交对应的 Actions URL 与 `backend-and-api-test-results` artifact。

## 10. 发布边界

发布分支为 `feat/w2-projects-mysql-ci`，个人远端为公开 fork `James10ker/taskflow-pro`；`upstream` 继续指向 `Siggmond/taskflow-pro`，不向上游推送或创建 PR。W1 的五个本地提交作为本分支历史保留。

相对 `upstream/main` 保留的 W1 提交为：`0d528a3 docs: audit upstream frontend architecture`、`da769f1 chore: add backend and local infrastructure scaffold`、`558512d feat: implement mysql-backed jwt authentication`、`5ab8894 feat: connect frontend auth to real backend`、`103c547 test: verify w1 auth vertical slice`。W2/W3 发布范围分为：

- Projects 后端、统一错误与 9 个 Java 集成测试；
- test-only 四身份/成员 fixture、21 个 Pytest 函数（28 个展开用例）、共用/H2/MySQL runner 与数据库直证；
- Projects 前端真实 service/store/views、路由、登录后跳转和 Vite proxy；
- CI、README、迁移说明、验收文档和示例环境配置。

`ATTRIBUTION.md`、V1/V2 历史迁移均未修改；构建目录、临时 venv 和 `.artifacts` 被 gitignore 排除。发布前的敏感模式扫描未发现私钥、GitHub/AWS token 或 Bearer JWT；CI 文件中的数据库口令只是每个隔离 service 使用的公开、一次性测试值，不是业务凭据。

发布按两笔可审核提交组织：

1. `feat: implement real projects workflow and resource permissions`：Projects 后端分层、权限与事务、前端真实链路、Java 集成测试；
2. `test: verify projects against mysql and add ci workflow`：test-only 四身份初始化、Pytest/Requests、共用 runner、MySQL 直证、CI、README/验收文档。

远端验收必须核对工作流实际 checkout SHA、两个必要 job、MySQL 三轮 XML/直证 artifact；不能只依据工作流名称或历史绿色记录。
