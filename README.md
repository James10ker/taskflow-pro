# Taskflow

Taskflow 是一个用于展示 Java 后端与接口测试能力的全栈项目。当前真正接入服务端和数据库的范围是认证与 Projects：登录、当前用户、项目创建、成员可见列表、详情、修改和删除。Projects 的身份与资源权限由 Spring Security 认证结果和数据库成员关系在服务端执行，不依赖前端按钮隐藏。

上游 Vue 前端来自 [Siggmond/taskflow-pro](https://github.com/Siggmond/taskflow-pro)。本仓库保留 MIT License 与 [ATTRIBUTION.md](ATTRIBUTION.md)，不把上游已有页面、六张表或前端架构声明为本轮从零完成的成果。

## 当前真实范围

| 模块 | 状态 | 数据来源 |
| --- | --- | --- |
| `GET /api/health` | 真实后端 | Spring Boot；仅表示 HTTP 进程存活 |
| 登录、`/auth/me` | 真实后端 | MySQL（主程序）或 H2（隔离测试） |
| Projects CRUD、成员可见列表 | 真实后端 | `projects`、`project_members` |
| Tasks、Comments、Activity | 暂未开放 | 遗留 Mock 源码仍在仓库，但真实入口不安装 Mock adapter，也不加载这些模块 |
| 成员邀请/移除、用户目录 | 暂未开放 | 本轮只有测试 profile 可准备成员前置关系，不是生产成员管理接口 |
| Redis | 未参与业务请求 | 仅保留既有依赖和配置；本轮不启动缓存、限流或 token 撤销 |
| Playwright E2E | 未实现 | 本轮只做过一次临时 Edge/CDP 真实浏览器验收，未提交可重复 UI 套件 |

`V2__seed_demo_users.sql` 仍位于主迁移路径，会为新库准备原有演示账号。本轮没有修改 V1/V2、repair checksum 或宣称完成生产种子治理。

## 技术栈与结构

- 后端：Java 21、Spring Boot 3.5.16、Spring Security、JWT、MyBatis 3.0.5、Flyway。
- 数据库：主程序使用 MySQL；Java 集成测试使用 H2；黑盒接口套件可由同一 runner 连接 H2 或隔离 MySQL 8.4。
- 前端：Vue 3、TypeScript、Pinia、Vue Router、Vite、Axios。
- 自动化：JUnit 5 + MockMvc、Pytest 9.1.1 + Requests 2.34.2、JUnit XML、GitHub Actions。

```text
backend/src/main/java/       # Spring Boot 认证、Projects、统一异常与安全配置
backend/src/main/resources/  # application.yml 与 Flyway V1/V2
backend/src/test/            # H2 集成测试、仅 test classpath 的 api-test 初始化器
src/                         # Vue 前端；当前业务入口只暴露真实 Projects
tests/api/                   # 面向真实 HTTP 进程的 Pytest + Requests
scripts/                     # 共用黑盒 runner、H2/MySQL 包装入口、数据库直证与就绪探测
infra/                       # 可选的本地 MySQL/Redis Compose；Projects 不需要 Redis
.github/workflows/ci.yml     # 前端、Java/H2、MySQL 8.4 三轮 Pytest 工作流配置
docs/                        # 数据模型、迁移状态和逐轮验证记录
```

## Projects API 与权限

所有路径以 `/api` 为前缀。项目 ID、owner ID 和 member ID 在 JSON 中是字符串。

| 方法与路径 | 用途 | 规则 |
| --- | --- | --- |
| `GET /auth/me` | 当前用户 | 有效 JWT |
| `GET /projects` | 当前用户可访问的项目 | 只按 `project_members.user_id` 返回 owner/member 项目 |
| `POST /projects` | 创建项目 | 仅全局 `admin`；owner 来自已验证 principal，同时创建 owner 成员行 |
| `GET /projects/{id}` | 项目详情 | owner/member 可查；已存在但无权为 403，不存在为 404 |
| `PUT /projects/{id}` | 修改名称、描述、状态 | 仅项目 owner；不接受 owner/member 字段 |
| `DELETE /projects/{id}` | 删除项目聚合 | 仅项目 owner；依照 V1 外键级联清理已有相关记录 |

权限矩阵：

| 操作 | 未认证 | 普通 member（项目成员） | 项目 owner | 非成员 global admin |
| --- | ---: | ---: | ---: | ---: |
| 创建 | 401 | 403 | 仅当其全局角色为 admin | 允许创建自己的新项目 |
| 列表/详情 | 401 | 允许 | 允许 | 目标项目不可见，详情 403 |
| 修改/删除 | 401 | 403 | 允许 | 403 |

DTO 校验错误返回 422；畸形 JSON/非法路径类型返回 400；不支持的方法和 Content-Type 分别返回 405/415。错误体统一包含 `code` 和 `message`，校验错误另含 `details`。

## 从干净环境运行

### 前置条件

- 完整 JDK 21（必须包含支持 `--release 21` 的 `javac`）和 Maven。
- Node.js 24（本地与 CI 已对齐；项目最低声明为 Node 18）与 npm。
- Python 3.12、`venv`/`ensurepip`；Debian/Ubuntu 通常需要 `python3.12-venv` 或 `python3-venv`。
- 运行主程序时需要隔离 MySQL 8.4；Docker 只是可选准备方式。

不要把下面的示例指向个人或团队业务库。不要复用共享 Compose project/volume。

### 1. 启动隔离 MySQL（可选 Compose 方式）

在新 shell 中设置仅供本地隔离环境使用的值：

```bash
export MYSQL_DATABASE=taskflow
export MYSQL_USER=taskflow
export MYSQL_PASSWORD='<isolated-db-password>'
export MYSQL_ROOT_PASSWORD='<isolated-root-password>'
export MYSQL_HOST_PORT=13306
docker compose -p taskflow-w2-local -f infra/docker-compose.yml up -d mysql
```

只启动 `mysql`，本轮业务不需要 Redis。停止时使用同一明确 project name：

```bash
docker compose -p taskflow-w2-local -f infra/docker-compose.yml down
```

该命令不带 `-v`，不会删除 volume。不要对不属于本轮的 Compose project 执行停止或清理。

### 2. 启动后端

```bash
export MYSQL_URL='jdbc:mysql://127.0.0.1:13306/taskflow?useUnicode=true&characterEncoding=utf8&serverTimezone=UTC&allowPublicKeyRetrieval=true&useSSL=false'
export MYSQL_USER=taskflow
export MYSQL_PASSWORD='<same-isolated-db-password>'
export JWT_SECRET="$(openssl rand -base64 48)"
export FRONTEND_ORIGINS='http://localhost:5173,http://127.0.0.1:5173'
cd backend
mvn spring-boot:run
```

应用启动时 Flyway 校验并执行 V1/V2。`/api/health` 是静态存活检查；数据库就绪应通过一次真实登录和 `/api/auth/me`，本仓库的 `scripts/wait-for-taskflow-api.py` 正是这样检查。

### 3. 启动前端

另开 shell，在仓库根目录执行：

```bash
npm ci
cp .env.example .env.local
npm run dev
```

默认访问 `http://localhost:5173`。Vite 把同源 `/api` 代理到 `VITE_DEV_API_PROXY_TARGET`（默认 `http://127.0.0.1:8080`）。生产同源部署可不设置 `VITE_API_BASE_URL`；只有刻意跨域部署时才设置完整 API base URL。

登录成功后直接进入 `/app/projects`。旧 Dashboard、Kanban 和用户目录 URL 会重定向到真实 Projects，不会在真实请求失败时回退到 Mock。

## 测试

### Java/H2 集成测试

完整 JDK 21 环境：

```bash
export JAVA_HOME=/path/to/full-jdk-21
export PATH="$JAVA_HOME/bin:$PATH"
mvn --batch-mode --file backend/pom.xml clean verify
```

当前测试包含 5 个认证测试和 9 个 Projects/异常契约测试。Projects 测试会验证 owner 成员行、多角色权限、拒绝后无副作用、更新后查询，以及带 task/comment/activity 关联记录时的级联删除。

### 一键真实 HTTP H2 测试

```bash
./scripts/run-api-tests-h2.sh 3
```

H2 包装入口和下方 MySQL 包装入口都调用 `scripts/run-api-tests.sh`。该共用 runner 按顺序完成：

1. 创建仓库内已忽略的 Python venv 并安装固定版本依赖；
2. 拒绝复用已占用的测试端口；
3. 验证 Maven、`java`、`javac` 使用完整 Java 21，再编译 test runtime；
4. Flyway 执行 V1/V2；
5. 通过仅存在于 test classpath 的 `api-test` profile，以事务方式准备四个测试身份和一个 owner/member 共享项目；
6. 用真实登录 + `/auth/me` 确认 HTTP 与数据库同时就绪；
7. 对同一后端连续运行指定次数的 Pytest，每轮自己创建和清理动态项目；
8. 写出每轮 JUnit XML 和后端日志；
9. trap 只终止本轮后端进程组，H2 随进程销毁。

脚本自动生成测试密码和 JWT secret，不会把它们写进仓库或输出到终端。若主动提供 `APP_API_TEST_PASSWORD` 与 `TASKFLOW_API_TEST_PASSWORD`，两者必须一致。写数据的测试默认拒绝非 loopback URL；远程隔离环境必须显式设置 `TASKFLOW_API_TEST_ALLOW_REMOTE=true`。默认必须使用完整 JDK；上一轮裁剪 runtime 的兼容参数只在显式设置 `TASKFLOW_ALLOW_JRE_COMPILER_FALLBACK=true` 时启用，不应复制到标准环境。

### 一键真实 HTTP MySQL 8.4 测试

在 Docker daemon 可用、且 `JAVA_HOME` 与 `PATH` 指向同一完整 JDK 21 时：

```bash
./scripts/run-api-tests-mysql.sh 3
```

该入口创建唯一命名、自动分配端口、`tmpfs` 数据目录的 `mysql:8.4` 临时容器，不挂载或删除共享 volume，也不会停止其他服务。容器只启动一次；共用 runner 只启动一次后端，并在同一数据库生命周期内连续运行三轮。最后 `verify-taskflow-mysql.py` 通过独立 PyMySQL 连接确认：

- 服务器确为 MySQL 8.4、catalog 精确为 `taskflow_api_test`，Flyway V1/V2 成功；
- API 创建的 project 与 owner membership 已写入 MySQL；
- 临时插入 task/comment/activity 后，经 owner 的真实 DELETE API 删除项目；
- `projects/project_members/tasks/task_comments/activity_logs` 对应记录均为 0。

本机 Docker 的 WSL shim 不可用时，脚本会尝试 Docker Desktop 的 Windows CLI；也可通过 `DOCKER_BIN` 指定已授权的 CLI。无可用 daemon 时脚本会明确失败，不会回退 H2。

本轮最终本机结果：标准 JDK 构建 14/14；MySQL Pytest 三轮各 28 passed、0 failed、0 errors、0 skipped；共用 runner 的额外 H2 烟测 28/28；前端 typecheck/lint/build 均通过。详细证据见 [Projects verification](docs/w2-projects-verification.md)。

## CI

`.github/workflows/ci.yml` 配置了两个 job：

- Frontend：Node 24、输出 Node/npm 实际版本、`npm ci`、typecheck、lint、build。
- Backend/API：Temurin Java 21、Maven `clean verify`、Python 3.12 项目 venv、隔离 MySQL 8.4、test-classpath 后端、三轮真实 HTTP Pytest 与 MySQL 直证。

MySQL job 与本地入口共用 `scripts/run-api-tests.sh`，显式覆盖 JDBC driver，并在就绪探测后要求后端日志出现 `jdbc:mysql:...taskflow_api_test`，防止实际仍连 H2。Java Surefire XML、三轮 Pytest XML、数据库直证和后端日志在失败时也会归档；核心步骤没有 `continue-on-error`。Redis 未启动。

证据边界：工作流文件已通过本地 YAML、shell 和 Python 静态检查；其共用的 Java 构建、MySQL 启动、三轮测试和直证流程已在本机实际通过。远端状态必须以个人 fork 目标分支最终提交对应的 Actions run URL、必要 job 和 artifact 为准，不能用本地结果或历史绿色记录替代。

远端验收应保存 run URL、工作流实际 checkout 的 commit SHA 和 `backend-and-api-test-results` artifact；本项目不向上游 remote 推送或自动创建 PR。

## 已知限制

- 没有公开注册、refresh token 或 Redis token 撤销；logout 仍是客户端清除 access token。
- Tasks、Comments、Activity、成员管理产品功能和管理员用户目录尚未迁移；页面明确显示未开放，不用 Mock 数据伪装为 0 条。
- V2 仍在主 Flyway 路径播种 demo 用户；生产种子隔离与历史库迁移治理待后续完成。
- 本轮没有可重复 Playwright 套件；远端 CI 结果不固化在 README 中，以目标分支对应的 Actions run 为准。
- 当前 WSL 的 `docker` shim 仍未启用 integration；本轮通过已安装的 Docker Desktop Windows CLI 完成隔离 MySQL 验证。启用 WSL integration 可恢复标准 `docker` 命令，但不是远端 CI 前置条件。
- 默认 `/usr/bin/java` 是缺少 `javac/ct.sym` 的裁剪 runtime；本机另有完整 Temurin JDK 21，已用于正常 `clean verify` 和 MySQL 验证。日常开发与 CI 均应显式使用完整 JDK。
- 当前系统 Python 缺少 `ensurepip/python3.12-venv`；本轮在全新临时 venv 中用 PyPA bootstrap 安装依赖并验证。标准 Ubuntu 环境应安装 `python3.12-venv`。
- 上游较旧的前端依赖树在本轮 `npm ci` 后报告 29 项 advisory；本轮没有用强制升级扩大业务范围。

## 贡献边界

本轮基线是分支 `feat/w1-real-auth` 的 commit `103c54763f4d146237c8a884c5ae0eeafe4a6243`。W1 已有真实认证；W2 的新增贡献是 Projects 服务端分层与权限、前端真实 Projects 入口、Java 风险测试、Pytest/Requests 与 H2 入口；W3 新增标准工具链验证、共用 runner、隔离 MySQL 8.4 三轮回归、数据库直证和 CI 收敛。V1/V2 表结构、上游 Vue 页面和未迁移 Mock 模块不是本轮从零设计成果。

## License

MIT。详见 [LICENSE](LICENSE) 与 [ATTRIBUTION.md](ATTRIBUTION.md)。
