# Meowa CLI 快速开始

游戏开发工作台命令、项目重试与活动恢复见 [game-development.md](references/game-development.md)。使用 `game-development-import --project-id ID --source-url URL` 导入有权使用的最终图片，使用 `game-development-assets --project-id ID` 查看已暂存素材；素材在下一轮开发时同步，不会自动启动任务或发布游戏。

单图任务只返回最终图片；多图素材包可以附带独立预览。

这份文档只负责安装、Meowa 账户认证和首次运行。具体美术能力、参数选择和工作流协作方式由 `SKILL.md` 及 `references/` 中的对应模块说明。

## 安装

只使用本地工具无需安装依赖或配置 API key：例如 `python3 <skill-dir>/scripts/split-components.py sheet.png --output-dir components`。本地 tools 统一放在 `scripts/`，参数和限制见 [local-tools.md](references/local-tools.md)。下面的依赖用于 API runner。

在 Skill 仓库根目录安装 runner 依赖：

```bash
python3 -m pip install requests Pillow
python3 skills/game-assets/meowart_api.py --help
python3 skills/game-assets/meowart_api.py --version
```

## 更新 Skill

旧版 runner 仍可继续执行；服务端发现新版本时，runner 只提示一次，不会阻断命令。
如果旧版 runner 执行失败，会额外提示该错误可能由版本滞后导致。此时先更新完整 Skill，
不要重新提交已经扣费的任务：

```bash
git -C <meowa-skills-repo> pull --ff-only
cp -R <meowa-skills-repo>/skills/game-assets/. \
  "${CODEX_HOME:-$HOME/.codex}/skills/game-assets/"
python3 "${CODEX_HOME:-$HOME/.codex}/skills/game-assets/meowart_api.py" --version
```

更新后先用顶层 `--help` 查看可用的 `*-poll` 恢复命令，再使用原 `job_id` 恢复下载。
通用图片任务统一使用 `general-image-poll`；旧轮询命令仍兼容。恢复命令只轮询原任务，
不会重新提交或再次扣费。必须复制整个 `skills/game-assets` 目录，不能只替换
`SKILL.md` 或 `meowart_api.py`。

```bash
python3 skills/game-assets/meowart_api.py --help
python3 skills/game-assets/meowart_api.py general-image-poll \
  --job-id <original-job-id> \
  --output-dir <output-dir>
```

## 创建 Meowa API key

普通账号在登录或 `credits-balance` 查询余额时自动获得当天 10 积分，北京时间次日零点到期。`free-credits` 只查询资格，并返回网页积分中心链接。风控账号在网页通过安全验证后手动领取每天 20 积分，最多 5 次、累计 100 积分；每笔有效期 7 天，未领取日期不补发，问卷、活动和邀请不增加额度。
有效充值账号豁免免费福利风控，余额耗尽仍保留豁免；全部付款全额退款或拒付后重新判定。账号封禁仍生效。CLI 不代替用户完成人机验证。

```bash
python3 skills/game-assets/meowart_api.py free-credits
```

1. 登录 [Meowa API Keys](https://meowa.ai/#/api-keys)。
2. 点击 `Create API Key`。
3. 复制以 `ma_live_` 开头的 key，并仅保存在自己的本地环境中。

不要把 key 粘贴到聊天、prompt、命令参数、截图、日志或 Git 仓库中。

## 配置认证

### macOS 或 Linux

只为当前终端会话配置：

```bash
export MEOWART_API_KEY="ma_live_xxxxxxxxxxxxxxxxxxxx"
```

### Windows PowerShell

只为当前 PowerShell 会话配置：

```powershell
$env:MEOWART_API_KEY = "ma_live_xxxxxxxxxxxxxxxxxxxx"
```

### 使用本地 `.env`

也可以在运行命令的当前目录创建 `.env`：

```dotenv
MEOWART_API_KEY="ma_live_xxxxxxxxxxxxxxxxxxxx"
```

确保 `.env` 已被 Git 忽略。环境变量值只填写 `ma_live_...` 本身，不要添加 `Bearer`、字段名或其他前缀。runner 不接受命令行凭据参数。

## 验证认证

```bash
python3 skills/game-assets/meowart_api.py credits-balance
```

能够返回当前账户余额即表示配置成功。输出中的 `total_credits` 是总可用积分，等于
`paid_credits + subscription_credits + trial_credits`；`trial_credits` 是有期限的体验积分，
其最近到期时间由 `next_trial_credit_expires_at` 表示。`map-reference-search` 和
`map-reference-download` 可在未认证时使用，但策划 Agent、图片、动画、视频和音频命令都需要有效的 Meowa API key。

如果看到以下错误：

```text
Meowa authentication is not configured.
```

请确认：

- 环境变量名是 `MEOWART_API_KEY`；
- key 以 `ma_live_` 开头且没有多余前缀；
- 使用 `.env` 时，命令从包含该文件的目录执行；
- 新开终端后，临时环境变量已经重新设置。

## 开始使用

先读取 `SKILL.md` 选择正确模块，再查看对应命令：

```bash
python3 skills/game-assets/meowart_api.py <command> --help
```

每次生成都指定新的输出目录，并只交付任务目录中的最终媒体与 `final_outputs.json`。
策划任务使用 `game-design-run`，会保存 `game_design_outputs.json` 与 `design_docs/` 下的 Markdown 文档；不预扣、不封顶，按实际 token 实时增量扣费，下一轮预估积分不足时会停止并提示充值。

### 通用生成 `general-image-run`

通用生成统一使用 `general-image-run`。旧命令 `image-2.5-run`、`image-2-run`、`nano-banana-run` 仍可用，分别等价于 `--generation-model image-2.5`、`image-2`、`nano-banana`，原参数和默认值不变。模型选项与条件参数见 [生成指南](references/pixel-and-hd-assets.md#general-generation-hd-or-pixel-style)。

`general-image-run --prompt "..."` 使用 Image 2.5 Sunburst；默认 `--quality standard`。
质量仅支持 `standard/detailed/ultimate`，对应网页 普通/精细/极致 与 canonical `low/medium/high`。
`--resolution 1K|2K` 默认 1K；`--aspect-ratio` 默认 1:1，支持 1:1、3:4、4:3、9:16、16:9。
可重复 `--reference-image` 传参考图；失败或中断用 `general-image-poll --job-id ...` 恢复，勿重复提交。
1K 基础积分为 1/5/10，2K 为 2/10/20；每张参考图另加 2 积分，由服务端结算。

通用生成统一使用 `general-image-run`，`--generation-model image-2.5|image-2|nano-banana` 默认 `image-2.5`。万能编辑高清模式默认使用 Image2.5、2K；像素模式默认不变。万能编辑支持 `image-edit-run --generation-model image-2.5`，参数与 `image-2` 相同。普通／精细／极致基础积分：1K 为 1/5/10，2K 为 2/10/20；每张参考图 +2。Image2.5 去背景免费，只提供普通抠图；失败则不去背景、不扣附加费。分区像素化沿用现有附加费。

素材克隆使用 `asset-clone-run` 和 `/api/workflows/asset_clone/run`。`--clone-count` 可选 1、4、9、16、25、36，返回完整网格图而不自动切分。多张参考图必须同尺寸；尺寸不一致时使用 `--cell-width`、`--cell-height` 和 `--fit-mode pad|crop` 居中处理，不缩放。像素模式默认分区量化与多重像素化，像素缩放比例低于 2、高清缩放比例低于 0.5 时提交前拒绝。像素和高清模式均默认 Image2.5、1K、精细画质；Nano Banana 固定普通画质，默认不去背景；Image2.5 默认去背景。背景选项只有 `none` / `standard`。

素材克隆的模型选择：

- **色彩还原**：GPT Image2.5 色彩层次更丰富，更能还原参考图色系，整体更鲜艳；Nano Banana 配色较保守，可能偏离参考图色系。
- **形体控制**：Nano Banana 对轮廓、像素边缘和体积尺度的一致性控制更强，适合形体及尺寸约束严格的像素资产；GPT Image2.5 像素质感相对较弱，资产尺寸更容易变化。
- **去背景**：GPT Image2.5 去背景不收附加积分；Nano Banana开启去背景需额外积分，以当前报价为准。

素材克隆默认跳过润色（`--skip-prompt-optimization` 已开启）。省略 `--prompt` 时使用「参考图 1 的布局，生成1 个不同外观的美术资产，保持美术风格一致。」，数量随 `--clone-count`（默认 1）变化；有额外要求或图内实际数量不同时，显式传入完整 `--prompt`，原样使用，不追加模板、不改数量。`--clone-count` 是拼接格数，仅支持 1、4、9、16、25、36，尽量匹配输入张数；单张组合图通常保持 1，在 prompt 中写实际 N 个物体，避免整图重复拼接。详见 [素材克隆数量规则](references/ui-and-image-editing.md#match-the-count-to-the-input)。

仅在需要润色时使用 `asset-clone-prompt --clone-count 4 --prompt "..."`，它通过同一 API 的 `prompt_only=true` 返回提示词，不生成图片。润色会将基础句数量改为 `--clone-count`，不适合图内物体数与格数不同的情况；检查返回内容后传给 `asset-clone-run --prompt "..."` 即可。
万能编辑 `--multi-pixelation` 返回三张像素化结果，不额外收费。`--regional-pixelation` 默认启用多重像素化，可用 `--no-multi-pixelation` 单独关闭；不分区时也可单独开启。

HD hex 公开 `--mode standard`（默认）和 `tetraploid`。七倍体与 Image2 暂时关闭。

Image2.5 通用生成支持 `--remove-bg-method none|standard`，默认 `none`，与网页去背景开关一致。开启后尝试原生透明 PNG，免费；失败则保留原背景、不后处理、不扣附加费。万能编辑选择 Image2.5 时同样免费，高级抠图不可用。重新打开项目或轮询原任务不会再次提交生成。

### Animation Edit

`meowa-animation-run --resolution 1080p` keeps the 1080P Fast route (30/35 generation credits for Standard/Detailed at 1–2 seconds (35/40 at 3–4 seconds)). `--resolution 1080p_full` selects the original 480P/720P model and prompt format at 1080P with 20/30 steps (40/45 generation credits at 1–2 seconds; 45/50 at 3–4 seconds). Both options default to no background removal; 480P/720P remain unchanged.

The Animation Edit tab has a required MP4/animated GIF/WebP reference and an optional static appearance image.
`meowa-animation-edit-prompts --video-file motion.webp --edit-intent 'Replace the character' [--image-file panda.png]`
returns three reviewable strings. Pass the reviewed `--edit-intent`, `--video-description` and `--image-description`
to `meowa-animation-edit-run` with the same media. Descriptions start empty; generation requires edit intent and video content, plus image content with an image reference. Polishing is manual and optional.
References are limited to 4.5 seconds. Output duration is selected automatically: up to 2 seconds → 16 frames, up to 3 seconds → 24 frames, up to 4.5 seconds → 32 frames (4–4.5 seconds stay on the 4-second tier). Generation uses 56/73/90 frames at 24fps; final media uses 8fps. Detailed quality, Pixel/480p and standard removal are defaults. Generation costs 15 credits for 2 seconds or 20 for 3–4 seconds; removal adds 5 per batch, and HD 720p adds 10. Only final media is downloaded.

Video-reference editing: both `meowa-animation-edit-prompts` and `meowa-animation-edit-run` accept `--background-color '#RRGGBB'` (default `#ffffff`). The same color fills transparent pixels in every reference-animation frame and the appearance image; opaque pixels are unchanged. Use the same color for polishing and generation. Background filling adds no credits.

Nano Banana exposes one product model. Generation uses Nano Banana 2.1. Generation costs 10/20/40 credits at 1K/2K/4K. Each reference image adds 2 credits.

HD frame animation: `meowa-animation-run` and `meowa-animation-edit-run` accept `--auto-scale-to-input` (default off). It restores the final WebP to the input dimensions using smooth scaling, preserves the original as a second WebP, and adds no credits. With background removal, only the final transparent animation is scaled.


Final downloads use the server-selected URL, including the domestic media domain. Re-query an existing successful job to obtain its current route; never guess a replacement hostname. Small image downloads share a 45-second budget across at most three attempts, and files are saved only after a complete media response. Large media uses bounded inactive reads. `general-image-run` mirrors the web model selector (default Image2.5, Standard, 1K, 1:1, no background removal); `general-image-poll` resumes the original job. Model-specific legacy commands retain the same requests. The runner is statically distributed; there is no remote bootstrap execution.

Domestic ready final files may use `media-cn.meowjito.com`; legacy `media.meowjito.com` links remain valid. Follow the exact server-returned final URL and re-query the job to refresh its route. No storage or provider option is required.
# Image expansion

`image-expander-run --target-coord ROW COL --neighbor-left left.png --custom-prompt "Continue the road"` mirrors the canvas grid. Project/chat context is created automatically; reuse the printed IDs with `--project-id` / `--thread-id` for later tiles of the same map. Supply one to four neighbor images (`--neighbor-top/left/right/bottom`), or `--source-image` for an initial cardinal target. Defaults: HD, 1K, auto aspect ratio, top-down-60 view, Nano Banana, normal speed, Detailed Image2 quality (`medium`), 20% overlap, 10% feather. `--basic-prompt` follows the selected view; `--custom-prompt` defaults to empty. `--image2-quality low/medium/high` means Standard/Detailed/Ultimate and applies to GPT Image2.

`image-expander-prompt --project-id PROJECT --source-image map.png --prompt "Continue the road" --direction top-right` supports all cardinal and diagonal directions. Generation saves declared final target tiles only. See `references/maps-tiles-and-textures.md` and `--help` for the full parameter contract.

`image-expander-export --project-id PROJECT --tiles-json tiles.json --aspect-ratio 1:1 --export-kind assembled` mirrors canvas image export; `--export-kind split` exports the selected final tile archive. The JSON list contains canonical `coord`, `asset_id` and optional `display_feather` facts (`range_percent` defaults to 3; `top/right/bottom/left` default to 0). Coordinates and assets refer to the same project input references as the canvas. Match the map’s mode, resolution, resolved aspect ratio, generation provider and overlap when exporting.

`--export-kind godot` creates a Godot 4 scene with final textures split into bounded chunks and the same positions, paint order, display feather and pixel/HD sampling as the canvas. Extract the archive as a Godot 4 project and open `project.godot`; its main scene is `scenes/image_expansion.tscn`. This avoids allocating one giant combined image.

## New-media storage preference

Use `media-storage-get` to read the account preference. Use `media-storage-set --media-storage-site auto|domestic|overseas` to change it; omitting the option sets `auto`. This is the shared storage and download preference for web and API clients. Automatic uses the same mainland-IP rollout cohort for reads and new writes. Domestic writes new assets to domestic storage and prefers domestic downloads, falling back to the same authorized GCS original if the domestic copy is unavailable. Authorized legacy private assets may create a verified domestic copy before reading; originals stay in place. Missing public copies retain the original URL. Downloads fail only when no available authorized copy exists; OSS-only assets have no inferred GCS copy.

Two-head Spine uses GPT Image 2 (`image-2`, default) or GPT Image 2.5 (`image-2.5`). `--quality standard/detailed/ultimate` selects a 25/35/55-credit package permitting at most 6/8/12 logical image calls, including appearance reference and repairs. Every image is generated at Standard quality; unused calls do not change the fixed package price. Export size does not add credits. The four-head template and existing part-edit/full-reskin commands retain their original model and pricing contracts.

`spine-editor-open --project-id ID --node-id ID`: opens the equivalent full web Spine editor; the browser handles canonical keyframe and rebind requests. No API key is required to build the URL; the website enforces project access.


默认动画入口与网页主面板一致：`meowa-animation-run`（16 帧、Pixel、480P）。旧引擎用 `animate-run`，多关键帧用 `keyframes-run`，两者并非新版动画的别名。旧引擎省略图像类型时按输入尺寸选择：不超过 256×256 为 Pixel，否则 HD；显式选择保持不变。Standard 帧数为 4/6/8/10/12/16，Advanced 为 3–16 的任意整数。

生成任务受理后会立即输出 ID。中断后用 `workflow-poll --job-id ID --workflow-id image_edit` 等恢复原任务，workflow ID 对照表见 [任务恢复](references/running-and-outputs.md#polling-and-recovery)。自定义 workflow 用 `custom-workflow-poll`，Spine 用 `spine-poll`；这些命令只读原任务，不会重新生成。扩图和自定义 workflow 首次运行不再要求手填项目／会话 ID；后续操作复用打印出的 ID。

Image2.5 的 `standard` 去背景附加费为零，但生成和参考图仍计费；原生透明失败会保留背景，不会自动转付费抠图。适合生成透明角色、道具、图标和 UI 素材；已有图片经过编辑仍属于一次生成，不能承诺像素完全不变。通用生成需显式开启 `--remove-bg-method standard`；素材克隆、HD GEN、UI 生成默认已开启，万能编辑需选 Image2.5。详见 [透明素材技巧](references/pixel-and-hd-assets.md#image25-transparent-asset-tips)。
