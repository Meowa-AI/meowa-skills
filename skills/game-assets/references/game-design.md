# Game Designer

Use the persistent Game Designer Agent for game concepts, mechanics, systems, balance, progression, content planning, research, critique, and design documents. Do not use an image-generation command merely to answer a planning question.

## Start a design run

```bash
python3 meowart_api.py game-design-run \
  --prompt "设计一款适合双人合作的像素地牢游戏，先明确核心循环和差异化" \
  --project-title "双人像素地牢" \
  --locale zh-CN \
  --output-dir ./meowa-output
```

The command creates a project and a Game Designer thread when IDs are omitted. It prints `project_id`, `thread_id`, and `api_job_id`; retain them. The saved task directory contains `game_design_outputs.json` and a `design_docs/` tree of Markdown documents.

To continue the same design context, run the command again with both IDs:

```bash
python3 meowart_api.py game-design-run \
  --prompt "把战斗资源循环细化，并回答上轮提出的问题" \
  --project-id <project_id> \
  --thread-id <thread_id> \
  --output-dir ./meowa-output
```

If polling is interrupted, recover the paid task without resubmitting it:

```bash
python3 meowart_api.py game-design-poll \
  --project-id <project_id> \
  --thread-id <thread_id> \
  --api-job-id <api_job_id> \
  --output-dir ./meowa-output
```

## Billing

- There is no initial credit reservation and no per-run maximum charge.
- Usage is charged incrementally after each planning-model call: uncached input is 150 credits per million tokens, cached input is 15 per million, and output including reasoning is 900 per million. The cumulative per-job amount is rounded up to whole credits.
- Before accepting a message and before each later planning round, the service checks the current balance against that round's estimated input, recent observed cache, and estimated output. A call proceeds only when the estimate is covered.
- The runner prints cumulative calculated credits, charged credits, and remaining credits while polling. If the balance is empty or cannot cover the next estimated round, it reports the exact balance state and includes the recharge URL instead of starting another model call.
- Completed model calls remain charged when a task later fails or is cancelled; calls that never start are not charged.
- Asset, image, audio, video, web-research, or other paid tools are priced separately under their existing capability rules. The Agent token charge does not include them.

The output manifest reports only provider-neutral token counts and credit settlement. It does not store raw Agent events, provider responses, internal URLs, prompts, signed links, or debug metadata.

## Working rules

- Give the Agent the product goal, audience, platform, constraints, references, and decision to make. Avoid prescribing a document outline unless the structure itself is required.
- Treat an `ask_user` result as a real design question. Present it to the user, then continue the same project and thread with their answer.
- Read the saved Markdown files before summarizing the result. Distinguish confirmed decisions from proposals and open questions.
- Use a new thread when the design direction is unrelated; reuse the existing thread for iterative refinement.
- Do not resubmit a job merely because local polling timed out. Recover it with `game-design-poll`.
