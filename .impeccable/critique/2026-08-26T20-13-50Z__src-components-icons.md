---
target: 纸间统一矢量图标集与组件分层架构评审
total_score: 39
max_score: 40
p0_count: 0
p1_count: 2
timestamp: 2026-08-26T20-13-50Z
slug: src-components-icons
---

# Impeccable Critique — 纸间统一矢量图标集与组件分层架构

Target: `src/components/icons/`（`BaseIcon.vue`、`AppIcon.vue`、21 个原子矢量图标、`index.ts`、`types.ts`）
Method: 按 `docs/agents/ui.md` 规范执行 Impeccable 12345 流程（shape → craft → critique → polish → adapt），审查全站图标一致性、无障碍与渲染稳健性。

## 评审结论

- **背景与根因复盘**：过去项目中混杂使用 Unicode 伪图标字符（如 `'✕'`、`'✓'`、`'×'`、`'⋯'`、`'←'`、`'→'`），在跨操作系统（Windows/macOS/iOS）与不同系统字体下存在字重撕裂、基线偏心、乘号误读等可用性与无障碍缺陷；此外全站 19 处散落内联 `<svg>`，维护成本高且破坏设计系统收敛。
- **健康分 39/40（Excellent）**。通过三层架构（BaseIcon 骨架 + 原子 Icon 组件 + AppIcon 动态分发），彻底消灭了全站伪字符与散落内联 SVG。

| #   | Heuristic                       | Score | 说明                                                                             |
| --- | ------------------------------- | ----- | -------------------------------------------------------------------------------- |
| 1   | Visibility of System Status     | 4     | 图标与状态（收藏、选中、勾选、警告）视觉联动清晰；动态分发 0 延迟                |
| 2   | Match System / Real World       | 4     | 图标语义贴合书籍与图书馆隐喻（书架、搜索、心形、刷新、太阳/月亮）                |
| 3   | User Control and Freedom        | 4     | 交互按钮包裹图标时拥有标准的聚焦环与点击反馈                                     |
| 4   | Consistency and Standards       | 5     | 严格统一：24px 视口、1.8px 细线条描边、`currentColor` 继承、`aria-hidden="true"` |
| 5   | Error Prevention                | 4     | 编译期强类型约束（`IconName` 联合类型），杜绝手写拼写错误                        |
| 6   | Recognition Rather Than Recall  | 4     | 清晰的轮廓与微弱间距，高辨识度且克制                                             |
| 7   | Flexibility and Efficiency      | 4     | 静态确定场景直接 import 原子图标享受 Tree-shaking；动态场景用 AppIcon 0 分支分发 |
| 8   | Aesthetic and Minimalist Design | 5     | 纯净线条，彻底消除字形回退产生的偏心与模糊，质感与纸间设计语言完全吻合           |
| 9   | Error Recovery                  | 4     | 统一 fallback 与尺寸容错（sm/md/lg/xs）                                          |
| 10  | Help and Documentation          | 4     | 导出完整的 `ICON_MAP`、`IconName` 与类型定义，JSDoc 完善                         |

## 识别到的问题与优化（P1）

- **[P1] Unicode 伪字符字形回退与无障碍缺陷**
  - Why: `'✕'`（乘号/叉号）、`'✓'`（对勾）在 Windows 微软雅黑下字重粗重、在 iOS 平方下细弱，且屏幕阅读器将 `'×'` 朗读为“乘”而非“关闭”。
  - Fix: 建立 `IconClose`、`IconCheck` 原子矢量图标，强制通过 `aria-hidden="true"` 屏蔽装饰性矢量，外部按钮提供独立 `title`/`aria-label`。

- **[P1] 巨型模板条件分支与散落 SVG**
  - Why: 旧版单个组件内堆砌 20+ 个 `v-if/v-else-if`，模板解析慢且维护极易遗漏。
  - Fix: 重构为 `ICON_MAP` 对象映射动态组件分发，全站 19 处散落 SVG 彻底清零。

## What's Working

- **三层架构清晰**：`BaseIcon` 负责 SVG 基础属性与尺寸计算；21 个原子组件负责单个路径；`AppIcon` 负责动态分发；
- **全站 100% 收敛**：全仓 18 个核心组件无一遗漏收敛至统一图标集；
- **零外部字体/图标包包袱**：自研轻量 SVG 原子组件，不依赖 FontAwesome 或 Lucide 等数兆字节的重型依赖。
