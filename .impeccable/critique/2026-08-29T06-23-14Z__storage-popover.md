---
timestamp: 2026-08-29T06-23-14Z
slug: storage-popover
---

# 纸间 · Paper Room — PWA 与设备离线存储面板 A 轨设计评审报告

**评审对象**：`src/components/StoragePopover.vue`（配合 `useOfflineStorage.ts`、`usePwaInstall.ts`、`AppHeader.vue`）  
**评审角色**：独立设计总监（Design Director · Assessment A）  
**评审标准**：Nielsen 10 项可用性启发式准则、纸间典藏物理装订美学（Quiet Archive / Vermilion Ink）、认知负荷评估模型

---

### 1. Design Health Score（设计可用性健康度评分）

| #        | 启发式可用性维度 (Heuristic)                           | 得分 (0-4) | 关键缺陷与核心裁定                                                                                                                 |
| -------- | ------------------------------------------------------ | :--------: | ---------------------------------------------------------------------------------------------------------------------------------- |
| 1        | **系统状态可见性** (Visibility of System Status)       |   **2**    | 清理缓存后 Toast 提示产生数值竞态，显示荒谬的「已释放 0 B」；初始加载前硬编码显示「离线已就绪」产生虚假反馈                        |
| 2        | **系统隐喻与现实匹配** (Match System & Real World)     |   **3**    | 文案宣称「500MB LRU 保护」，但 Workbox 真实规则为 1000 篇目；红点徽标被误用为 PWA 安装提示，违背告警隐喻                           |
| 3        | **用户控制度与自由度** (User Control & Freedom)        |   **2**    | 「重置全部离线环境」属高危破坏性操作，却无任何二次确认弹窗或撤销机制，单次误触即销毁全站 Service Worker                            |
| 4        | **一致性与行业标准** (Consistency & Standards)         |   **3**    | `AppPopover` 的指示箭头写死在左侧 16px，与 `align="end"` 彻底脱靶；刻度轨圆角胶囊与全站 3px 平直标尺规范不一致                     |
| 5        | **防错机制** (Error Prevention)                        |   **2**    | 重置按钮只有 16px 触控高度（`padding: 0`），紧贴常规清理按钮下方，移动端与触控板极易产生灾难性误触                                 |
| 6        | **识别而非回忆** (Recognition Rather Than Recall)      |   **3**    | 触发按钮写死 `aria-label="查看设备离线存储"`，遮蔽了屏幕阅读器对实际容量（如 12.4 MB）的读出；顶栏「离线」与「本地优先」概念易混淆 |
| 7        | **灵活性与使用效率** (Flexibility & Efficiency)        |   **3**    | 缺乏针对 iOS Safari（不支持 `beforeinstallprompt`）的「添加到主屏幕」指导说明；非现代浏览器降级缺乏 Esc 键盘关闭                   |
| 8        | **美学与极简主义设计** (Aesthetic & Minimalist Design) |   **3**    | 整体暖纸色与分项账单排版得当；但触发按钮红点制造了不必要的通知焦虑（Notification Fatigue），进度条缩放产生椭圆拉伸畸变             |
| 9        | **容错恢复与状态诊断** (Error Recovery & Help)         |   **2**    | 清理后若出现释放失败或用户误点，无任何恢复途径；PWA 弹窗被系统或用户取消后静默吞没，按钮突兀消失无反馈                             |
| 10       | **帮助与说明文档** (Help & Documentation)              |   **3**    | 「安全边界提示」明确声明不影响服务端书库，值得称赞；但未对「重置离线环境」的破坏后果给出任何上下文阐释                             |
| **总分** | **Total Health Score**                                 | **26/40**  | **Acceptable (可接受 · 65%)** — 骨架扎实，但存在显著交互与状态防线缺陷                                                             |

---

### 2. Priority Issues 归档与修复实施

1. **🔴 P1 Toast 数值归零竞态**：清理完成后直接透传 `freedBytes` 通过 `formatBytes(freedBytes)` 渲染 Toast，彻底杜绝已刷新为 0 的空值展示。
2. **🔴 P1 高危破坏操作无防线**：为「重置全部离线环境」构建两步交互防线（`isConfirmingReset` + 5s 自动超时回滚 + 独立取消按钮），触控热区垫高至 38px。
3. **🔴 P1 浮层指示箭头脱靶**：在 `AppPopover.vue` 中为 `.align-end::before` 与 `.align-center::before` 补齐正确的相对偏移样式。
4. **🟡 P2 顶栏语义防歧义**：Badge 标识由混淆的「离线 12.4 MB」优化为「设备 12.4 MB」（0 占用时为「设备就绪」）。
5. **🟡 P2 剔除常驻红点**：移除触发表面的朱砂红点，消除通知焦虑，安装入口纯净收敛于面板顶栏。
6. **🟡 P2 3px 平直标尺与 Workbox 真实规则**：修正刻度轨为 3px 纸印圆角，文案修正为真实规则「保留最新 1000 页面」。
