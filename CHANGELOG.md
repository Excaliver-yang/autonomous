# Changelog

All notable changes to the autonomous-continuity skill.

---

## v3.8 (2026-07-02)

### Added
- **探索韧性规则 (Exploration Resilience Rule)**: The #1 cause of research-task interruptions at Level 3 is "I don't know what direction to explore next" → STOP TO THINK. This is NOT a valid stop reason. The rule provides a mechanical Uncertainty Action Tree: list 2-3 candidate directions in your head → pick one arbitrarily (no evaluation) → execute immediately → if dead end, switch to next candidate → only when ALL exhausted is it a hard boundary. Core principle: "At Level 3, exploration IS analysis. You don't figure out the right direction by thinking — you figure it out by trying. Pick any. Try it. Probe, don't ponder."
- **New hard boundary**: "All exploration directions exhausted" (v3.8 — distinct from "task complete" because the task may be unsolvable given available tools, but you can only know after trying ALL directions)
- **New self-prompting token**: `[EXPLORE-ANY]` — uncertain about next direction → pick one arbitrarily, execute
- **openai.yaml Uncertainty Action Tree**: Mechanical decision tree replacing "自行判断" with concrete steps (list candidates → pick one → execute → try next if dead → exhaust all → hard boundary)

### Fixed
- **Research-task execution gap**: v3.7 rules tell the model "don't stop" but cannot force it to issue a tool call when it genuinely doesn't know what to explore next. The "decide what to do next" cognitive step is a natural interruption point in research tasks. The Exploration Resilience Rule fills this gap by replacing "decide → act" with "pick arbitrarily → act → adjust."

### Changed
- Category H Level 3 hard boundaries: added "all exploration directions exhausted"
- Category H Level 3 forbidden stops: added "不确定下一步该探索什么方向"
- Frontmatter description: added Exploration Resilience Rule to v3.8 feature list
- Self-Prompting Tokens: added `[EXPLORE-ANY]`
- openai.yaml: added Uncertainty Action Tree section, updated RATCHET RULE, updated FINAL RULE, added RESILIENT pattern
- diagnostics.md: added Exploration Resilience analysis

### Context
- Triggered by real session analysis: 6-push Playwright CLI research task where agent pattern was G→G→G→G→G/B→G (exploration chain breaks). Even with v3.7 total-push tracking correctly detecting the ratchet, the model still stopped after each exploration step because "figuring out the next direction" felt like a valid stopping point. The root cause is structural: execution tasks have mechanical next steps, but research tasks require dynamic direction decisions — and that decision point is a natural cognitive boundary. The Exploration Resilience Rule removes the decision step entirely by replacing "decide → act" with "pick arbitrarily → act."

### v3.8.1 Patch — "Let Me" Kill Switch

Same-day patch after further session analysis revealed ALL 6 interruptions shared one pattern: the phrase "让我/let me" followed by an action description, without the tool call. The Colon Rule already detected these — the failure was the model NOT running the self-audit before sending.

**Added:**
- **"Let Me" Kill Switch**: Promoted to the VERY FIRST rule in SKILL.md and openai.yaml. Single mechanical check: "Did I write 'let me/让我' + action description? → DELETE the sentence. REPLACE with the tool call." No judgment required, no multi-pass audit. One check, one action.
- Elevated from PASS 1 phrase scan to independent PASS -2 (runs before ratchet check and colon rule)
- Added as 🔴 KILL SWITCH section at the top of openai.yaml system prompt

**Why this works when Colon Rule didn't:** The Colon Rule is buried in a 4-pass self-audit with 20+ match patterns. The Kill Switch is ONE rule at the TOP of the file with a single mechanical action. Simpler → more likely to be executed. "Delete and replace" is easier to follow than "rewrite."

### v3.8.1 Compliance Failure → v3.9

**Critical finding:** The same-day Kill Switch patch had 0% compliance in the next session (9-push Playwright task). ALL 9 responses contained "让我/let me" phrases. The Kill Switch, Colon Rule, and all self-audits share the same fatal flaw: they require the model to voluntarily check its own output before sending. The model simply... doesn't run the check.

---

## v3.9 (2026-07-02) — No Future Tense Rule

### Root Cause Analysis

Across 15+ analyzed interruption responses in research tasks, **100% contain some form of "让我/let me" + action description.** The Colon Rule (v3.3), Kill Switch (v3.8.1), and PASS scans ALL detect this pattern. But compliance is ~0% because:

1. "让我/let me X" is the model's **natural language habit** — it's how LLMs transition between actions
2. Self-audits require the model to **remember** to check, **recognize** the violation, **decide** to fix it, and **execute** the fix — all before sending
3. Each of these steps has a failure probability. Multiplied together: ~0% compliance

### Solution: Language Constraint, Not Self-Audit

v3.9 stops telling the model "check your output for X" and instead tells it "you don't use X grammar pattern." It's a **language constraint** (like a style guide), not a self-audit.

**Core rule:** No future-tense volitional phrases for actions. Replace ALL "让我/let me/I'll" with present continuous (-ing) labels.

| Before (v3.8, future tense) | After (v3.9, present continuous) |
|---|---|
| "让我检查一下为什么被重定向:" | "Checking redirect cause:" + [TOOL CALL] |
| "let me search for auth logic:" | "Searching auth logic:" + [TOOL CALL] |
| "我来分析路由守卫:" | "Analyzing route guards:" + [TOOL CALL] |
| "I'll try injecting code:" | "Injecting code:" + [TOOL CALL] |

**Why language constraints > self-audits:**
- Self-audit: generate text → scan → recognize → decide → fix → send (6 steps, each with failure probability)
- Language constraint: generate text without future tense → send (the violation never occurs)

### Changed
- SKILL.md: Replaced "Let Me Kill Switch" with "No Future Tense Rule" + replacement cheat sheet
- openai.yaml: Replaced Kill Switch with LANGUAGE CONSTRAINT section + RESPONSE TEMPLATE
- Colon Rule: Reorganized with future-tense patterns as highest priority
- PATTERNS: All labels now use -ing form; added explicit ban on future tense
- FINAL RULE: Added grammar constraint language
- Self-checks: Simplified from 4-pass to 3-pass with future tense as PASS 1
- diagnostics.md: Added Self-Audit vs Language Constraint compliance analysis

### Context
- 9-push Playwright session with 0% Kill Switch compliance proved self-audits don't work
- 15+ analyzed responses all share the "让我/let me" pattern
- Structural fix: change the language the model uses, rather than adding more checks

---

---

## v3.7 (2026-07-02)

### Added
- **Category I — 用户上下文忽视型中断 (User Context Neglect Interruption)**: Agent ignores user-provided context ("I already opened the page", "file is at X") and performs unnecessary verification ("let me check if...") instead of leveraging it directly. 2 real cases. Rule: "Trust user context. Skip verification. Act directly on provided info."
- **Category I 子类型 — 慢命令单步循环 (Slow Command Single-Step Loop)**: Using slow tools (Playwright 12-18s, large compile 30s+) one command per response creates a low-efficiency push loop. Rule: minimum 2+ commands per response with slow tools, even at Level 0.
- **Category H 子类型 — 混合棘轮 (Mixed Ratchet)**: Different interruption categories alternating (A→C→B→G→B) without any single category repeating 3+ times — v3.6 same-category detection misses it entirely. 8-push Playwright CLI session case study.
- **Category B 子类型 — 命令行语法循环 (Command Syntax Loop)**: Shell/platform syntax errors (PowerShell escaping, `&` truncation, `--%` operator) tried one fix per response. Rule: try ALL syntax variants in ONE response.
- **New self-prompting token**: `[TRUST-CTX]` — skip verification, act on user-provided context.

### Fixed
- **CRITICAL: Category H blind spot — Mixed Ratchet**: v3.6 H类 only detected "same category 3+ consecutive". Mixed categories (A→C→B→G→B) with total pushes >= 3 were invisible. v3.7 changes H类 to track TOTAL push count across ALL categories. Real case: 8-push Playwright CLI session where v3.6 silently failed.

### Changed
- Category H trigger: "同一 Category 连续 ≥3 次" → "累计总推进 ≥3 次（任何 Category）"
- Category H 棘轮计数规则: 每次用户推进 +1，不区分 A/B/C/D/E/F/G/I 类型
- Frontmatter: 8-category → 9-category (A-H → A-I)
- Terminal Check: 8 patterns → 9 patterns
- Quick Reference: 8 forbidden endings → 9
- Colon Rule: added v3.7 patterns (`让我确认/检查`, `let me check/verify`)
- Pre-Response Self-Audit PASS -1: added slow-tool bonus rule, total-push tracking
- Fallback Strategies: A-H → A-I
- Self-Improvement: A-H → A-I references
- openai.yaml: v3.6→v3.7, 8→9 forbidden endings, added Category I + Command Syntax Loop + Mixed Ratchet rules
- continuity_monitor.py: v3.6→v3.7, `command_syntax_loop` + `user_context_neglect` patterns, `detect_ratchet_patterns()` rewritten for total-push + mixed ratchet detection, inject v3.7
- interruption-catalog.md: 25→30 cases, 8→9 categories, updated distribution
- diagnostics.md: Mixed Ratchet analysis, Category I boundary, v3.7 distribution update

### Context
- Triggered by real session: 8-push Playwright CLI task where the agent hit A→C→B→B→B→G→G→B alternating interruptions. v3.6 Category H never triggered because no single category appeared 3+ times consecutively. The mixed ratchet blind spot was the most critical flaw in v3.6. Additionally, the session revealed user context neglect ("I already opened the page" → agent verified instead of using) and command syntax loops (PowerShell escaping tried one attempt per response).

---

## v3.6 (2026-07-02)

### Added
- **Category H — 棘轮连续性中断 (Ratchet Continuity Interruption)**: Meta-category detecting same-pattern interruptions repeating 3+ consecutive times within one session. 4-level ratchet escalation: Level 0 (standard, 1+ calls), Level 1 (light, 2+ calls), Level 2 (medium, 3+ calls), Level 3 (heavy, until hard boundary). Triggered by 5-level reverse-engineering session where Category G repeated 5 times with user pushing each step.
- **Category G 子类型 — 多层次探索链 (Multi-Level Exploration Chain)**: Sub-type for when exploration data reveals deeper layers that need further analysis. Key self-check: "Does this data reveal another question that needs answering?" 5 real cases from Codeflying deep reverse-engineering session.
- **Category B 子类型 — 方法切换停滞 (Method Switch Stall)**: Sub-type for voluntary approach switches where "Let me try X instead" replaces execution. Rule: "Switch silently — the tool call IS the announcement."
- **Self-Improvement 中途触发 (Mid-Task Trigger)**: Allow self-improvement assessment when N>=3 same-category interruptions occur mid-task. Unlike post-task trigger (outputs text suggestions), mid-task trigger directly escalates behavior (level up, chain more calls) without outputting text.
- **Project Auto-Configuration Files**: Three new files for project-level autonomous continuity:
  - `hooks/continuity-hook.sh`: postToolUse hook script monitoring stall patterns
  - `templates/CLAUDE.md.snippet`: embeddable core continuity rules for project CLAUDE.md context
  - `templates/settings.json.snippet`: hook and permission configuration for auto-continuity
- **continuity_monitor.py v3.6**: New detection patterns (`recursive_exploration_break`, `ratchet_continuity_break`, `method_switch_stall`). New `detect_ratchet_patterns()` function for consecutive same-category detection. New `--detect-ratchet` CLI flag.
- **Colon Rule** expanded with v3.6 patterns: `let me try.*instead` / `maybe.*should switch` / `改用.*` / `换.*方法.*`.
- **Self-Prompting Token**: `[RATCHET: level N]` for ratchet level escalation tracking.

### Fixed
- Stateless A-G rules structurally incapable of detecting multi-response pattern repetition. Category H adds stateful meta-layer that tracks user push count across the session and escalates minimum steps-per-response.

### Changed
- Frontmatter: 7-category → 8-category, added H to description.
- Terminal Check / Quick Reference: 7 patterns → 8 patterns.
- Self-Improvement Mechanism: Category references A-G → A-H. Added mid-task trigger.
- Pre-Response Self-Audit: added PASS -1 (Ratchet Check — session-level push count).
- Fallback Strategies: A-G → A-H.
- Integration section: updated to 8 categories with Category H escalation awareness.
- openai.yaml: v3.5 → v3.6, 7→8 forbidden endings, added Ratchet Rule + Silent Switching rule, updated scan patterns.
- interruption-catalog.md: 19→25 cases, 7→8 categories, updated distribution percentages.
- diagnostics.md: added Ratchet Continuity Analysis section, updated category distribution, v3.6 audit preparation notes.
- continuity_monitor.py: v3.0 → v3.6, 3 new patterns, ratchet detection, updated inject_continuity().
- 说明.txt: updated version references and directory structure.

### Context
- Triggered by real session analysis: 5-level reverse-engineering task where the agent explored page → SPA → HTML → JS bundles → API, stopping after each layer. User pushed 5 times with "好的"/"ok"/"继续". Each individual stop was a valid Category G violation, but the 5× repetition revealed a meta-level structural flaw that single-response rules cannot address. The Ratchet Continuity Rule was designed as a stateful complement to the stateless A-H classification. Project auto-configuration files added in response to user questions about hooks and auto-start capabilities.

---

## v3.5 (2026-06-30)

### Added
- **Category G — 探索断链型中断 (Exploration Chain Break)**: Research/analysis tasks where exploration sub-steps fail to chain (`curl` → findings → "now let me analyze X" → STOP). 4 real cases from Codeflying reverse-engineering session.
- **JSON & API Error Recovery** section: dedicated chapter covering `Expecting ',' delimiter` (deep JSON error) and `Expecting property name enclosed in double quotes` (root-level JSON error), with char-position-based diagnostic strategy.
- **Colon Rule** expanded with exploration patterns: `现在来.*:` / `(?:let me|now|further)\s+(?:analyze|explore|look).*:`.

### Fixed
- 7 stale count references: `6 categories` → `7 categories`, `A-E` → `A-G`, `A-F` → `A-G` across frontmatter, Terminal Check, Quick Reference, Fallback Strategies, Self-Prompting Tokens, and Self-Improvement Mechanism.
- Colon Rule formatting: orphaned example lines from merge artifact realigned under correct regex patterns.
- SKILL.md ↔ openai.yaml JSON error pattern sync: both now cover `Expecting ',' delimiter` AND `Expecting property name`.

### Changed
- Frontmatter description updated to list all 7 categories.
- Integration section expanded from Agnes Image Generator only → all skills + Category G awareness.
- Self-Improvement Mechanism next-category reference updated: `Category G` → `Category H`.

---

## v3.4 (2026-06-30)

### Added
- **Category C 子类型 — 任务完成幻觉 (Task Completion Hallucination)**: Model claims "I already showed/did X" when nothing was actually done. Real case from README generation session.
- Colon Rule Chinese patterns: `让我.*:` / `我来.*:`.
- Colon Rule English hallucination pattern: `I (?:already|haven't|have).*(?:done|created|shown|generated).*`.

---

## v3.3 (2026-06-30)

### Added
- **冒号规则 (Colon Rule)**: Mechanical last-80-char scan for colon-ending patterns. Designed to catch the highest-frequency failure: `"X完成 ✓. Step N — Name:"` → STOP. 6 initial match patterns. Pre-Response Self-Audit restructured as 3-pass check (PASS 0 = colon scan).
- Category C mechanical rule sub-section with colon trap detection.

### Context
- Triggered by Water Margin (水浒传) test: 3 consecutive `"X完成 ✓。Step N — Name:"` → STOP failures, all Category C. Model understood the rule conceptually but treated colon as a thought boundary. Mechanical scanning added as a non-conceptual safeguard.

---

## v3.2 (2026-06-30)

### Added
- **Category F — 确认回应型中断 (Acknowledgement Interruption)**: User says "不要停"/"继续" → model replies "明白，继续X:" → STOP. The acknowledgement replaces execution. 2 real cases.
- **技能自我完善机制 (Skill Self-Improvement Mechanism)**: Post-task evaluation protocol. Allowed: new categories + new examples. Forbidden: code/rule/protocol changes + auto file writes.
- New real examples to Categories B, C, D from 3rd test session.

### Changed
- Terminal Output Category Check: 5 → 6 patterns.
- Forbidden Endings: 5 → 6.
- Pre-Response Self-Audit: added Category F phrase patterns + User Push Detection.

---

## v3.1 (2026-06-30)

### Added
- **中断分类体系 (Interruption Classification System)**: 5 categories with Chinese/English names, trigger conditions, real conversation cases, Forbidden/Required patterns, and self-check questions.
  - Category A: 计划陈述型 (Plan Statement)
  - Category B: 错误诊断型 (Error Diagnosis)
  - Category C: 进度报告型 (Progress Report)
  - Category D: 观察结论型 (Observation-Conclusion)
  - Category E: 思考推理型 (Thinking Process)
- **终端输出分类检查 (Terminal Output Category Check)**: Pre-send 5-pattern mechanical comparison.
- **Batch Pre-Planning with Forced Execution**: Plan + Step 1 tool call in SAME response.
- Model-Agnostic Trigger: removed all model-specific references (Agnes-1.5/2.0).

### Context
- Triggered by self-analysis that identified 3 root causes: (1) trigger conditions too narrow, (2) missing batch pre-planning, (3) no approval-break handling. Two full test sessions (7+4 interruptions) provided the case library.

---

## v3.0 (2026-06-30)

### Added
- Initial structured rewrite from the original minimal skill.
- Narrative Trap concept as #1 failure mode with FORBIDDEN/REQUIRED examples.
- Anti-Stall Rules (7 rules).
- Recovery Protocol: Phase 1 (Retry 2x) → Phase 2 (Alternative 2x) → Phase 3 (Escalate).
- Fallback Strategies Table (10 failure types).
- Self-Prompting Tokens (`[CONTINUING]`, `[RETRYING]`, `[FALLBACK]`, `[ESCALATING]`, `[SELF-PROMPT]`).
- Pre-Response Self-Audit (5 questions).
- continuity_monitor.py v3.0 with `--detect-narrative-traps`, `--watch`, `--validate-json`.
- Agent interface (openai.yaml) expanded from 1 line to 60+ line system prompt.

### Context
- Original problem: `CC Switch local proxy failed` JSON error + Agnes models pausing mid-execution. Initial skill had only conceptual recovery rules without classification or mechanical checks.

---

## v0.x (pre-v3.0)

### Original State
- Minimal SKILL.md with basic Recovery Protocol and 6 fallback strategies.
- 1-line openai.yaml agent prompt.
- Basic continuity_monitor.py with 5 interruption patterns (no narrative trap detection).
- Trigger conditions hardcoded to "Agnes-1.5 or Agnes-2.0 models".
