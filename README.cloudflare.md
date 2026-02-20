# Grok2API（Cloudflare Workers / Pages：D1 + KV）

这个仓库已经新增 **Cloudflare Workers / Pages** 可部署版本（TypeScript）。

> 一键部署前置条件：若使用 GitHub Actions 工作流，请先在仓库 Secrets 配置 `CLOUDFLARE_API_TOKEN` 与 `CLOUDFLARE_ACCOUNT_ID`。  
> Docker 一键启动入口仍是 `docker compose up -d`，请参考 `readme.md`。

## 功能概览

- **D1（SQLite）**：持久化 Tokens / API Keys / 管理员会话 / 配置 / 日志
- **KV**：缓存 `/images/*` 的图片/视频资源（从 `assets.grok.com` 代理抓取）
- **每天 0 点统一清除**：通过 KV `expiration` + Workers Cron 定时清理元数据（`wrangler.toml` 已配置，默认按北京时间 00:00）
- **前端移动端适配一致生效**：Workers 与 FastAPI/Docker 复用同一套 `/static/*` 资源，包含手机端抽屉导航、表格横向滚动、API Key 居中悬浮新增弹窗等交互

> 原 Python/FastAPI 版本仍保留用于本地/Docker；Cloudflare 部署请按本文件走 Worker 版本。

---

## 升级/迁移（不丢数据）

- Workers 代码更新不会清空 D1 / KV：只要继续绑定同一个 D1 数据库和 KV Namespace，账户数据（Tokens / Keys / 配置 / 日志）不会丢。
- 缓存不会因为升级而立刻丢失：KV 中的缓存对象会按“本地 0 点”过期（expiration）并由 Cron 每天清理元数据，升级后仍保持一天一清理。
- 注意不要随意改 `wrangler.toml` 里的 `name` / D1/KV 绑定 ID；如果你用 GitHub Actions 一键部署，也请保持 Worker 名称一致，否则可能创建新的 D1/KV 资源导致“看起来像丢数据”。
- 管理员账号密码不会被默认值覆盖：迁移脚本使用 `INSERT OR IGNORE` 初始化默认配置；如果你之前已在面板里修改过账号/密码，升级后会保留原值。

## 0) 前置条件

- Node.js 18+（你本机已满足即可）
- 已安装/可运行 `wrangler`（本仓库使用 `npx wrangler`）
- Cloudflare 账号（已托管域名更好，便于绑定自定义域名）

---

## 1) 初始化（本地）

```bash
npm install
```

登录 Cloudflare：

```bash
npx wrangler login
```

---

## 2) 创建并绑定 D1（仅手动部署需要）

创建 D1：

```bash
npx wrangler d1 create grok2api
```

把输出里的 `database_id` 填进 `wrangler.toml`：

- `wrangler.toml` 的 `database_id = "REPLACE_WITH_D1_DATABASE_ID"`

应用迁移（会创建所有表）：

```bash
npx wrangler d1 migrations apply grok2api --remote
```

你也可以直接按绑定名执行（推荐，避免改名后出错）：

```bash
npx wrangler d1 migrations apply DB --remote
```

迁移文件在：

- `migrations/0001_init.sql`
- `migrations/0002_r2_cache.sql`（旧版，已废弃）
- `migrations/0003_kv_cache.sql`（新版 KV 缓存元数据）

---

## 3) 创建并绑定 KV（仅手动部署需要）

KV Namespace 建议命名为：`grok2api-cache`

如果你使用 GitHub Actions（推荐），会在部署前自动：

- 创建（或复用）D1 数据库：`grok2api`
- 创建（或复用）KV namespace：`grok2api-cache`
- 自动绑定到 Worker（无需你手动填任何 ID）

如果你手动部署，可以自己创建 KV namespace 并把 ID 填进 `wrangler.toml`：

```bash
npx wrangler kv namespace create grok2api-cache
```

然后把输出的 `id` 填到 `wrangler.toml`：

- `[[kv_namespaces]]`
  - `binding = "KV_CACHE"`
  - `id = "<你的namespace id>"`

---

## 4) 配置每天 0 点清理（Cron + 参数）

`wrangler.toml` 已默认配置（按北京时间 00:00）：

- `CACHE_RESET_TZ_OFFSET_MINUTES = "480"`：时区偏移（分钟），默认 UTC+8
- `crons = ["0 16 * * *"]`：每天 16:00 UTC（= 北京时间 00:00）触发清理
- `KV_CACHE_MAX_BYTES = "26214400"`：最大缓存对象大小（KV 单值有大小限制，建议 ≤ 25MB）
- `KV_CLEANUP_BATCH = "200"`：清理批量（删除 KV key + D1 元数据）

---

## 5) 部署到 Workers（推荐，功能最完整）

部署：

```bash
npx wrangler deploy
```

部署后检查：

- `GET https://<你的域名或workers.dev>/health`
- 打开 `https://<你的域名或workers.dev>/login`

（可选）冒烟测试：

```bash
python scripts/smoke_test.py --base-url https://<你的域名或workers.dev>
```

默认管理员账号密码：

- `admin / admin`

强烈建议登录后立刻修改（在「设置」里改 `admin_password` / `admin_username`）。

---

## 5.1) GitHub Actions 一键部署（推荐）

仓库已包含工作流：`.github/workflows/cloudflare-workers.yml`，在 `main` 分支 push 时会自动：

1. `npm ci` + `npm run typecheck`
2. 自动创建/复用 D1 + KV，并生成 `wrangler.ci.toml`
3. `wrangler d1 migrations apply DB --remote --config wrangler.ci.toml`
4. `wrangler deploy`

触发策略保持不变：

- `push` 到 `main`：自动触发 Cloudflare 部署作业
- `workflow_dispatch`：可手动选择 `cloudflare/docker/both`
- `v*` tag：用于 Docker 构建发布链路

你需要在 GitHub 仓库里配置 Secrets（Settings → Secrets and variables → Actions）：

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`（必填）

> 提示：`CLOUDFLARE_API_TOKEN` 建议使用 **API Token**（不要用 Global API Key），并确保至少包含 **Workers Scripts / D1 / Workers KV Storage** 的编辑权限；否则工作流可能无法自动创建/复用 D1/KV 或部署 Worker。

然后直接 push 到 `main`（或在 Actions 页面手动 Run workflow）即可一键部署（无需你手动创建/填写 D1 或 KV 的 ID）。

> 注意：此版本不再使用 R2。GitHub Actions 会自动创建/复用 D1 与 KV，但你仍需在 GitHub 配好 `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID`。
>
> 另外：`app/static/_worker.js` 是 Pages Advanced Mode 的入口文件。Workers 部署时会被 `app/static/.assetsignore` 排除，避免被当成静态资源上传导致部署失败。

---

## 6) 绑定自定义域名（你有 CF 托管域名）

在 Cloudflare Dashboard：

1. Workers & Pages → 选择 `grok2api` 这个 Worker
2. Settings / Triggers（不同 UI 可能略有差异）
3. 找到 **Custom Domains** → Add
4. 选择你的域名并创建

绑定完成后，直接用你的域名访问 `/login` 与 `/v1/*` 即可。

---

## 7) 后台初始化配置（必须）

登录 `/admin/token` 后至少配置（`/manage` 仍保留为兼容入口，会跳转）：

1. **Tokens**：添加 `sso` 或 `ssoSuper`
   - 添加后会 **自动为所有新 Token 开启 NSFW**（账户级别的 `always_show_nsfw_content`）
   - 也可以在 Token 列表中选中 Token 后点击 🛡 按钮手动一键开启
2. **设置**：
   - `dynamic_statsig`（建议开启）
   - 或者关闭动态并填写 `x_statsig_id`
   - （可选）填写 `cf_clearance`（只填值，不要 `cf_clearance=` 前缀）
   - （可选）开启 `video_poster_preview`：将返回内容中的 `<video>` 替换为 Poster 预览图（默认关闭）
   - （可选）`image_generation_method`：`legacy`（默认，稳定）或 `imagine_ws_experimental`（实验性新方法，失败自动回退旧方法）
   - **图片NSFW**：控制图片生成 WS 负载中 `enable_nsfw` 字段（默认开启）
3. **Keys**：创建 API Key，用于调用 `/v1/*`

---

## 8) 接口

- POST /v1/chat/completions (supports stream: true)
- GET /v1/models
- GET /v1/images/method: returns current image-generation mode (legacy or imagine_ws_experimental) for /chat and /admin/chat UI switching
- POST /v1/images/generations: experimental mode supports size (aspect-ratio mapping) and concurrency (1..3)
- POST /v1/images/edits: only accepts grok-imagine-1.0-edit
- GET /images/<img_path>: reads from KV cache; on miss fetches assets.grok.com and writes back to KV (daily expiry/cleanup policy)
- Note: Workers KV single-value size is limited (recommended <= 25MB); most video players use Range requests, which may bypass KV hits
- Admin APIs: /api/*
- POST /api/tokens/enable-nsfw: 为指定 Token 开启账户级 NSFW（gRPC-Web 调用 `UpdateUserFeatureControls`）

### 支持的模型

| 模型 | 类型 | 说明 |
|------|------|------|
| grok-3 | 聊天 | Grok 3 |
| grok-3-mini | 聊天 | Grok 3 Mini (Thinking) |
| grok-3-thinking | 聊天 | Grok 3 Thinking |
| grok-4 | 聊天 | Grok 4 |
| grok-4-mini | 聊天 | Grok 4 Mini |
| grok-4.1-mini | 聊天 | Grok 4.1 Mini |
| grok-4-thinking | 聊天 | Grok 4 Thinking |
| grok-4.20-beta | 聊天 | Grok 4.20 Beta |
| grok-imagine-1.0 | 图片生成 | 图片生成模型 |
| grok-imagine-1.0-edit | 图片编辑 | 图片编辑模型 |
| grok-video-1.0 | 视频生成 | 视频生成模型 |

### 8.1) 管理后台 API 兼容语义（与 FastAPI 一致）

- GET /api/v1/admin/tokens adds fields (compatible): token_type, quota_known, heavy_quota, heavy_quota_known
- POST /api/v1/admin/keys/update returns 404 when key does not exist
- Quota semantics: remaining_queries = -1 means unknown quota; frontend should use quota_known / heavy_quota_known for judgement

---

## 9) 部署到 Pages（可选，但不推荐用于“定时清理”）

仓库已提供 Pages Advanced Mode 入口：

- `app/static/_worker.js`

部署静态目录：

```bash
npx wrangler pages deploy app/static --project-name <你的Pages项目名> --commit-dirty
```

然后在 Pages 项目设置里添加绑定（名称必须匹配代码）：

- D1：绑定名 `DB`
- KV：绑定名 `KV_CACHE`

注意：

- **自动清理依赖 Cron Trigger**，目前更推荐用 Workers 部署该项目以保证定时清理稳定运行。

---

## 10) Worker 出站更倾向美区（可选）

本仓库默认在 `wrangler.toml` 将 Workers 的 Placement 固定在美国（Targeted Placement）：

```toml
[placement]
region = "aws:us-east-1"
```

这会让 Worker 的执行位置更稳定地靠近美国区域，从而让出站更偏向美区（对上游在美区的场景更友好）。

如需调整：把 `region` 改成你想要的区域（例如 `aws:us-west-2`）。
如需关闭：删除 `wrangler.toml` 中的 `[placement]` 段落即可（恢复默认的边缘就近执行）。

---

## 11) 发布后验证（建议）

部署后可执行以下最小检查：

1. 基础健康与登录页：
   - `GET /health`
   - `GET /login`
2. 管理页可访问性：
   - `GET /admin/token`
   - `GET /admin/keys`
3. 移动端回归（建议使用 `390x844`）：
   - `/admin/keys`：点击“新增 Key”后应为居中悬浮弹窗（有遮罩，可点遮罩关闭，可 `Esc` 关闭）
   - 顶部导航：手机端应为抽屉菜单（可打开/关闭，点击菜单项后自动收起）
   - Token/Keys/Cache 表格：应保持横向滚动，不应压碎列布局
4. 可选 smoke test：

```bash
python scripts/smoke_test.py --base-url https://<你的域名或workers.dev>
```
