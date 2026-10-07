# 百宠集

每一种宠爱，都有同好。养宠交流社区，提供图文帖子、互动收藏、通知搜索、宠物档案和治理后台；AI 支持主动选择宠物、检索资料引用、回答反馈及确认后整理日常。

完整功能、升级路线、后端分层说明、数据库迁移与运维统一维护在 [项目总方案](md/百宠集项目总方案.md)。

## 目录

- `frontend/`：Vue 3 + Vite 页面。
- `backend/app/api/`：接口、请求模型与认证依赖。
- `backend/app/services/`：用户、社区、AI 等业务逻辑。
- `backend/app/database/`：PostgreSQL、Redis、Chroma 仓储与迁移支持。
- `backend/app/infrastructure/`：OSS 和模型服务适配。
- `backend/alembic/`：数据库版本文件。

## 本地启动

要求 Python 3.13+、uv、Node 22.18+、Docker Desktop。此电脑已有配置和业务数据库；新环境配置步骤见总方案。

项目根目录启动数据服务：

```powershell
docker compose up -d postgres redis
```

后端终端：

```powershell
cd backend
uv sync --locked
uv run alembic upgrade head
uv run python -m app.main
```

前端另开终端：

```powershell
cd frontend
npm ci
npm run dev
```

前端默认 http://127.0.0.1:5500/ ，后端默认 http://127.0.0.1:8001/ 。个人中心 `/#/profile`，管理后台 `/#/admin`，AI 助手 `/#/ai`；管理员使用已有账号登录，不需要单独启动后台服务。

后端使用 `backend/.venv`。若已激活根目录旧虚拟环境，先执行 `deactivate`。当前 AI 任务采用单 worker；登录不依赖 Redis 限流。

## 验证

在 backend 目录：

```powershell
$env:RUN_POSTGRES_TESTS='1'
$env:TEST_REDIS_URL='redis://127.0.0.1:6379/15'
uv run python -m unittest discover -s tests -v
uv run alembic check
```

前端在 frontend 目录运行 `npm test`、`npm run test:e2e` 和 `npm run build`。集成测试使用独立 PostgreSQL schema 与 Redis 测试命名空间。

统一检查：`powershell -File scripts/verify.ps1 -Browsers`。真实浏览器联通测试需设置 `RUN_API_E2E=1`；测试进程使用临时 schema，退出后清理。

本机迁移版本为 `0006_governance_ai`。更新代码后重启前后端即可使用。生产入口为 `scripts/start-production.ps1`，保持单 worker 且关闭热重载。数据库备份与恢复演练：在 backend 运行 `uv run python -m app.backup_database --rehearse`；该命令不会覆盖正式数据库。
