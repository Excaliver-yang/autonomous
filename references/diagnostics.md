# Diagnostics Reference

Error diagnosis patterns, audit findings, and language analysis from the autonomous-continuity skill development.

---

## JSON Error Diagnostics

### Error Type Comparison

Two distinct JSON error patterns encountered with the Agnes API via Codex proxy. The char position is the key differentiator.

| Attribute | Type 1: Comma Delimiter | Type 2: Property Name |
|-----------|------------------------|----------------------|
| **Error message** | `Expecting ',' delimiter: line 1 column 124 (char 123)` | `Expecting property name enclosed in double quotes: line 1 column 2 (char 1)` |
| **Char position** | 123 (deep) | 1 (root) |
| **Meaning** | JSON structure is mostly valid; a comma is missing at a specific nested location | The very first character after `{` is illegal — the entire body is not valid JSON |
| **Typical root cause** | Trailing comma, missing comma between properties, unescaped character in a string value | Single quotes instead of double quotes, unquoted property names, BOM character, or non-JSON content passed as JSON |
| **Fix strategy** | Locate and fix the specific position | Reformat the entire request body from scratch |
| **Diagnostic rule** | char > 100 → deep structural fix | char < 5 → root-level reformat |

### Common JSON Fixes

```
Trailing commas:        {"a": 1,}           → {"a": 1}
Single quotes:          {'key': 'value'}    → {"key": "value"}
Unquoted property:      {key: "value"}      → {"key": "value"}
Unescaped quotes:       {"t": "say "hi""}   → {"t": "say \"hi\""}
Unescaped backslashes:  {"p": "C:\Users"}   → {"p": "C:\\Users"}
Missing commas:         {"a": 1 "b": 2}     → {"a": 1, "b": 2}
UTF-8 BOM:              ﻿{"key": ...}  → {"key": ...}
```

---

## Audit Findings (v3.5 Diagnostic Audit)

### Stale Count References (7 defects found, all fixed)

During the v3.5 audit, Category G was added but multiple references to category counts were not updated. This is a systematic maintenance hazard in iteratively-developed skill files.

| Location | Stale Value | Correct Value |
|----------|------------|---------------|
| Frontmatter description | `6 categories` | `7 categories` |
| Terminal Output Check header | `6 个模式` | `7 个模式` |
| Quick Reference title | `The 6 Forbidden Endings` | `The 7 Forbidden Endings` |
| Quick Reference CN subtitle | `6 种方式` | `7 种方式` |
| Fallback Strategies | `Category A-E` | `Category A-G` |
| Self-Prompting Tokens | `Category A-E pattern` | `Category A-G pattern` |
| Self-Improvement trigger | `Category A-F` | `Category A-G` |

**Prevention rule for future iterations:** When adding a new category, search for `A-` followed by the previous last letter and update all references.

### Merge Artifact (1 defect found, fixed)

Colon Rule section had 3 orphaned example lines from the `I (?:already|haven't|have)` regex that were displaced below v3.5 patterns instead of being aligned under their parent regex.

### SKILL.md ↔ openai.yaml Inconsistency (1 defect found, fixed)

SKILL.md's JSON error coverage only mentioned `Expecting ',' delimiter` while openai.yaml covered both comma and property-name errors. A dedicated JSON & API Error Recovery section was added to SKILL.md to close this gap.

---

## Language Analysis: Chinese vs English

### Conclusion: Language Does NOT Affect Interruption Patterns

The root cause of all interruptions is output structure (colon-ending text without tool call), not output language.

### Evidence

| Language | Interruption Case | Structure Pattern |
|----------|------------------|-------------------|
| Mixed CN/EN | `"武松完成 ✓。Step 2 — 鲁智深:"` → STOP | Colon-ending progress report |
| Pure EN | `"Sun Wukong done. Now generating Zhu Bajie:"` → STOP | Colon-ending progress report |
| Pure CN | `"明白，继续生成猪八戒:"` → STOP | Colon-ending acknowledgement |
| EN thinking | `"Let me create"` → STOP | Intent declaration without execution |
| CN thinking | `"让我搜索一下它在 skill 中的位置。"` → STOP | Intent declaration without execution |
| EN research | `"Now let me explore further:"` → STOP | Colon-ending exploration chain |
| CN research | `"现在来分析/探索/查看:"` → STOP | Colon-ending exploration chain |

### Implication

The Colon Rule and PASS 0 last-80-char scan are language-independent. The match patterns simply need to cover both English and Chinese variants of the same structural patterns. v3.5 covers both.

---

## Category Distribution Analysis

### Why Category C Dominates (68.4% of all interruptions)

Category C (Progress Report Interruption) is the highest-frequency failure by a wide margin:

1. **Psychological "done" signal**: The word "done" / "完成" triggers a cognitive boundary — the model feels the step is complete and naturally stops.
2. **Colon as thought boundary**: The colon in `"Step N — Name:"` is grammatically a "continuation marker" but cognitively becomes an "ending marker" for the model.
3. **Progress reporting feels like work**: Describing what was accomplished feels productive, so the model treats it as a complete output.

### Mitigation Strategy Evolution

| Version | Strategy | Effectiveness |
|---------|----------|--------------|
| v3.0 | Conceptual rule: "NEVER stop after progress report" | Low — model understood but didn't comply |
| v3.1 | Category C with Forbidden/Required patterns | Medium — model could classify but still violated |
| v3.2 | More real examples added to Category C | Medium — examples helped but didn't solve root cause |
| v3.3 | **Colon Rule**: mechanical last-80-char scan | High — bypasses "understanding" entirely |
| v3.5 | Colon Rule expanded with 12 match patterns | Highest — comprehensive pattern coverage |

### Key Lesson

**Conceptual rules ("don't stop after reporting progress") are insufficient for LLM behavior modification. Mechanical pattern-matching checks ("if last 80 chars match X, rewrite") are necessary as a complementary layer.**

---

---

## Ratchet Continuity Analysis (v3.6)

### The Ratchet Problem

Individual Category A-G rules are **stateless** — they check one response at a time. A session can fail at the meta-level: the same category interruption repeats 5+ consecutive times while each individual response technically triggers the same Forbidden pattern.

**Example:** In the 5-level reverse-engineering session:
- Each response: `[Finding] + "Now let me explore X:"` → STOP (Category G)
- Individually, each is a Category G violation
- Collectively, 5 Category G violations in a row = structural ratchet failure

The stateless rules cannot say "this is the 5th time — escalate." Category H fills this gap.

### Detection Heuristic

Track consecutive same-category interruptions in session logs:
- >= 3 consecutive Category G → Ratchet flag
- >= 3 consecutive Category C → Ratchet flag
- >= 3 consecutive **any** same-category → Ratchet flag

### Mitigation: Ratchet Level Escalation

Instead of only preventing individual interruptions, the skill now self-escalates the MINIMUM number of tool calls per response based on user push count.

| User Pushes | Ratchet Level | Min Tool Calls | Stop Condition |
|------------|---------------|----------------|----------------|
| 0 | Level 0 (Standard) | 1 | Task complete or A-H violation |
| 1 | Level 1 (Light) | 2 | Task complete (must chain) |
| 2 | Level 2 (Medium) | 3 | Task complete (deep chain) |
| 3+ | Level 3 (Heavy) | Unlimited | Only hard boundaries |

### Why This Works

The ratchet rule addresses the root cause: each "继续" is feedback that the agent should do MORE per response. By formalizing this into escalating minimums, the rule becomes self-reinforcing — more pushes = more work per push = fewer pushes needed.

### Key Lesson

**Stateless rules (checking one response) are necessary but insufficient. Stateful meta-rules (tracking push frequency across responses) are required to prevent cumulative structural failures.**

### The Mixed Ratchet Blind Spot (v3.6 → v3.7 Fix)

v3.6's Category H detection had a critical blind spot: it only detected **consecutive same-category** interruptions (e.g., G→G→G). Mixed-category ratchets (A→C→B→B→G→B) slipped through because no single category appeared 3+ times consecutively.

**Real case:** Playwright CLI session — 8 user pushes across alternating categories:
```
A(计划)→C(初始化)→B(重定向)→B(语法)→B(URL截断)→G(快照)→G(标签)→B(重定向)
```
- No single category repeats 3+ times consecutively
- v3.6 Category H: **NOT TRIGGERED** — silent failure
- User pushed 8 times with zero ratchet escalation

**v3.7 fix:** Category H now tracks **TOTAL push count**, not category-specific streaks. The detection heuristic becomes:
- Count ALL user pushes ("继续"/"好的"/"ok"/"不要停") regardless of preceding category
- total >= 3 → ratchet detected → escalate
- Also flag `mixed_ratchet: true` when unique categories >= 3 and no same-category streak exists

### New Category Distribution (v3.7)

| Category | Cases | Key Change |
|----------|-------|-----------|
| I — User Context Neglect | 2 | NEW: agent verifies instead of leveraging user-provided info |
| H — Ratchet Continuity | 3 | UPDATED: now tracks total pushes (including mixed ratchet) |
| B — Error Diagnosis | 5 | EXTENDED: command syntax loop sub-type added |

---

## Exploration Resilience Analysis (v3.8)

### The Research-Task Execution Gap

After v3.7's total-push ratchet tracking, a fundamental structural problem remained:

**Execution tasks** (image generation, file operations) have **mechanical next steps**: "generate Zhu Bajie after Sun Wukong" — the agent knows exactly what to do next. The only failure is not chaining the tool call.

**Research tasks** (code analysis, reverse engineering, debugging) have **dynamic next steps**: "this file is minified → should I search for route guards, check cookies, or analyze the network tab?" — the agent must DECIDE before it can act. That decision step is a natural cognitive boundary where interruptions occur.

### Why Prompt Rules Alone Can't Fix This

v3.7 rules say "don't stop at Level 3." But when the model genuinely doesn't know which of 3 directions to pursue, it faces a conflict:
- "Don't stop" → must issue a tool call
- "But which tool call?" → can't decide without thinking
- "Thinking takes a response" → stops to think

The model resolves this by... stopping to think. The rule says "don't stop" but the model's architecture creates a hard dependency: decision precedes action, and decision requires a response boundary.

### The Exploration Resilience Solution

Instead of fighting the decision→action dependency, the rule **removes the decision step entirely**:

```
Old: Decision → Action (decision requires a response boundary)
New: Pick arbitrarily → Action → Adjust (no decision, just probing)
```

The Uncertainty Action Tree replaces "decide what to do" with "pick any direction and try it." This works because:
1. At Level 3, the cost of trying a wrong direction is low (it's just one tool call)
2. The cost of NOT trying anything is high (user must push again)
3. Trying the "wrong" direction still produces useful information (it confirms a dead end)

### Expected Effect on the 6-Push Session

| Push# | What happened (v3.7) | What should happen (v3.8) |
|-------|---------------------|--------------------------|
| 1 | B: eval error → fix syntax → stop | Same — Level 1, can still make single-step fixes |
| 2 | G: found redirect → "let me check why" → stop | Better — Level 2, should chain cookie check |
| 3 | G: no cookies → "let me view route guard" → stop | **Resilience triggers**: pick any direction (cookies done, route guard OR search auth logic) → execute |
| 4-6 | G→G→G: each mini-exploration → stop | **Resilience active**: pick→try→dead?→next→try→dead?→next→all exhausted → hard boundary |

### Key Lesson

**"Don't stop" is a negative instruction — it tells the model what NOT to do. The Exploration Resilience Rule is a positive instruction — it tells the model what TO DO when it doesn't know what to do. Pick any direction. Try it. Negative rules create paralysis; positive rules create action.**

---

## "Let Me" Kill Switch Analysis (v3.8.1)

### The Colon Rule Compliance Problem

The 6-push Playwright session revealed a critical issue: **ALL 6 interruptions contained "让我/let me" phrases that the Colon Rule already detects.** The rule was correct — the model just didn't follow it.

```
Session analysis (all 6 responses):
  ✅ Colon Rule PATTERN MATCH: 6/6 (100% detected)
  ❌ Colon Rule COMPLIANCE:    0/6 (0% followed — model sent response anyway)
```

### Why Compliance Fails

The Colon Rule is embedded in a 4-pass self-audit (PASS -2, -1, 0, 1, 2) with 20+ match patterns, nested formatting, and multi-step fix instructions. Cognitive load is too high for a pre-send check that must happen in milliseconds.

### The Kill Switch Solution

Instead of adding MORE patterns to the audit, the Kill Switch simplifies to ONE rule:

```
Did I write "let me/让我" + action description?
→ YES → Delete the sentence. Put the tool call there instead.
→ Send.
```

**Design principle:** The Colon Rule has high precision (correctly identifies all violations) but low compliance (model ignores it). The Kill Switch trades precision for compliance: it catches fewer patterns but the ONE pattern it catches (let me/让我) accounted for 100% of the 6-push session's interruptions. One rule, perfectly followed, beats 20 rules inconsistently followed.

### Placement Matters

The Kill Switch is placed:
1. **SKILL.md**: As the first section after the opening statement (before the classification system)
2. **openai.yaml**: As the first rule after the mode declaration (before "THE ONLY RULE THAT MATTERS")
3. **Pre-Response Self-Audit**: As PASS -2 (before ratchet check, before colon rule)

This "first thing you see" placement ensures it's read before any other rule — maximizing compliance probability.

### Kill Switch Compliance Failure (v3.8.1 → v3.9)

The Kill Switch was tested in a 9-push Playwright session. Result: **0/9 compliance.** ALL 9 responses contained "让我/let me" phrases. Placement at the top of the file did not improve compliance.

This proved that **self-audit placement doesn't matter.** The failure is in the audit mechanism itself — not in where it's positioned.

---

## Self-Audit vs Language Constraint — The v3.9 Pivot

### The Fundamental Problem

All rules from v3.3 (Colon Rule) through v3.8.1 (Kill Switch) share one mechanism: **pre-send self-audit**. The model must voluntarily check its own output before sending.

| Version | Mechanism | Compliance | Evidence |
|---------|----------|-----------|---------|
| v3.3 | Colon Rule (20+ patterns) | ~10% | Various sessions |
| v3.8.1 | Kill Switch (1 pattern, top of file) | 0% | 9-push session: 0/9 |
| v3.8.1 | Kill Switch + Colon Rule combined | 0% | Same session |

**Finding: Rule simplicity and placement do NOT correlate with self-audit compliance.** The failure is systemic.

### Why Self-Audits Fail (Cognitive Model)

The model generates text autoregressively. "让我检查X" is generated before any rule can intercept it. Post-generation audit requires:
1. Remember the rule exists
2. Scan generated text
3. Recognize the pattern match
4. Decide it's a violation
5. Execute the fix (delete + rewrite)
6. Send corrected response

Each step has non-zero failure probability. Multiplied = near-zero compliance.

### The Language Constraint Alternative

v3.9 replaces "check your output for X" with "you don't use X grammar pattern." It's a **generation-time constraint** (style guide), not a **post-generation audit** (checklist).

| Mechanism | Operates | Failure Mode |
|-----------|---------|-------------|
| Self-audit | After generation | Model forgets/ignores the audit |
| Language constraint | During generation | Model follows the grammar rule |

LLMs are better at following stylistic rules during generation ("use -ing for action labels") than at auditing output after generation ("scan for 'let me' and delete it"). The constraint shapes token probabilities; the audit fights them.

---

## v3.6 Audit Preparation

The following locations must be verified after v3.6 changes:
- Frontmatter: 7→8 categories (SKILL.md + openai.yaml)
- Terminal Check: 7→8 patterns
- Quick Reference: 7→8 forbidden endings
- Colon Rule: new v3.6 patterns present in all 3 locations (SKILL.md PASS 0, openai.yaml PASS 0)
- Self-Improvement: A-F→A-H, A-G→A-H references throughout
- Fallback Strategies: A-G→A-H
- Self-Prompting Tokens: A-G→A-H, added RATCHET token
- Integration section: 7→8 categories
- continuity_monitor.py: version, pattern dict, ratchet function wired, --detect-ratchet flag
- interruption-catalog.md: 19→25 cases, percentages recalculated
- diagnostics.md: distribution percentages, ratchet analysis added

### New Pattern Locations Checklist
New v3.6 colon patterns must appear in:
- [ ] SKILL.md Colon Rule match patterns
- [ ] SKILL.md Pre-Response Self-Audit PASS 0
- [ ] openai.yaml Colon Rule (METHOD SWITCH TRAPS section)
- [ ] openai.yaml PASS 0 last-80-char scan

---

## Cross-Category Boundary Analysis

### Fuzzy Boundaries (Classification Ambiguity Without Functional Conflict)

Some interruption patterns sit at the boundary between two categories. In all cases below, the fix action is identical (add tool call), so classification ambiguity does not cause behavioral conflict.

| Boundary | Categories | Example | Why Ambiguous |
|----------|-----------|---------|---------------|
| Plan ↔ Exploration | A ↔ G | "现在来生成第一张:" vs "现在来分析路由:" | Both state next action after preamble. A has Task Plan preamble; G has research findings preamble. |
| Progress ↔ Observation | C ↔ D | "All done. Let me rename:" vs "I notice overwrites. Let me rename:" | C has step-success trigger; D has problem-discovery trigger. Same fix. |
| Thinking ↔ Exploration | E ↔ G | "I should analyze this" vs "Now let me analyze this" | E is conceptual reasoning; G is research chaining. Both require a tool call after the conclusion. |
| Error Diagnosis ↔ Exploration | B ↔ G | "Error. Let me retry:" vs "Found X. Let me explore Y:" | B triggered by failure; G triggered by research step completion. Both state next intent without executing it. |
| Exploration ↔ Ratchet | G ↔ H | Category G violations repeated 5 times in one session | H is the meta-layer above G. Individual responses are G; the pattern's frequency makes it H. Same fix (chain more) but H adds escalation. |
| Progress ↔ Ratchet | C ↔ H | Category C violations repeated 4 times (colon traps) | H detects the repetition. C fixes each response; H fixes the cumulative pattern. |

**Design principle:** When two categories have the same fix, classification ambiguity is acceptable. The Colon Rule acts as a universal safety net that catches all colon-ending patterns regardless of category.

**v3.6 Design principle:** Category H is unique — it is the only category whose fix is NOT "add a tool call to this response" but rather "increase the MINIMUM tool calls for ALL future responses in this session." It modifies behavior, not content.

**v3.7 Design principle:** Category H now tracks TOTAL push count across ALL categories, not just same-category streaks. A mixed ratchet (A→C→B→G→B, 8 pushes) is just as harmful as a same-category one (G→G→G). The counter doesn't care about category type. Category I introduces the principle of "trust user context — skip verification."
