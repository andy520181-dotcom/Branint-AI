# Trout 品牌战略 Agent — 完整工作流程图

> 文档版本：v1.0 · 2026-04-04  
> 系统：Branin AI · Backend  
> 核心文件：`strategy_agent.py` + `trout_skills.py` + `agents/strategy.md`

---

## 一、总览：Trout 在整体系统中的位置

```
用户输入
   │
   ▼
┌──────────────────────────────────────────────────────┐
│              AgentOrchestrator（编排器）                │
│                                                      │
│  品牌顾问 Ogilvy（需求分析 + 路由决策）                   │
│       │  generate_workflow_dag                       │
│       ▼                                              │
│  路由序列（selected_agents）                            │
│  例：["market", "strategy", "content", "visual"]     │
│       │                                              │
│       ├──→ Wacksman（市场研究 Agent）                  │
│       │         └── handoff 交接摘要                  │
│       │                    │                         │
│       ├──────────────────→ Trout（品牌战略 Agent）◄───┤
│       │         └── handoff 交接摘要                  │
│       │                    │                         │
│       ├──────────────────→ Lois（内容策划 Agent）     │
│       │                    │                         │
│       └──────────────────→ Scher（视觉设计 Agent）    │
│                                                      │
│  品牌顾问 Ogilvy（质量审核 + 最终综合报告）                │
└──────────────────────────────────────────────────────┘
   │
   ▼
SSE 流式推送至前端
```

**Trout 的上游输入**：Wacksman 市场研究 Agent 的 `<handoff>` 交接摘要  
**Trout 的下游输出**：品牌战略 Markdown 报告 + `<handoff>` 标签（供 Lois / Scher 读取）

---

## 二、Trout Agent 内部工作阶段一览

| 阶段 | 名称 | 执行方式 |
|------|------|---------|
| Phase 0 | 输入组装 | Python 层构建初始消息 |
| Phase 1 · Round 0 | 元路由：场景识别与框架预选 | LLM 工具调用 |
| Phase 1 · Round 1~N | 逐步执行品牌框架工具 | LLM 工具调用循环 |
| Phase 1 · 最终轮 | 触发报告合成信号 | LLM 调用 synthesize_strategy_report |
| Phase 2 | 流式生成完整 Markdown 报告 | LLM 流式输出（call_llm_stream） |

---

## 三、完整流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                    TROUT AGENT 入口                              │
│   run_strategy_agent_stream(user_prompt, handoff_context)        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   【Phase 0】输入组装                             │
│                                                                 │
│  • 加载 system prompt（agents/strategy.md）                      │
│  • 构建 user 消息：                                              │
│      "品牌需求：{user_prompt}"                                    │
│      + Wacksman handoff 交接摘要（若有）                          │
│      + "【第一步必须】请调用 select_applicable_frameworks..."      │
│  • 初始化 messages 列表                                          │
│  • 初始化 framework_plan=[] / executed_frameworks=[]             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│             【Phase 1】工具调用循环（最多 10 轮）                  │
│                                                                 │
│   for round_idx in range(1, MAX_TOOL_ROUNDS + 1):               │
│                                                                 │
│        call_llm_with_tools(messages, TROUT_TOOLS)               │
│                                                                 │
│                    ┌─────────────────┐                          │
│                    │   LLM 返回响应   │                          │
│                    └─────────────────┘                          │
│                           │                                     │
│           ┌───────────────┼───────────────┐                     │
│           ▼               ▼               ▼                     │
│      有 tool_calls    直接返回文本      空响应                    │
│           │               │               │                     │
│           │             break          break（异常）             │
│           ▼                                                     │
│      解析工具调用（parse_trout_tool_calls）                       │
│           │                                                     │
│      按工具名路由执行（execute_trout_tool）                        │
│           │                                                     │
│  ┌────────┴──────────────────────────────────────────────┐     │
│  │                  工具执行路径                            │     │
│  │                                                       │     │
│  │  [0] select_applicable_frameworks  ← 必须第一步         │     │
│  │      execute_select_frameworks(args)                   │     │
│  │      → 提取 framework_plan（顺序列表）                  │     │
│  │      → 强制校验：定位+品牌屋+原型 不可缺席                │     │
│  │      → 返回 framework_sequence + 执行指令                │     │
│  │                                                       │     │
│  │  [1] apply_positioning_framework   ← 核心必选           │     │
│  │      execute_positioning_framework(args)               │     │
│  │      → 生成 Positioning Statement + 竞争坐标轴文档       │     │
│  │                                                       │     │
│  │  [2] build_brand_house             ← 核心必选           │     │
│  │      execute_brand_house(args)                         │     │
│  │      → 生成品牌屋（承诺/三支柱/MVV/调性指南）             │     │
│  │                                                       │     │
│  │  [3] design_brand_architecture     ← 可选              │     │
│  │      execute_brand_architecture(args)                  │     │
│  │      → 输出架构模型推荐 + 层级结构图                     │     │
│  │                                                       │     │
│  │  [4] apply_brand_archetypes        ← 核心必选           │     │
│  │      execute_brand_archetypes(args)                    │     │
│  │      → 输出 Jung原型 + Aaker五维度 + 黄金圈              │     │
│  │                                                       │     │
│  │  [5] generate_naming_candidates    ← 可选              │     │
│  │      execute_naming_candidates(args)                   │     │
│  │      → 输出 3-5 个候选品牌名 + 首选推荐                  │     │
│  │                                                       │     │
│  │  [6] synthesize_strategy_report    ← 必须最后一步        │     │
│  │      execute_synthesize_report(args)                   │     │
│  │      → 返回报告触发信号（不生成报告正文）                  │     │
│  │      → synthesis_triggered=True → break                │     │
│  └───────────────────────────────────────────────────────┘     │
│           │                                                     │
│      将工具结果追加到 messages（role: tool）                       │
│           │                                                     │
│      framework_plan 已确定？→ 注入进度提示到 messages             │
│      "[执行进度] 已完成: X | 下一步: Y | 剩余: Z"               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│            【Phase 2】流式生成完整品牌战略报告                      │
│                                                                 │
│  构建报告指令消息（仅包含本次实际执行的章节）                         │
│                                                                 │
│  章节映射：                                                       │
│    apply_positioning_framework → ① 品牌定位                     │
│    build_brand_house           → ② 品牌屋                       │
│    design_brand_architecture   → ③ 品牌架构（如选用）             │
│    apply_brand_archetypes      → ④ 品牌个性系统                 │
│    generate_naming_candidates  → ⑤ 命名方案（如选用）             │
│    始终附加                    → ⑥ 战略落地优先级建议              │
│                                                                 │
│  call_llm_stream(messages)                                      │
│    → async for chunk → yield chunk（SSE 流式推送）               │
│                                                                 │
│  报告标准结构：                                                   │
│    # 品牌战略报告                                                 │
│    ## 战略执行摘要（3-5条，执行层可直接使用）                       │
│    ## 一、品牌定位（定位语 / 竞争坐标图 / USP）                    │
│    ## 二、品牌屋（承诺 / 三支柱 / MVV / 调性指南）                 │
│    ## 三、品牌架构（模型推荐 + 层级结构，如适用）                   │
│    ## 四、品牌个性系统（Jung原型 / Aaker五维度 / 黄金圈）           │
│    ## 五、命名建议（候选名 + 首选推荐，如适用）                     │
│    ## 六、战略落地优先级建议                                       │
│    <handoff>...</handoff>                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
            输出完成 → handoff 被提取
            存入 project_context["handoffs"]["strategy"]
            供下游 Lois / Scher 读取
```

---

## 四、工具详解

### 工具 0：`select_applicable_frameworks`（元路由，必须第一步）

**功能**：智能分析用户场景，决定本次执行哪些框架

**场景类型枚举与推荐框架**：

| 枚举值 | 中文含义 | 推荐框架组合 |
|--------|---------|------------|
| `new_brand_startup` | 零基础新品牌 | 定位 + 品牌屋 + 架构 + 原型 + 命名（全套） |
| `brand_repositioning` | 成熟品牌再定位 | 定位 + 品牌屋 + 原型（核心三件套） |
| `brand_architecture_design` | 多品牌架构整合 | 定位 + 品牌屋 + 架构（重点）+ 原型 |
| `brand_identity_refresh` | 品牌调性/个性升级 | 定位 + 品牌屋 + 原型（重点） |
| `naming_focused` | 命名专项 | 定位 + 品牌屋 + 原型 + 命名（重点） |
| `comprehensive_strategy` | 综合品牌战略分析 | 全套或按需，核心三件套必选 |

**Python 层强制保障机制**（即使 LLM 漏选也会自动补充）：
- `apply_positioning_framework` — 定位是一切战略的基石
- `build_brand_house` — 品牌屋定义品牌存在的意义与对外承诺
- `apply_brand_archetypes` — 原型系统为内容和视觉提供个性方向

---

### 工具 1：`apply_positioning_framework`（核心必选）

**功能**：Jack Trout 定位理论 + 竞争坐标轴分析

| 参数 | 说明 |
|------|------|
| `brand_name` | 品牌名（或项目代号） |
| `target_audience` | 目标人群（人口统计 + 心理特征） |
| `category` | 品牌所在品类/参考框架 |
| `core_benefit` | 核心利益（功能利益 + 情感利益） |
| `competitive_differentiator` | 差异化支撑点（RTB: Reason to Believe） |
| `key_competitors` | 2-4 个主要竞品品牌 |
| `positioning_axis_x` | 竞争坐标 X 轴维度 |
| `positioning_axis_y` | 竞争坐标 Y 轴维度 |

**输出**：标准 Positioning Statement + 竞争坐标图位置说明

---

### 工具 2：`build_brand_house`（核心必选）

**功能**：基于 Unilever 品牌屋模型，构建品牌战略核心文档

| 参数 | 说明 |
|------|------|
| `brand_promise` | 品牌承诺（屋顶，一句话统领） |
| `brand_pillars` | 三大品牌支柱（名称 + 含义 + 2-3条证明点） |
| `mission` | 品牌使命（解决什么问题） |
| `vision` | 品牌愿景（5-10年目标） |
| `values` | 品牌价值观（3-5条） |
| `brand_personality_keywords` | 品牌个性关键词（5个形容词） |
| `tonality_guide` | 品牌语气指南（是什么 / 绝对不是什么） |

---

### 工具 3：`design_brand_architecture`（可选）

**功能**：推荐最合适的品牌架构模型（仅在有多产品线/子品牌需求时选用）

| 模型 | 代表品牌 | 特点 |
|------|---------|------|
| Branded House（统一品牌） | Google、Apple | 规模效益高，认知统一 |
| House of Brands（多品牌矩阵） | P&G、联合利华 | 独立品牌，精准定位不同人群 |
| Endorsed Brand（背书品牌） | 万豪旗下各酒店 | 主品牌背书，子品牌独立运营 |
| Hybrid/Sub-brand（混合子品牌） | 三星、宝马 | 双层结构，灵活延伸 |

---

### 工具 4：`apply_brand_archetypes`（核心必选）

**功能**：Jung 12原型 + Aaker 五维度 + 黄金圈，建立品牌个性系统

**Jung 12原型**：

| 原型 | 中文 | 代表品牌 | 核心特质 |
|------|------|---------|---------|
| innocent | 纯真者 | 可口可乐 | 乐观、纯粹、美好 |
| everyman | 凡人/邻家好友 | IKEA | 亲切、包容、踏实 |
| hero | 英雄 | Nike | 激励、勇气、挑战极限 |
| outlaw | 颠覆者 | Harley-Davidson | 反叛、自由、打破规则 |
| explorer | 探险家 | Jeep | 冒险、发现、自由精神 |
| creator | 创造者 | 乐高 | 想象力、创新、自我表达 |
| ruler | 权威统治者 | Mercedes-Benz | 秩序、掌控、权威 |
| magician | 魔法师 | Apple | 变革、愿景、转化现实 |
| lover | 情人 | Chanel | 诱惑、热情、深度连接 |
| caregiver | 照顾者 | 强生 | 关爱、保护、养育 |
| jester | 弄臣 | 老干妈 | 幽默、轻松、反差萌 |
| sage | 智者 | Google | 知识、洞察、追求真理 |

**Aaker 五维度评分（1-10分）**：真诚度 / 激情度 / 能力感 / 精致感 / 粗犷感

**黄金圈（Golden Circle）**：WHY（品牌信念）→ HOW（核心方法论）→ WHAT（产品/服务）

---

### 工具 5：`generate_naming_candidates`（可选）

**功能**：生成 3-5 个候选品牌命名方案 + 商标可注册性初评

| 命名类型 | 说明 |
|---------|------|
| 描述型（descriptive） | 直接表达品类/功能，认知成本低 |
| 联想型（associative） | 隐喻/类比建立联想，兼顾记忆点 |
| 抽象型（abstract） | 自造词/谐音，独创性强，保护性高 |
| 混合型（mixed） | 综合多种策略，灵活均衡 |

**每个候选名评估维度**：品牌契合度（1-10分）/ 国际化适用性 / 商标注册风险 / 域名可用性

---

### 工具 6：`synthesize_strategy_report`（必须最后调用）

**功能**：触发器——通知系统所有框架完成，准备进入 Phase 2 报告生成

| 参数 | 说明 |
|------|------|
| `positioning_summary` | 一句话总结品牌定位核心 |
| `brand_promise_summary` | 品牌承诺一句话 |
| `key_strategic_decisions` | 3-5 个关键战略决策点 |
| `recommended_next_steps` | 2-3 条战略落地优先行动建议 |

---

## 五、状态机与循环控制

```
Phase 1 循环状态机（MAX_TOOL_ROUNDS = 10）

Round 1:  select_applicable_frameworks
          → 确定 framework_plan 序列

Round 2:  apply_positioning_framework
          → 工具结果追加 messages
          → 注入进度提示："下一步: build_brand_house"

Round 3:  build_brand_house
          → 工具结果追加 messages
          → 注入进度提示

Round 4:  design_brand_architecture（如在 framework_plan 中）

Round 5:  apply_brand_archetypes

Round 6:  generate_naming_candidates（如在 framework_plan 中）

Round N:  synthesize_strategy_report
          → synthesis_triggered = True → break → 进入 Phase 2

─────────────────────────────────────────────
异常退出条件：
  ① LLM 直接返回文本（无工具调用）→ break → 进入 Phase 2
  ② LLM 返回空响应 → Warning 日志 → break
  ③ 达到 MAX_TOOL_ROUNDS（10轮）→ 强制退出
─────────────────────────────────────────────
```

---

## 六、Handoff 数据格式

```
<handoff>
品牌定位语：[完整 Positioning Statement]
核心 USP：[一句话差异化主张]
品牌承诺：[Brand Promise]
品牌个性关键词：[5个关键词，逗号分隔]
Jung 主原型：[原型名称]
黄金圈WHY：[品牌信念一句话]
目标人群：[精准描述]
推荐品牌名：[首选名称]（如有命名任务）
战略基调：[为内容和视觉设计的一句话方向指引]
</handoff>
```

**提取机制（含降级保障）**：
- 标签存在 → 精确提取 `<handoff>...</handoff>` 内容
- 标签缺失 → 截取输出末尾 500 字作为兜底（并记录 Warning）

---

## 七、SSE 事件流（前端接收顺序）

```
event: agent_start       data: "strategy"

【Phase 1 在后端静默执行，无 SSE 推送】

【Phase 2 开始流式推送】

event: agent_chunk       data: {"id": "strategy", "chunk": "# 品牌战略报告\n"}
event: agent_chunk       data: {"id": "strategy", "chunk": "..."}
...（持续 token 流式推送）

event: agent_output      data: {"id": "strategy", "content": "（完整报告全文）"}
event: agent_complete    data: "strategy"
```

---

## 八、关键设计原则

| 原则 | 说明 |
|------|------|
| **元路由优先** | 第一轮必须调用 `select_applicable_frameworks`，system prompt 强制要求 |
| **最低框架保证** | Python 层强制校验：核心三件套（定位+品牌屋+原型）不可缺席，LLM 漏选自动补充 |
| **动态框架序列** | 不跑全量 6 个框架，LLM 根据场景智能选取 3-5 个，降低无效分析耗时 |
| **进度提示注入** | 每轮工具结果后，Python 层主动注入「当前进度 + 下一步」提示，防止 LLM 遗漏或乱序 |
| **流式报告分离** | Phase 1（工具调用，非流式）和 Phase 2（报告生成，流式）完全解耦 |
| **章节按需生成** | 只报告实际执行的框架章节，跳过的框架不出现在报告里 |
| **Handoff 标准化** | 输出末尾必须有 `<handoff>` 标签，编排器精确提取供下游 Agent 注入 |

---

## 九、文件索引

| 文件路径 | 职责 |
|---------|------|
| `backend/agents/strategy.md` | Trout 的 system prompt（角色定义 / 工作流程 / 报告格式规范） |
| `backend/agents/_shared_rules.md` | 所有 Agent 共享的输出铁律（格式/handoff规范） |
| `backend/app/service/strategy_agent.py` | Trout Agent 主逻辑（Phase 1 循环 + Phase 2 流式输出） |
| `backend/app/service/skills/trout_skills.py` | 全部 7 个工具的 JSON Schema + 执行函数 + 统一调度分发器 |
| `backend/app/service/agent_orchestrator.py` | 全局编排器（路由决策 / handoff 提取 / SSE 事件推送） |

---

*生成时间：2026-04-04 · Branin AI 内部工程文档*
