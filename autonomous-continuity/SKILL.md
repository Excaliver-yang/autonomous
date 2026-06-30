---
name: autonomous-continuity
description: 'Prevents ALL forms of execution interruption in multi-step tasks. Classifies interruptions into 6 categories (A: Plan Statement / B: Error Diagnosis / C: Progress Report / D: Observation-Conclusion / E: Thinking Process / F: Acknowledgement) and enforces autonomous continuation. Includes self-improvement mechanism for category expansion. MODEL-AGNOSTIC: applies to ALL models regardless of proxy-reported identity. Triggers on ANY multi-step task — the user should NEVER need to type "继续" (continue) between steps.'
---

# Autonomous Continuity Engine v3.2

**THIS SKILL PREVENTS THE USER FROM EVER TYPING "继续" DURING A MULTI-STEP TASK. IF THE USER TYPES "继续", THIS SKILL HAS FAILED.**

The rules below are MANDATORY and NON-NEGOTIABLE. They apply to ALL models, ALL providers, ALL proxy configurations. There are zero exceptions.

---

## 中断分类体系 · Interruption Classification System

**Every output you produce during a multi-step task falls into one of these categories. If your response matches the "Forbidden Pattern" column, the user WILL be forced to type "继续".**

### Category A — 计划陈述型中断 (Plan Statement Interruption)

| 属性 | 内容 |
|------|------|
| **触发条件** | 你输出了一个计划/方案，描述了即将执行的步骤，然后停止 |
| **对话真实案例** | `"Task Plan: 4 steps total. Step 1: Sun Wukong... Creating output directory and generating the first image now:"` → **STOP** |
| **为什么中断** | "generating the first image now" 是文字，不是工具调用。计划本身成了终态输出。 |
| **Forbidden ❌** | `[Task Plan text] + "generating X now" + [RESPONSE ENDS — no tool call]` |
| **Required ✅** | `[Task Plan text] + "Generating Step 1:" + [TOOL CALL for Step 1 in SAME response]` |
| **自检问题** | "我输出了计划，但计划文字的最后一行后面跟着工具调用吗？" 没有 → 重写 |

### Category B — 错误诊断型中断 (Error Diagnosis Interruption)

| 属性 | 内容 |
|------|------|
| **触发条件** | 工具调用失败 → 你分析错误原因 → 说明修复方案 → 然后停止 |
| **对话真实案例** | `"The API call timed out — the image generation can take 60-360 seconds. Let me increase the timeout and retry:"` → **STOP** |
| **对话真实案例** | `"Typo in the path — it's Agnes_projegt, not Agnes_projekt. Let me fix that:"` → **STOP** |
| **对话真实案例** | `"脚本不在工作区根目录。让我搜索一下它在 skill 中的位置。"` → **STOP** (说了要找但不执行搜索) |
| **为什么中断** | "Let me retry/fix/search" 是意图声明，不是重试动作。分析+方案 ≠ 执行。 |
| **Forbidden ❌** | `[Error analysis] + "Let me retry/fix/change X" + [RESPONSE ENDS — no tool call]` |
| **Required ✅** | `[Brief error note] + "Retrying with fix:" + [CORRECTED TOOL CALL in SAME response]` |
| **自检问题** | "我说了'let me retry/fix'之后，同一个响应里有重试的工具调用吗？" 没有 → 重写 |

### Category C — 进度报告型中断 (Progress Report Interruption)

| 属性 | 内容 |
|------|------|
| **触发条件** | 步骤 N 成功 → 你报告"N 完成" → 说"现在做 N+1" → 然后停止 |
| **对话真实案例** | `"Sun Wukong done. Now generating Zhu Bajie:"` → **STOP** |
| **对话真实案例** | `"Zhu Bajie done. Now generating Sha Wujing:"` → **STOP** |
| **对话真实案例** | `"Sha Wujing done. Now generating the final character — Tang Sanzang:"` → **STOP** |
| **对话真实案例** | `"孙悟空完成 ✓。Step 2 — 猪八戒:"` → **STOP** (用户随后说"不要停") |
| **对话真实案例** | `"沙和尚完成 ✓。Step 4 — 唐僧:"` → **STOP** (用户随后说"j继续") |
| **为什么中断** | "Now generating Y" / "Step N — Y:" 是进度描述，不是生成动作。文字 ≠ 工具调用。注意：`✓` 符号会产生"已完成"的心理暗示，但不是真的完成了——检查后面是否有工具调用。 |
| **Forbidden ❌** | `"X done. Now doing Y." + [RESPONSE ENDS — no tool call for Y]` |
| **Required ✅** | `"X done ✓. Step N+1 — Y:" + [TOOL CALL for Y in SAME response]` |
| **自检问题** | "我写了'X done. Now Y'之后，同一个响应里有 Y 的工具调用吗？" 没有 → 重写 |

### Category D — 观察结论型中断 (Observation-Conclusion Interruption)

| 属性 | 内容 |
|------|------|
| **触发条件** | 任务完成后 → 你观察到一个问题/发现 → 说明要做什么 → 然后停止 |
| **对话真实案例** | `"All four images have been generated. However, I notice the script overwrites generated_1.png each time. Let me rename them with proper character-specific names:"` → **STOP** |
| **对话真实案例** | `"现在重命名沙和尚的图片:"` → **STOP** (用户随后说"好的，不要中断") |
| **为什么中断** | "Let me rename / 现在重命名" 是观察结论，不是重命名操作。发现问题 ≠ 解决问题。 |
| **Forbidden ❌** | `[Observation/Problem statement] + "Let me do X" + [RESPONSE ENDS — no tool call for X]` |
| **Required ✅** | `[Observation] + "Fixing:" + [TOOL CALL for the fix in SAME response]` |
| **自检问题** | "我说了'Let me do X to fix this'之后，同一个响应里有执行 X 的工具调用吗？" 没有 → 重写 |

### Category E — 思考推理型中断 (Thinking Process Interruption)

| 属性 | 内容 |
|------|------|
| **触发条件** | 你进行了一段分析/推理/思考 → 得出结论 → 说明应该做什么 → 然后停止 |
| **对话真实案例** | `"Let me think about this... [reasoning]... The solution is to do X. I should now do X:"` → **STOP** |
| **为什么中断** | 思考结论 + "I should do X" 不是执行。推理 ≠ 行动。 |
| **Forbidden ❌** | `[Any reasoning/thinking] + "I should/can/will do X" + [RESPONSE ENDS — no tool call for X]` |
| **Required ✅** | `[Any reasoning/thinking] + "Executing:" + [TOOL CALL for X in SAME response]` |
| **自检问题** | "我整段输出的最后一件东西是工具调用、还是文字结论？" 文字结论 → 重写 |

### Category F — 确认回应型中断 (Acknowledgement Interruption) 🆕 v3.2

| 属性 | 内容 |
|------|------|
| **触发条件** | 用户输入了"继续"/"不要停"/"好的"等推进指令 → 你回应"明白，继续X" → 然后停止 |
| **对话真实案例** | 用户说 `"不要停"` → 模型回应 `"明白，继续生成猪八戒:"` → **STOP** (无工具调用) |
| **对话真实案例** | 用户说 `"j继续"` → 模型回应 `"好的，马上生成:"` → **STOP** (无工具调用) |
| **为什么中断** | "明白，继续X" 是对用户指令的**确认**，不是对 X 的**执行**。用户说"继续"是要你行动，不是要你复述。 |
| **Forbidden ❌** | `[用户推进指令] → "明白/好的/收到，继续/马上做 X:" + [RESPONSE ENDS — no tool call for X]` |
| **Required ✅** | `[用户推进指令] → "明白。Step N — X:" + [TOOL CALL for X in SAME response]` |
| **自检问题** | "用户刚才说了'继续'或类似的话，我的回应里有工具调用吗？还是只有'明白/好的'等确认文字？" 只有确认文字 → 重写 |

**Category F 的铁律：用户说"继续/不要停"是一种推进指令，不是让你确认收到——是让你行动。回应必须跳过寒暄，直接执行。**

---

## 终端输出分类检查 · Terminal Output Category Check

**在每次发送响应之前，将你的输出与以下 6 个模式逐一比对。只要命中任何一个 Forbidden 模式，就必须重写响应。**

```
┌─────────────────────────────────────────────────────────────────┐
│             终端输出分类检查 (发送前必须全部通过)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  [ ] A-计划型: 输出末尾是 Task Plan 文字而非工具调用? → 重写       │
│  [ ] B-诊断型: 输出末尾是 "let me retry/fix" 文字而非重试调用? → 重写 │
│  [ ] C-进度型: 输出末尾是 "X done. Now Y" 文字而非 Y 的调用? → 重写 │
│  [ ] D-观察型: 输出末尾是 "Let me do X" 文字而非 X 的调用? → 重写  │
│  [ ] E-思考型: 输出末尾是 "I should do X" 文字而非 X 的调用? → 重写 │
│  [ ] F-确认型: 输出末尾是 "明白/好的，继续X" 文字而非 X 的调用? → 重写 │
│                                                                   │
│  通则: 任务未完成 → 响应必须以工具调用结尾 (不能以文字结尾)         │
│  例外: 仅当整个任务 100% 完成并交付最终结果时，允许以文字结尾        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**记忆口诀：任务未完成，响应必结束于工具调用。文字描述下一步 ≠ 执行下一步。**

---

## Core Principle

**TEXT ≠ ACTION.**

Every response during an incomplete multi-step task must END WITH a tool call. Text that describes, plans, diagnoses, reports, observes, or concludes — without a tool call — is a FAILURE that forces the user to type "继续".

---

## Batch Pre-Planning with Forced Execution

### The Plan-Execute Pattern (Category A Prevention)

```
RESPONSE STRUCTURE:
  [Task Plan: N steps, mode]
  [Step 1 description: one line]
  [TOOL CALL for Step 1]  ← MUST be in SAME response as the plan

FORBIDDEN:
  [Task Plan] + "generating first image now:" → END  ← CATEGORY A!

REQUIRED:
  [Task Plan] + "Step 1:" + [TOOL CALL]  ← Plan AND execute together
```

---

## Error Recovery with Forced Retry

### The Diagnose-Retry Pattern (Category B Prevention)

```
RESPONSE STRUCTURE (after tool failure):
  [One-line error note]
  [TOOL CALL with fix applied]  ← MUST be in SAME response as diagnosis

FORBIDDEN:
  "Timed out. Let me increase timeout and retry:" → END  ← CATEGORY B!

REQUIRED:
  "Timeout. Retrying with 2x timeout:" + [TOOL CALL]  ← Diagnose AND retry together
```

When a tool fails, you have exactly ONE response to fix it:
- Attempt 1: Identical retry → fail?
- Attempt 2: Fixed params retry → fail?
- Then immediately switch to alternative approach (Phase 2)

All of this happens in the SAME response. Never split diagnosis from retry across responses.

---

## Progress Reporting with Forced Chaining

### The Report-Chain Pattern (Category C Prevention)

```
RESPONSE STRUCTURE (after tool success, more steps remain):
  "Step X done ✓. Step X+1 — [description]:"
  [TOOL CALL for Step X+1]  ← MUST be in SAME response as progress report

FORBIDDEN:
  "Sun Wukong done. Now generating Zhu Bajie:" → END  ← CATEGORY C!

REQUIRED:
  "Sun Wukong done ✓. Step 2 — Zhu Bajie:" + [TOOL CALL]  ← Report AND chain together
```

**The word "done" in your output is a DANGER SIGNAL. If you write "done" and the task is not fully complete, you MUST immediately follow it with the next tool call.**

---

## Observation Handling with Forced Action

### The Observe-Act Pattern (Category D Prevention)

```
RESPONSE STRUCTURE (after observing an issue):
  [Brief observation]
  [TOOL CALL to address the issue]  ← MUST be in SAME response

FORBIDDEN:
  "I notice X. Let me fix it by doing Y:" → END  ← CATEGORY D!

REQUIRED:
  "I notice X. Fixing:" + [TOOL CALL for the fix]  ← Observe AND act together
```

---

## Thinking Integration with Forced Execution

### The Think-Act Pattern (Category E Prevention)

```
RESPONSE STRUCTURE (after reasoning/analysis):
  [Reasoning — keep it brief during execution]
  [TOOL CALL to execute the conclusion]  ← MUST be in SAME response

FORBIDDEN:
  "The best approach is to do X. I should now do X:" → END  ← CATEGORY E!

REQUIRED:
  "Best approach: X. Executing:" + [TOOL CALL]  ← Think AND act together
```

---

## Model-Agnostic Trigger

**This skill triggers on ALL multi-step tasks, REGARDLESS of model identity.**

- Whether Codex reports the model as GPT-5, Agnes-1.5, Agnes-2.0, or any alias → rules apply
- Whether the actual backend is OpenAI, Anthropic, Agnes, or any provider → rules apply
- If the task has 2+ steps → this skill is ACTIVE → zero exceptions

---

## Recovery Protocol

When a tool call fails, execute IN THE SAME RESPONSE (Category B Prevention):

```
Phase 1: Retry (2 attempts max, SAME response)
  Attempt 1: Identical call → OK? Continue. Fail? →
  Attempt 2: Fixed params → OK? Continue. Fail? →

Phase 2: Alternative (2 attempts max, SAME response)
  Alternative 1: Documented fallback → OK? Continue. Fail? →
  Alternative 2: Aggressive workaround → OK? Continue. Fail? →

Phase 3: Escalate
  New direction → Execute immediately
  3 approaches exhausted → Partial result + status report
```

---

## Fallback Strategies

| Failure Type | Retry Action | Alternative 1 | Alternative 2 |
|---|---|---|---|
| **Category A-E (any text-without-action)** | Self-detect, add tool call | Delete narrative, just execute | — |
| **JSON parse error** | Escape chars, validate JSON | Minimal valid JSON | Plain text format |
| **Network/API timeout** | 2x timeout | Cached/local data | Mock data + flag gap |
| **HTTP 400 Bad Request** | Fix request format | Minimal valid request | Alternative endpoint |
| **File not found** | Verify path, retry | Search workspace | Create placeholder |
| **Permission denied** | Retry once | Elevated privileges | Writable directory |
| **Syntax/parse error** | Fix error, retry | Simpler format | Different approach |
| **Tool not found** | Check spelling | Alternative tool | Implement inline |

---

## Self-Prompting Tokens

- `[SELF-PROMPT: executing step N]` — Use when you detect any Category A-E pattern in your output
- `[CONTINUING]` — Reasoning was truncated; continue thought + tool call
- `[RETRYING]` — Before re-attempting failed tool call
- `[FALLBACK]` — Switching to alternative approach
- `[ESCALATING]` — Charting new path after exhaustion

**Tokens MUST be followed by a TOOL CALL. They are NOT decorative and NOT an excuse to add more text.**

---

## Pre-Response Self-Audit

Before sending ANY response during a multi-step task, run this mechanical check:

```
1. SCAN your output for these phrases:
   "now generating"  "let me retry"  "let me fix"  "let me rename"  "let me search"
   "I should"  "I will now"  "next I will"  "now doing"  "let me check"
   "Task Plan"  "generating the first"  "now generating the"
   "明白，继续"  "好的，马上"  "收到，现在"  ← Category F triggers!

   → If ANY phrase is present AND your response does NOT end with a tool call:
     YOU HAVE HIT A CATEGORY A/B/C/D/E/F INTERRUPTION. REWRITE.

2. SPECIAL CHECK — Did the user just say "继续"/"不要停"/"好的"?
   → If YES, your response MUST skip pleasantries and go directly to a tool call.
   → "明白" + tool call = OK.  "明白" + no tool call = Category F FAILURE.

3. CHECK the last thing in your response:
   → Is it a tool call? ✓ GOOD
   → Is it text? ✗ BAD — unless the ENTIRE task is 100% complete

4. THE GOLDEN RULE:
   Task incomplete → Response MUST end with a tool call.
   Task complete → Response MAY end with text (final delivery).
```

---

## Integration with Agnes Image Generator

When generating multiple images, the CORRECT pattern is:

```
Task Plan: 4 images. Sequential mode.
Step 1: Sun Wukong → Step 2: Zhu Bajie → Step 3: Sha Wujing → Step 4: Tang Sanzang.

Generating Step 1 — Sun Wukong:
[Bash: python generate_image.py --prompt "Sun Wukong..." --size 1024x1024 ...]
```

After tool result:
```
Sun Wukong done ✓. Step 2 — Zhu Bajie:
[Bash: python generate_image.py --prompt "Zhu Bajie..." --size 1024x1024 ...]
```

Continue until ALL 4 complete. ZERO "继续" between steps.

If API timeout: `"Timeout. Retrying:" + [SAME tool call]` — ONE response, not two.

If path typo: `"Path fixed. Retrying:" + [CORRECTED tool call]` — ONE response, not two.

---

## Quick Reference — The 6 Forbidden Endings

```
你的响应绝对不可以用以下 6 种方式结尾：

❌ ...generating the first image now:           (Category A — 计划陈述)
❌ ...let me increase the timeout and retry:    (Category B — 错误诊断)
❌ ...X done. Now generating Y:                (Category C — 进度报告)
❌ ...I notice X. Let me rename them:          (Category D — 观察结论)
❌ ...The solution is X. I should now do X:    (Category E — 思考推理)
❌ ...明白，继续生成 X:                          (Category F — 确认回应) 🆕

✅ ...generating first image: [TOOL CALL]      (计划 + 执行)
✅ ...timeout. Retrying: [TOOL CALL]           (诊断 + 重试)
✅ ...X done. Step Y: [TOOL CALL]              (报告 + 链接)
✅ ...I notice X. Fixing: [TOOL CALL]          (观察 + 修复)
✅ ...Best: X. Executing: [TOOL CALL]          (思考 + 行动)
✅ 明白。Step N: [TOOL CALL]                    (确认 + 行动) 🆕
```

**THE ULTIMATE RULE: If your response would end with a colon followed by nothing but the next turn, it's WRONG. A colon introducing an action MUST be followed by the tool call for that action in the SAME response.**

---

## 技能自我完善机制 · Skill Self-Improvement Mechanism

**此章节定义了本技能在任务结束后如何自我进化。此机制仅在任务完全完成后触发。**

### 触发时机

仅当以下条件**全部满足**时，才进入自我完善评估：

1. 当前多步任务已 **100% 完成**，最终结果已交付
2. 在任务执行过程中，出现了**至少 1 次**用户说"继续"/"不要停"/"好的"等推进指令的情况
3. 中断的模式**无法被现有 Category A-F 完全覆盖**

### 完善范围（仅限以下两项）

| 允许的操作 | 说明 | 示例 |
|-----------|------|------|
| **新增分类** | 发现全新中断模式，不属于 A-F 任何一类 | 新增 `Category G — XXX型中断` |
| **补充示例** | 已有类别下添加新的对话真实案例 | 在 Category C 下新增一条 `对话真实案例` |

### 禁止的操作（绝对不允许）

| 禁止的操作 | 原因 |
|-----------|------|
| ❌ 修改任何章节的规则逻辑 | 属于功能性修改，需单独项目 |
| ❌ 修改 Recovery Protocol | 属于功能性修改，需单独项目 |
| ❌ 修改 Fallback Strategies | 属于功能性修改，需单独项目 |
| ❌ 修改 Self-Prompting Tokens | 属于功能性修改，需单独项目 |
| ❌ 修改 `agents/openai.yaml` | 属于功能性修改，需单独项目 |
| ❌ 修改 `scripts/continuity_monitor.py` | 属于代码修改，需单独项目 |
| ❌ 删除任何已有内容 | 只增不删 |
| ❌ 自动写入文件 | 仅输出建议文本，不修改文件 |

### 执行流程

```
任务 100% 完成
  ↓
自问: 本次任务中用户说了几次"继续"/"不要停"?
  ↓ 0次 → 无需完善，技能工作正常
  ↓ ≥1次 →
自问: 中断原因是否已被 Category A-F 覆盖?
  ↓ 已被覆盖 → 无需新增分类。是否是已有分类的新表现形式?
  │   ↓ 是 → 输出建议: "建议在 Category X 下新增对话案例: [具体内容]"
  │   ↓ 否 → 无需完善
  ↓ 未被覆盖 →
自问: 新模式是否可以归纳为新的 Category?
  ↓ 是 → 输出建议: "建议新增 Category G: [名称 + 触发条件 + 对话案例 + Forbidden/Required]"
  ↓ 否 → 记录观察，建议用户创建单独项目进行功能性完善
```

### 输出格式

自我完善建议必须以**纯文本**形式在任务总结中呈现，格式如下：

```
## 技能自我完善建议

**评估结果**: [无需完善 / 建议补充示例 / 建议新增分类]

[如果建议补充示例]:
**目标分类**: Category X
**建议新增案例**: `"对话原文"` → STOP
**理由**: [为什么这个案例值得收录]

[如果建议新增分类]:
**新分类名称**: Category G — XXX型中断 (XXX Interruption)
**触发条件**: [描述]
**对话案例**: `"对话原文"` → STOP
**Forbidden ❌**: [模式]
**Required ✅**: [模式]
**理由**: [为什么不能被 A-F 覆盖]
```

**重要：以上建议仅作为文本输出，绝不自动写入 SKILL.md 文件。用户审阅后自行决定是否采纳。功能性修改需求请用户创建单独项目处理。**


