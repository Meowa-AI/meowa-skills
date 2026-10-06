# Meowa CLI 快速开始

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
通用图片任务分别使用 `nano-banana-poll` 和 `image-2-poll`。恢复命令只轮询原任务，
不会重新提交或再次扣费。必须复制整个 `skills/game-assets` 目录，不能只替换
`SKILL.md` 或 `meowart_api.py`。

```bash
python3 skills/game-assets/meowart_api.py --help
python3 skills/game-assets/meowart_api.py nano-banana-poll \
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

### 通用生成 Image 2.5

`image-2.5-run --prompt "..."` 使用 Image 2.5 Sunburst；默认 `--quality standard`。
质量仅支持 `standard/detailed/ultimate`，对应网页 普通/精细/极致 与 canonical `low/medium/high`。
`--resolution 1K|2K` 默认 1K；`--aspect-ratio` 默认 1:1，支持 1:1、3:4、4:3、9:16、16:9。
可重复 `--reference-image` 传参考图；失败或中断用 `image-2.5-poll --job-id ...` 恢复，勿重复提交。
1K 基础积分为 1/5/10，2K 为 2/10/20；每张参考图另加 2 积分，由服务端结算。

通用生成默认使用 Image2.5（`image-2.5-run`）。万能编辑高清模式默认使用 Image2.5、2K；像素模式默认不变。万能编辑支持 `image-edit-run --generation-model image-2.5`，参数与 `image-2` 相同。普通／精细／极致基础积分：1K 为 1/5/10，2K 为 2/10/20；每张参考图 +2。Image2.5 去背景免费，只提供普通抠图；失败则不去背景、不扣附加费。分区像素化沿用现有附加费。

素材克隆使用 `asset-clone-run` 和 `/api/workflows/asset_clone/run`。`--clone-count` 可选 1、4、9、16、25、36，返回完整网格图而不自动切分。多张参考图必须同尺寸；尺寸不一致时使用 `--cell-width`、`--cell-height` 和 `--fit-mode pad|crop` 居中处理，不缩放。像素模式默认分区量化与多重像素化，像素缩放比例低于 2、高清缩放比例低于 0.5 时提交前拒绝。像素和高清模式均默认 Image2.5、1K、精细画质；Nano Banana 固定普通画质，默认不去背景；Image2.5 默认去背景。背景选项只有 `none` / `standard`。

`asset-clone-prompt --prompt "..."` 使用同一个 API 的 `prompt_only=true` 单独润色提示词，不生成图片。将返回的提示词传给 `asset-clone-run --prompt "..." --skip-prompt-optimization` 可直接使用；不带该标志时生成阶段会运行提示词优化。默认提示词为「参考图 1 的布局，生成一些不同外观的美术资产，保持美术风格一致。」
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
