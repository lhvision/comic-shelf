# ADR 0037 — 馆长会话凭据升级与根口令零暴露

- **日期**：2026-11-06
- **状态**：Accepted
- **关联**：承接 ADR 0003 (认证与防盗链)、ADR 0006 (访客通行证体系)、ADR 0036 (部署环境变量双轨级联)

## 背景与问题

纸间定位于「本地优先的个人漫画收藏馆与私密阅览室」。在此前的安全与认证架构中：

1. **根口令长期写入客户端 Cookie 与 Storage**：
   馆长在登录页面输入 `COMIC_SHELF_SECRET`（或 `AUTH_SECRET`）后，后端认证通过时直接将明文根口令设为客户端 `HttpOnly; SameSite=Lax` Cookie（`comic_shelf_token`），并原样作为 `LoginResponse.token` 返回前端存入 `localStorage`。
2. **根口令暴露与无法主动吊销风险**：
   - 根口令是服务端环境配置的最高密钥。若以静态形式长期保存在不同客户端的 Cookie 或本地存储中，一旦某台终端（如公共电脑、离职设备、朋友借用手机）未能及时清理，或 Cookie 被物理提取，相当于服务端根凭据被永久窃取；
   - 在旧机制下，馆长登出仅仅是通知客户端清除本地 Cookie 与 Storage，服务端无法单向对已签发的会话执行主动吊销（Revocation）；若想使旧终端失效，必须在服务器修改 `.env` 重启服务，进而迫使所有设备全体掉线。
3. **MCP Token 的安全澄清**：
   对于 `COMIC_SHELF_MCP_TOKEN`，其专供服务端或外部大模型 Client（如 Claude Desktop / IDE 扩展）通过 `Authorization: Bearer` 鉴权，代码体系内从未写入 Cookie，前端也无存储逻辑，具备天然隔离性。

因此，亟需针对 Web 前端与多终端登录场景，将馆长认证升级为高熵临时会话凭据体系，达成**主口令零暴露**、**密码轮换即刻失效**与**服务端主动注销**。

## 核心决策

### 一、会话凭据抽象与主口令零暴露（Zero Master-Credential Exposure）

1. **动态会话生成**：
   馆长在前端提供主口令时，后端仅在内存中通过安全常数时间比对（`secrets.compare_digest`）进行验证。验证成功后，通过 CSPRNG 生成 48 位 16 进制高熵随机会话令牌：
   ```text
   cs_curator_<secrets.token_hex(24)>
   ```
2. **客户端零存储主口令**：
   `set_auth_cookie` 与 `LoginResponse.token` 仅携带并返回生成的 `cs_curator_` 临时会话令牌。无论 Cookie 还是浏览器 LocalStorage，均绝不接触真正的 `AUTH_SECRET`。

### 二、SQLite 会话持久化与滑动窗口续期（Sliding Expiration）

在 SQLite 中开辟独立的 `curator_sessions` 表进行会话生命周期管理：

```sql
CREATE TABLE IF NOT EXISTS curator_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT UNIQUE NOT NULL,
    secret_hash TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    last_active_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    client_ip TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_curator_sessions_expires ON curator_sessions(expires_at);
```

- **初始生命周期**：默认为 30 天（2,592,000 秒）；
- **滑动窗口防写放大续期**：
  在客户端活跃访问时，`verify_and_touch_curator_session` 检查当前时间与 `last_active_at`。为避免高频图片与静态资源请求导致高并发数据库写锁竞争，仅在距上次活跃时间**超过 1 小时（3600 秒）**时，才执行一次 `UPDATE` 刷新 `last_active_at` 与 `expires_at`，兼顾保活与高性能。
- **容量上限与 LRU 自动淘汰**：
  将每个站点的活跃馆长会话总容量上限锁定为 `MAX_CURATOR_SESSIONS = 20`。当超出时自动按最久未活跃（`last_active_at ASC`）淘汰超额历史会话，彻底杜绝无界增长与会话累积。

### 三、密码轮换即刻失效（Secret Fingerprint Binding）

为杜绝“站长在 `.env` 中修改了 `COMIC_SHELF_SECRET`，但旧设备依然凭 SQLite 历史会话登入”的安全死角：

- 每次创建会话时，记录当前主口令的 SHA-256 截断指纹 `secret_hash`；
- 每次会话校验时，比对当前运行态主口令指纹。一旦站长在环境配置中修改口令，所有由旧口令派生的会话在首次请求时**就地阻断并永久销毁**，实现配置级改密即全局吊销。

### 四、服务端确定性主动注销与一键下线全部设备

1. **单设备安全注销**：
   馆长调用 `/api/auth/logout` 时，后端提取当前 `cs_curator_` 令牌并调用 `delete_curator_session(token)` 物理抹除记录。
2. **一键注销全设备**：
   支持 `/api/auth/logout?all=true`（或 `X-Logout-All: 1`），仅限已鉴权馆长调用（未鉴权或访客调用直接拦截 401/403），调用 `delete_all_curator_sessions()`，瞬时清空数据库全部馆长会话，满足丢机或紧急避险诉求。
3. **过期自动清理**：
   在应用启动生命周期（`lifespan`）及定期维护中，调用 `clean_expired_curator_sessions()`，利用 `idx_curator_sessions_expires` 索引毫秒级物理清理过期会话。

### 五、Cookie 缺失时的静默自愈（Cookie Self-Healing）

前端 SPA 在特定浏览器策略或跨标签页场景下，可能保留了 `localStorage` 的 Bearer Token 但被清除了 HttpOnly Cookie。由于网页原生 `<img src="...">` 无法携带自定义 Authorization Header：

- 当客户端通过 Bearer Header 访问 `/api/auth/status` 且鉴权成功时，若服务端探测到 `Cookie: comic_shelf_token` 缺失且凭据为高熵 `cs_curator_` 令牌，自动在响应头回写 `set_auth_cookie`；若凭据为自动化原始根口令，则绝不回写 Cookie，彻底杜绝明文主口令落地；
- 确保后续画页与封面渲染零 401 偶发故障，实现鉴权与媒体推流闭环。

### 六、双轨向下兼容（Dual-Track Architecture for Automation）

为保证自动化脚本、备份工具、cURL 命令或第三方客户端的稳定运行，`get_user_context` 采用双轨降级探测：

1. **第一优先级**：探测令牌是否以 `cs_curator_` 开头，若是则走 SQLite 会话有效性、口令指纹与滑动延期校验；
2. **第二优先级（兼容保底）**：若未匹配会话令牌，继续比对 `secrets.compare_digest(token, AUTH_SECRET)`。自动化脚本在 `Authorization: Bearer <AUTH_SECRET>` 中直接传递根口令依然能够顺畅通行，无需强制改造。

## 影响与收益

1. **根密钥绝不落地**：客户端（Cookie、LocalStorage）只持有短时高熵的 Session Token，根口令永远静默于服务器 `.env` 中；
2. **密码轮换自愈防御**：修改环境变量中的口令即可实现全网旧终端瞬时失效，无残留后门；
3. **多终端可控性**：单设备退出即时吊销，全设备注销一键完成；
4. **媒体推流稳健自愈**：通过状态探测自动修复 Cookie 缺失，杜绝画页加载异常；
5. **性能无感知**：凭借 1 小时节流的延期写回策略与 SQLite 唯一索引，认证查询损耗维持在微秒级。
