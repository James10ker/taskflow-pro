# W1 真实验证记录

日期：2026-09-14（Asia/Shanghai）

本页记录本轮确实执行过的验证。密码和 JWT 密钥只通过临时环境变量/临时 env 文件传入，不记录真实值，也没有写入 Git。

## 环境说明

- 上游 commit：`daf01f99564e2e5025584014cac03d03351e8cdd`
- 工作分支：`feat/w1-real-auth`
- Node：Linux Node `v24.18.1`；npm `10.9.4`
- Java：OpenJDK `21.0.12`
- Maven：`4.0.0-rc-5`
- Docker Engine：`29.0.1`；Compose `2.40.3`
- 当前 WSL 默认 Java 安装只有 JRE、没有 `javac`，所以验证时把 OpenJDK 21 JDK 解压到 `/tmp` 并显式设置 `JAVA_HOME`；这不是仓库依赖。
- WSL 中没有常规 Linux `node` 命令，所以用已安装的 VS Code Server Linux Node 执行 npm。仓库本身仍只要求 Node `>=18`。
- 本机 3306/6379 已被占用，真实 Compose 验收用临时 `MYSQL_HOST_PORT=13306` 与 `REDIS_HOST_PORT=16379`；默认配置仍是标准端口。

## 上游 baseline

在任何业务改动前执行：

| 命令 | 退出码 | 结果 |
| --- | ---: | --- |
| `npm install` | 0 | 安装 270 packages；npm audit 报 18 个既有依赖漏洞（1 low、4 moderate、13 high） |
| `npm run typecheck` | 0 | PASS |
| `npm run lint` | 0 | PASS |
| `npm run build` | 0 | PASS，149 modules transformed |
| `npm run dev -- --host 0.0.0.0 --port 4174` | 0（主动停止前持续运行） | Vite 启动，HTTP 请求返回 200 |

## W1 最终前端

实际执行的 npm 命令前增加了临时 Linux Node 的 `PATH`，业务命令如下：

| 命令 | 退出码 | 关键结果 |
| --- | ---: | --- |
| `npm run typecheck` | 0 | `vue-tsc --noEmit` 无错误 |
| `npm run lint` | 0 | ESLint 0 warnings / 0 errors |
| `npm run build` | 0 | Vite 5.4.21；147 modules；产物成功生成 |

Build 有一条非阻塞警告：`caniuse-lite` 数据已有 9 个月未更新。

## W1 最终后端

在 `backend/` 执行：

| 命令 | 退出码 | 关键结果 |
| --- | ---: | --- |
| `mvn test` | 0 | 5 tests，0 failures，0 errors，0 skipped；BUILD SUCCESS |
| `mvn package` | 0 | 未跳过测试，再次 5/5 通过；生成可执行 Spring Boot JAR；BUILD SUCCESS |

测试使用 Spring Boot 完整上下文 + MockMvc + Flyway + H2 MySQL compatibility mode。真实 MySQL 验收见下一节。Maven 4 输出了项目 root 提示、一个本机配置的 Flyway GitHub Packages metadata 401，以及 Mockito 未来 JDK agent 提示；均未影响编译或测试。

## Docker、MySQL 与 Redis

实际使用 `infra/.env.example` 对应字段生成了未提交的临时 env 文件，并执行：

| 命令 | 退出码 | 关键结果 |
| --- | ---: | --- |
| `docker compose --env-file <temporary-env> -f infra/docker-compose.yml config --quiet` | 0 | Compose 配置有效 |
| `docker compose --env-file <temporary-env> -f infra/docker-compose.yml up -d` | 0 | MySQL 与 Redis 创建并启动 |
| `docker compose ... ps` | 0 | `taskflow-ai-mysql-1` healthy；`taskflow-ai-redis-1` healthy |
| `docker exec taskflow-ai-redis-1 redis-cli ping` | 0 | `PONG` |

为验证最终 V1 migration 能从空库建立，删除并重建了只属于本轮 `taskflow-ai` Compose 项目的临时容器和卷。新 MySQL 8.4 实例中：

- Flyway 从空 schema 成功执行 V1、V2，到 version 2；
- 六张核心业务表全部存在；
- admin/member 两个用户均存在、启用，密码字段前缀均为 BCrypt `$2b$`；
- `projects.status` 约束为 `active / paused / completed`。

Spring Boot 随附的 Flyway 版本提示“MySQL 8.4 高于已测试的 8.1”，但本轮 validation 与 migration 均真实成功。该版本组合仍列为技术风险，不把警告伪装成完全无风险。

## 真实后端 API

用环境变量连接 Docker MySQL/Redis，执行 `java -jar target/taskflow-backend-0.1.0-SNAPSHOT.jar`，应用在 8080 端口成功启动。随后用 Node `fetch` stdin smoke script 实际请求（脚本不输出完整 JWT）：

| 场景 | HTTP | 关键结果 |
| --- | ---: | --- |
| `GET /api/health` | 200 | `{ "status": "UP" }` |
| 正确 admin 登录 | 200 | email/role 正确，Token 为三段式 JWT |
| 错误密码 | 401 | `UNAUTHORIZED` |
| 无 Token 请求 `/api/auth/me` | 401 | `UNAUTHORIZED` |
| 有效 Token 请求 `/api/auth/me` | 200 | 从数据库返回 admin 用户与角色 |
| 无效 Token 请求 `/api/auth/me` | 401 | `UNAUTHORIZED` |
| 非法邮箱 + 空密码 | 422 | `VALIDATION_ERROR`，details 含 email/password |
| 允许来源 `http://localhost:5173` | 200 | 返回精确 origin 和 credentials header |
| 非允许来源 | 403 | 没有 allow-origin header |

## 浏览器端到端

真实运行 Vite 5173、Spring Boot 8080、MySQL 13306 和 Redis 16379，再用独立 Edge headless profile 通过 DevTools Protocol 操作页面。验证脚本退出码 0，结果为：

1. 登录页预填 `admin@taskflow.pro` 和 demo 密码，并明确提示 W1 未迁移注册。
2. 提交真实登录后进入 `/app/dashboard`，session 用户为 admin，Token 有三段。
3. 全页导航到 `/app/projects` 后，真实 `/me` 成功恢复会话。
4. 页面显示 Mock 项目 `Mobile App Redesign`，证明过渡期 Projects 仍可运行。
5. `taskflow_pro_db_v1` 的 users 中已没有 `password` 字段，旧明文 demo 密码被加载迁移清理。

验收后已正常停止临时 Vite、Spring Boot 和 headless Edge；MySQL/Redis Compose 容器保持 healthy，便于继续手工验收。
