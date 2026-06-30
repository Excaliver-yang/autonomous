[README_autonomous_continuity.md](https://github.com/user-attachments/files/29496580/README_autonomous_continuity.md)
 # Autonomous Continuity Skill
 
 ## Overview
 
 Autonomous Continuity is a Codex skill that prevents ALL forms of execution interruption in multi-step tasks. It ensures the user never needs to type "继续" (continue) between steps during any multi-step workflow.
 
 **Model-Agnostic:** Applies to ALL models regardless of proxy-reported identity (Agnes-1.5, Agnes-2.0, GPT-5, Claude, or any alias).
 
 ---
 
 ## Core Problem Solved
 
 During multi-step tasks, language models often output a plan, progress report, or error diagnosis and then STOP — waiting for the user to type "继续" to proceed. This skill eliminates that friction entirely.
 
 ---
 
 ## How It Works
 
 ### 1. Interruption Classification System
 
 Every possible output that could cause an interruption is classified into one of five categories:
 
 | Category | Chinese Name | Description |
 |----------|-------------|-------------|
 | A | 计划陈述型中断 | Model outputs a plan but doesn't execute the first step |
 | B | 错误诊断型中断 | Model analyzes an error and says "let me retry" but doesn't actually retry |
 | C | 进度报告型中断 | Model says "X done. Now doing Y" but doesn't actually do Y |
 | D | 观察结论型中断 | Model notices a problem and says "let me fix it" but doesn't fix it |
 | E | 思考推理型中断 | Model reasons about a solution but doesn't execute it |
 
 ### 2. Forced Execution Pattern
 
 For each interruption category, the skill defines a **Forbidden** pattern (what causes the break) and a **Required** pattern (the correct behavior):
 
 - **Forbidden:** Text description of intent WITHOUT a tool call
 - **Required:** Brief text + IMMEDIATE tool call in the SAME response
 
 ### 3. Golden Rule
 
 > **Task incomplete → Response MUST end with a tool call.**
 > **Task complete → Response MAY end with text (final delivery).**
 
 ---
 
 ## Recovery Protocol
 
 When a tool call fails, the skill mandates a phased recovery strategy executed in a SINGLE response:
 
 1. **Phase 1 — Retry:** Up to 2 identical retries
 2. **Phase 2 — Alternative:** Up to 2 documented fallback approaches
 3. **Phase 3 — Escalate:** New direction with immediate execution
 
 ---
 
 ## Self-Prompting Tokens
 
 The skill defines tokens for self-correction during execution:
 
 - `[SELF-PROMPT: executing step N]` — Detects Category A-E pattern, adds tool call
 - `[CONTINUING]` — Reasoning was truncated; continue thought + tool call
 - `[RETRYING]` — Before re-attempting failed tool call
 - `[FALLBACK]` — Switching to alternative approach
 - `[ESCALATING]` — Charting new path after exhaustion
 
 ---
 
 ## Pre-Response Self-Audit Checklist
 
 Before sending any response during an incomplete task, the model must mechanically verify:
 
 1. Scan for forbidden phrases: "now generating", "let me retry", "let me fix", "I should", "I will now", "Task Plan", etc.
 2. Check: Is the last thing in the response a tool call? If it's text → REWRITE.
 3. Apply the Golden Rule.
 
 ---
 
 ## Five Forbidden Endings (Quick Reference)
 
 | ❌ Forbidden Ending | Category |
 |---------------------|----------|
 | "...generating the first image now:" | A — Plan Statement |
 | "...let me increase the timeout and retry:" | B — Error Diagnosis |
 | "...X done. Now generating Y:" | C — Progress Report |
 | "...I notice X. Let me rename them:" | D — Observation Conclusion |
 | "...The solution is X. I should now do X:" | E — Thinking Process |
 
 | ✅ Correct Ending | Pattern |
 |-------------------|---------|
 | "...generating first image: [TOOL CALL]" | Plan + Execute |
 | "...timeout. Retrying: [TOOL CALL]" | Diagnose + Retry |
 | "...X done. Step Y: [TOOL CALL]" | Report + Chain |
 | "...I notice X. Fixing: [TOOL CALL]" | Observe + Act |
 | "...Best: X. Executing: [TOOL CALL]" | Think + Act |
 
 ---
 
 ## Integration with Agnes Image Generator
 
 When generating multiple images, the correct pattern is:
 
 ```
 Task Plan: 4 images. Sequential mode.
 Step 1: Sun Wukong → Step 2: Zhu Bajie → Step 3: Sha Wujing → Step 4: Tang Sanzang.
 
 Generating Step 1 — Sun Wukong:
 [Bash: python generate_image.py --prompt "Sun Wukong..." ...]
 ```
 
 After each successful step, immediately chain to the next:
 
 ```
 Sun Wukong done ✓. Step 2 — Zhu Bajie:
 [Bash: python generate_image.py --prompt "Zhu Bajie..." ...]
 ```
 
 ---
 
 ## Summary
 
 This skill transforms multi-step tasks from a broken interactive flow (where the user must repeatedly type "继续") into a seamless autonomous pipeline. The model plans, executes, recovers from errors, and chains steps — all without ever stopping to wait for user input.
