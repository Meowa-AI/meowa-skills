# Meowa CLI 快速开始

这份文档只负责安装、Meowa 账户认证和首次运行。具体美术能力、参数选择和工作流协作方式由 `SKILL.md` 及 `references/` 中的对应模块说明。

## 安装

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
