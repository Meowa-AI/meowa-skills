# Game development workbench

Develop TypeScript + Three.js games in an isolated remote workspace. Authenticate with your Meowa account API key using the normal runner setup. This beta is restricted to accounts with developer access, matching the website entry `/develop/game-development`. The server must also enable this capability; every project action checks developer access and ownership. Ordinary accounts receive `enabled: false` and project actions return 404, including direct API calls. Shared infrastructure credentials are never client parameters.

| Website action | CLI command | Product inputs |
| --- | --- | --- |
| Entry availability | `game-development-capabilities` | None |
| Create game project | `game-development-create --title "My game"` | Required title, 1–512 characters |
| Open workbench | `game-development-open --project-id ID` | None |
| Read activity and task state | `game-development-read --project-id ID` | None |
| Start development | `game-development-run --project-id ID --prompt "Build a collection game"` | Required prompt, 1–8000 characters |
| Stop task | `game-development-cancel --project-id ID --turn-id TURN` | None |
| Open private game preview | `game-development-preview --project-id ID` | None |
| Download last saved source | `game-development-export --project-id ID` | None |
| Read saved build and publication | `game-development-publication --project-id ID` | None |
| Publish selected saved build | `game-development-publish --project-id ID --build-id BUILD --revision REVISION --generation GENERATION` | Explicit public release action |
| Withdraw public game | `game-development-unpublish --project-id ID --revision REVISION --generation GENERATION` | Explicit withdrawal action |
| List imported images | `game-development-assets --project-id ID` | None |
| Import library image | `game-development-import --project-id ID --source-url URL` | Required source URL, 1–2048 characters |

Imports use the same `source_url` field as the website's library image selection. Only accessible final PNG/JPEG/GIF/WebP images are accepted: at most 8 MiB per file, 64 files and 16 MiB per project. The server reads the owned source; the runner does not download or persist it. Imports are deduplicated by content and become available at the start of the next development task. Active tasks and public releases are not automatically changed. After an uncertain result, read the imported list before retrying; do not automatically submit a development task. Arbitrary URLs and intermediate workflow files grant no access.

Run commands with `python3 <skill-dir>/meowart_api.py`. Create then open the project; read until `execution_ready` before submitting development. Titles and prompts are trimmed just like the website. There are no model, provider, execution-command, or sandbox configuration options.

Creation prints a project ID before the request. On an uncertain response, repeat `create` with that same `--project-id` and title. Task submission similarly prints a request ID; retain it and use `--request-id` for retries of the same prompt. Use a new ID only for a new task. Failed or cancelled tasks are not automatically replayed.

`read --after N` resumes from `next_cursor`; the default is exactly `0`. Drain pages while `has_more`, otherwise poll about once per second. If `generation` changes, discard old activity and read from `0`. A paused `service.code` keeps queued tasks; cancellation and existing previews remain available. Re-read before deciding to submit another task.

Preview returns a short-lived private URL when ready. Open it in a browser; it is not a public release. Do not share tickets. Session commands print only the declared workbench view and do not save raw responses, metadata, credentials, or media files.

`game-development-export` downloads only the owned project's declared source ZIP from its dedicated authenticated endpoint. The global `--output-dir` selects a local destination; omitted, the current directory is used. It writes a unique `game-source-*.zip` without overwriting existing files or extracting/ executing anything. This source-code deliverable is separate from media downloads; ordinary media downloaders still reject non-media responses. JSON, HTML, redirects, unsafe ZIP paths, unexpected files and oversized archives are rejected before publication.

The ZIP contains the latest saved source, which may not yet pass typecheck/build; it does not include unsaved changes. Export remains available while execution is paused. It includes standard npm/Vite/TypeScript configuration, `.gitignore`, optional `README.md`, the game's `game-assets.json`, recognized source files under `src/`, and game assets under `public/`. Hidden files, dependency/build directories, logs, caches, credentials and internal workflow manifests are excluded. Keep game code and assets in the declared folders. Export is private and does not publish a game. After extracting locally, review the source, run `npm ci`, then `npm run dev`; use `npm run typecheck` and `npm run build` for validation.

For static builds, list public runtime assets explicitly: `game-assets.json` contains `{"files":["coin.png"]}` for `public/coin.png`. Bundled imports are collected by the build tool; unlisted files in `public/` and existing `dist/` contents are not copied. Saving a static build does not publish it.

Publishing makes the saved build playable by anyone with its link. It never happens automatically after development. Only publish on the user's explicit request for public access. Read `publication` first, review the candidate, and pass its `candidate.id`, `revision`, and `generation` unchanged to `publish`. These are required identity/concurrency values, not editable game settings; the website supplies the same fields from the displayed state. `unpublish` uses the current `revision` and `generation`. A 409 means state or candidate changed: read again and review the new version instead of automatically resubmitting. After an uncertain response, read state before deciding what to do; no mutation is automatically retried.

The published version remains fixed when development continues. Replacing or withdrawing it invalidates its old URL; publishing after withdrawal creates a new URL. Publication reads and withdrawal remain available while execution is paused. Public play does not require the game workspace to be running. Withdrawal stops subsequent file requests, but cannot recall files already loaded or saved. These commands print only the declared publication view and never download or execute the published game.

The project template uses strict TypeScript, pinned dependencies and a lockfile. Verification order is **typecheck → build → actual gameplay**. Vite transpiles TypeScript but does not type-check it; `typecheck` must run `tsc --noEmit`. Browser testing still requires the applicable host authorization.
