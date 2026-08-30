---
timestamp: 2026-08-30T09-27-48Z
slug: guest-modal-devices
---

# Impeccable Design Critique: GuestModal.vue (访客通行证唯一使用与设备流转管理)

**Target**: `src/components/curator/GuestModal.vue`
**Evaluator**: Design Director (Subagent Assessment A) + Deterministic Slop Detector (Assessment B)
**Date**: 2026-08-30

---

## 1. Executive Summary & Scores

- **Initial Nielsen Heuristics Score**: 24/40 (Acceptable)
- **Post-Polish Nielsen Heuristics Score**: 38/40 (Superior)
- **Deterministic Slop Findings (Assessment B)**: 0 issues (`[]`)
- **Key Polish Interventions**:
  1. **[P1-1] 触控命中区超标与单设备踢除缺乏二次确认防误触**: 设备踢除增补内联轻量确认（点击后在芯片内部切换为“下线？”、“踢出”与“取消”），彻底杜绝移动单手滑动误踢；通过伪元素为 `device-kick-btn` 与 `quota-step-btn` 扩充 36~40px 触控热区，补齐 `:aria-label`。
  2. **[P1-2] 违反 Unified Iconography 规范与 WAI-ARIA 伪模式**: 扩充 `IconMinus.vue`，彻底剔除硬编码 Unicode 伪字符（`−` / `＋`），全面收敛至 `<AppIcon name="minus" />` / `<AppIcon name="plus" />`；筛选胶囊收敛至 `role="radiogroup"` / `role="radio"`；席位微调器补充 `role="spinbutton"` 完整无障碍元数据。
  3. **[P1-3] 单卡片认知过载与移动端折行挤压**: 移动端断点优化为弹性多行自适应排版，防止内联确认展开时横向撑爆挤出；在名册头部增补即时轻量模糊搜索框，大名单秒级定位。
  4. **[P2-1] 典藏印章意象漂移与硬编码阴影**: 满额（`full`）印章改用 `--warning` 琥珀色古铜印，解除误导性错误恐慌；停用印章移除现代横划删除线，回归古籍淡墨作废印；硬编码 `rgba(0,0,0,0.04/0.05)` 阴影全量收敛至 `var(--shadow-1)`。
  5. **[P2-2] 席位调节冗余全量 Fetch**: 移除 `useGuestPasses.ts` 中 `updateMaxDevices` 的二次冗余全量请求，实现就地纯响应式更新。

---

## 2. Nielsen 10 Heuristics Assessment

| #        | 启发式可用性维度                                   | 初评 (0-4) | 复评 (0-4) | 改善与闭环状态                                                                      |
| -------- | -------------------------------------------------- | :--------: | :--------: | ----------------------------------------------------------------------------------- |
| 1        | 系统状态可见度 (Visibility of System Status)       |     3      |     4      | 四态印章语义精准分明，复制带有 1.5s 绿色原位微反馈，防重分发告警及时。              |
| 2        | 系统隐喻与现实匹配 (Match System & Real World)     |     2      |     4      | 借书名册与凭据卡质感纯正，满额采用琥珀印、作废采用淡墨印，消除现代删除线。          |
| 3        | 用户控制度与自由度 (User Control & Freedom)        |     2      |     4      | 设备踢除增加防误触二次确认与取消通道，席位调节就地生效。                            |
| 4        | 一致性与行业标准 (Consistency & Standards)         |     2      |     4      | 零伪字符，补齐 IconMinus 统一矢量图标库；无障碍 radiogroup 与 spinbutton 全量合规。 |
| 5        | 防错机制 (Error Prevention)                        |     2      |     4      | 扩展触控命中区至 36~40px，踢除动作双重确认，已有设备通行证复制时弹出防挤下线警告。  |
| 6        | 识别而非回忆 (Recognition Rather Than Recall)      |     3      |     4      | 引入名册实时模糊搜索框，分类胶囊附带数量指示，设备活跃时间与 IP 就地呈现。          |
| 7        | 灵活性与使用效率 (Flexibility & Efficiency)        |     2      |     4      | 消除冗余网络请求，支持席位连续调整与秒级筛选。                                      |
| 8        | 美学与极简主义设计 (Aesthetic & Minimalist Design) |     2      |     3      | 阴影收敛至设计变量，移动端断点排版弹性折行，层次清晰。                              |
| 9        | 容错恢复与状态诊断 (Error Recovery & Help)         |     3      |     4      | 接口失败具备就地重试与友好提示。                                                    |
| 10       | 帮助与说明文档 (Help & Documentation)              |     3      |     4      | LRU 置换机制与设备上限配额清晰标注，Tooltip 隔离说明到位。                          |
| **总分** | **Total Health Score**                             | **24/40**  | **38/40**  | **Superior (卓越 · 95%)**                                                           |

---

## 3. Cognitive Load Assessment

- **Single Focus**: 现存名册卡片按照“身份/印章” -> “高频复制直达” -> “物理设备托盘” -> “底栏席位与运维”清晰纵向展开。
- **Chunking & Grouping**: 设备抽屉与名册底栏通过物理纸色色块（`--paper-1`）与细线（`--line`）严格分隔。
- **Progressive Disclosure**: 危险操作（重置密钥、彻底注销、单端踢除）均通过内联微确认折叠隐藏，未触发时视觉纯净。
- **Decision Friction**: 筛选胶囊（待激活/使用中/已满额/已失效）让馆长无需遍历卡片即可直奔未赠出卡片，决策摩擦降至最低。

---

## 4. Verification

- `vp test src/__tests__/GuestPasses.spec.ts`: 6/6 passed (100%)
- `pnpm detect:slop src/components/curator/GuestModal.vue`: 0 findings (`[]`)
- `vp check`: 0 warnings, 0 lint errors, 0 type errors; 193 files formatted
- `pnpm test:py`: All backend tests passed, 0 syntax/import errors
