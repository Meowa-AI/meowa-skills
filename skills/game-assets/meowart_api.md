# Meowa API 简明文档

常用脚本：

- `skills/meowart_api.py`

这个文档只保留最常用的调用方式，作为快速入口。
需要确认完整 CLI 参数时，可以查看脚本的 `--help`。

重要 endpoint 规则：

- 不存在 `POST /generate` 或 `POST /api/generate`。
- 像素资产生成固定使用 `POST /api/pixel-gen`，再用 `GET /api/pixel-gen/jobs?id=<api_job_id>` 轮询。
- 高清资产生成固定使用 `POST /api/hd-gen`，再用 `GET /api/hd-gen/jobs?id=<api_job_id>` 轮询。
- 通用 Gemini 代理使用 `POST /api/gemini/...` 或封装命令 `gemini-generate-content`。
- 如果调用方收到 404 且路径是 `/generate`，先修正 endpoint，不要把它解释为 API key 无效。

可用能力概览：

- `credits-balance`：查询当前账号剩余 credit，适合在批量生成前先确认额度是否充足。
- `pixel-gen-run`：像素资产默认入口。基于模板生成像素图片，适合角色、怪物、物件、道具、icon、UI 小图标这类固定尺寸 Sprite；命令会自动提交、轮询并保存结果。某些模板支持批量生成 N 个 Sprite，但是费用不变。
- `hd-gen-run`：高清非像素资产入口。基于 HD 模板生成透明 PNG 角色、图标、物品包等；命令会自动提交、轮询并保存结果。
- `gemini-generate-content`：通用生成入口（nano banana），适合非像素概念图、高清/插画资产、大幅完整背景概念稿、UI 整体视觉稿。不要把它作为像素 sprite、像素角色、像素道具、像素 icon 的默认入口；像素资产只有没有合适模板或用户明确不用模板时才 fallback 到这里。
- `self-loop-run`：基于现有图片生成 self-loop 无缝循环图。目前支持横向或纵向无缝拼接，适合用于横版卷轴背景、纵向场景和可重复平铺的纹理。
- `texture-gen-run`：生成单张像素纹理 texture，适合水面、石块、墙面、木板、岩浆等可平铺地表或材质；默认追加四方连续后处理。
- `tileset-gen-run`：生成 dual-grid 15 地形过渡 tileset，适合草地/水面、石地/岩浆等前景和背景 terrain 过渡。
- `map-reference-search` / `map-reference-download`：搜索并下载 Meowa 内置地图 preset 图片。地图类需求必须先查这里；如果已有合适图片，直接用 preset，不要再生成。
- `isometric-gen-run`：生成像素等角地图块，后端 workflow 为 `pixel_isometric_gen`。
- `hex-isometric-gen-run`：生成像素六角等角地图块，后端 workflow 为 `pixel_hex_isometric_gen`。
- `hd-isometric-gen-run`：生成高清等角地图块，后端 workflow 为 `hd_isometric_gen`。
- `hd-hex-isometric-gen-run`：生成高清六角等角地图块，后端 workflow 为 `hd_hex_isometric_gen`。
- `remove-background-run`：对现有图片做去背景处理
  - 像素图片使用 `pixel` 模式，只支持去白色背景。支持任意尺寸输入，最好提前做过 pixelate，且不需要提前缩放到 nano banana尺寸。
  - 普通图片使用 `hd`，支持任意背景色
- `pixelate-run`：把较大的图片重新收敛成更干净的像素风输出，适合在 AI 先生成大图后，将其变为完美像素的 Spite。
- `animate-run`：基于单张角色图生成动作动画，适合做角色待机、跑步、跳跃、弹跳这类短循环动画。
- `sound-run` / `sfx-run`：生成短音效，适合 UI 点击、攻击、拾取、爆炸、技能、环境短音；支持单条、音效包、同音效多版本。
- `music-run`：生成结构化音乐描述，可选继续生成音乐音频；适合游戏 BGM、主题曲、场景音乐方向测试。

## 0. 命令选择

- 明确要像素图、pixel art、sprite、角色、怪物、道具、物品、icon、UI 小图标时：先执行 `pixel-gen-template-info`，再用合适模板执行 `pixel-gen-run`。
- 明确要高清非像素角色、透明 PNG、高清 icon 或物品包时：先执行 `hd-gen-template-info`，再用 `hd-gen-run`。
- 明确要可平铺 texture / material tile / 地表纹理时：执行 `texture-gen-run`。
- 明确要 terrain tileset / dual-grid 地形过渡图时：执行 `tileset-gen-run`。
- 明确要地图块、isometric tile、hex tile、HD isometric map、地图 preset 时：先执行 `map-reference-search`。命中合适结果时执行 `map-reference-download` 或 `map-reference-search --download`，直接交付 preset；只有没有合适 preset 时才执行对应的 `*-isometric-gen-run` 生成。
- 明确要 SFX、音效、UI click、攻击、拾取、爆炸、技能音时：执行 `sound-run` 或 `sfx-run`。
- 不要因为需求写了“人物”“背景”“场景”就直接使用 `gemini-generate-content`。如果最终要求是像素资产，`pixel-gen-run` 优先。
- 只有非像素概念图、高清插画、完整大背景概念稿、UI 整体视觉稿，或明确没有合适 pixel template 时，才使用 `gemini-generate-content`。
- 像素资产 fallback 到 `gemini-generate-content` 后不能直接交付：继续跑 `pixelate-run`，需要透明图时再跑 `remove-background-run --method pixel`，并检查尺寸和透明通道。

## 1. 鉴权

在使用 Meowa API 前，先登录 [https://meowa.ai/#/api-keys](https://meowa.ai/#/api-keys)，然后点击左侧的 `Create API Key` 按钮，创建一个 token。

默认使用真实用户 API key：

```http
Authorization: Bearer ma_live_xxxxxxxxxxxxxxxxxxxx
```

环境变量里只放 `ma_live_...` 本身，不要把 `authenticate:` 这类标签一起复制进去。

项目调试或后端自部署环境也支持开发者鉴权：

```http
X-Dev-Key: xxxxxxxxxxxxxxxxxxxx
```

推荐先设置环境变量：

```bash
export MEOWART_API_KEY="ma_live_xxxxxxxxxxxxxxxxxxxx"
```

`skills/meowart_api.py` 在未显式传入 `--api-key` 时，会自动读取这个环境变量。
如果传入 `--dev-key`，或设置 `MEOWART_DEV_KEY` / `DEV_API_KEY`，脚本会改用 `X-Dev-Key` 调用后端。读取顺序优先级是：

1. `--dev-key`
2. `MEOWART_DEV_KEY` 或 `DEV_API_KEY`
3. `.env` 里的 `MEOWART_DEV_KEY` 或 `DEV_API_KEY`
4. `--api-key`
5. `MEOWART_API_KEY`
6. `.env` 里的 `MEOWART_API_KEY`

也可以写入当前目录、`skills/` 目录或项目根目录的 `.env`：

```bash
MEOWART_API_KEY="ma_live_xxxxxxxxxxxxxxxxxxxx"
MEOWART_DEV_KEY="xxxxxxxxxxxxxxxxxxxx"
```

推荐优先使用环境变量或 `.env`，尽量不要在每次调用 API 时都显式传入 `--api-key`，因为这样不够安全，容易出现在 shell 历史、日志或截图里。

如果运行时找不到 `MEOWART_API_KEY`，应先提醒用户配置 key；需要时也可以直接帮用户打开 API key 页面：

```bash
open "https://meowa.ai/#/api-keys"
```

这样用户可以立刻前往创建或查看自己的 API key。

## 2. 安装

```bash
pip install requests
python3 skills/meowart_api.py --help
```

## 2.1 Bootstrap 自动更新

`meowart_api.py` 自带 bootstrap wrapper。正常执行命令时，它会先检查远端
`meowart_api.bootstrap.json`，如果发现更高版本的 CLI runner，会下载新的
`meowart_api.py` 到本机缓存，校验 SHA-256 后再执行缓存 runner。检查或下载失败
不会中断当前任务，会自动回退到 skill 内置脚本。

常用命令：

```bash
python3 skills/meowart_api.py bootstrap-status
python3 skills/meowart_api.py bootstrap-status --check
python3 skills/meowart_api.py --no-bootstrap credits-balance
python3 skills/meowart_api.py --bootstrap-force credits-balance
```

常用环境变量：

- `MEOWART_BOOTSTRAP=0`：关闭本次/当前环境的 bootstrap 检查。
- `MEOWART_BOOTSTRAP_MANIFEST_URL=...`：改用自定义 manifest 地址。
- `MEOWART_BOOTSTRAP_CACHE_DIR=...`：改用自定义缓存目录。
- `MEOWART_BOOTSTRAP_VERBOSE=1`：打印 bootstrap 诊断信息。
- `MEOWART_BOOTSTRAP_TIMEOUT=2`：设置 manifest/runner 下载超时时间，单位秒。

这个机制更新的是 CLI runner。`SKILL.md` 的触发描述和路由说明仍然是 Codex
启动时加载的内容；如果这些说明发生变化，仍需要执行 `skills update` 或重新安装
skill，并重启 Codex。

## 2.2 动态 Skill 指南

`SKILL.md` 是稳定 loader。真正会频繁变化的命令选择策略、API 说明、模板建议
通过动态指南获取：

```bash
python3 skills/meowart_api.py skill-doc --task "生成 64x64 像素道具"
python3 skills/meowart_api.py skill-doc --topic pixel-gen
python3 skills/meowart_api.py skill-doc-status --check
```

`skill-doc` 默认请求 Meowa 后端的公开只读文档接口，并缓存到
`~/.cache/meowa-skills/game-assets/docs/`。如果网络不可用、接口异常或校验失败，
会自动回退到当前 bundled `meowart_api.md`。

## 3. Credits

```bash
python3 skills/meowart_api.py credits-balance
```

## 4. General Image Generation

For non-pixel concepts, high-resolution illustration, full-scene background concepts, and broad UI mockups, use `generateContent`:

```bash
python3 skills/meowart_api.py \
  gemini-generate-content \
  --text "Write a one-line description of a cream sofa"
```

Reference images can be passed as inline Gemini image parts. `--image-file` can be repeated; `--reference-image` and `--reference-file` are aliases:

```bash
python3 skills/meowart_api.py \
  gemini-generate-content \
  --text "Generate a matching 16:9 background concept using this character's palette." \
  --image-file ./reference_character.png \
  --generation-config '{"responseModalities":["TEXT","IMAGE"],"imageConfig":{"aspectRatio":"16:9","imageSize":"2K"}}'
```

If you need to customize the path or request body, check the `gemini-*` subcommands in `skills/meowart_api.py`.

## 5. 像素 Sprite / 角色 / 道具 / Icon 生成

`pixel-gen` 是像素资产的默认入口。最常用的命令是 `pixel-gen-run`，它会自动完成提交、轮询和结果下载。
底层 endpoint 是 `POST /api/pixel-gen`，不是 `/generate`。

```bash
python3 skills/meowart_api.py \
  pixel-gen-run \
  --template-name "pixel_character_large" \
  --requirement "A fox rogue with twin daggers" \
  --template-config '{"direction":"left"}'
```

常用参数：

- `--template-name`
- `--requirement`
- `--template-config '{}'`
- `--dry-run`
- `--output-dir ./outputs/pixel_gen`
- `--reference-file ./reference.png`

`--dry-run` 只打印计划提交的 request 和预计输出目录，不提交任务、不消耗额度，也不需要 API key。它适合在正式生成前确认模板、尺寸、输出路径是否符合预期。

如果需要让服务端根据用户参考图解析需求或保持色彩/造型倾向，可以传 `--reference-file`。该参数会作为 `/api/pixel-gen` 的 `reference_file` multipart 字段上传。

现在脚本也兼容把通用参数写在子命令后面，例如 `--api-base`、`--api-key`、`--timeout`、`--max-wait`、`--poll-interval`、`--output-dir`、`--work-dir`、`--no-download`、`--insecure`。下面两种写法都可以：

```bash
python3 skills/meowart_api.py --timeout 120 --output-dir ./outputs pixel-gen-run ...
python3 skills/meowart_api.py pixel-gen-run --timeout 120 --output-dir ./outputs ...
```

`*-run` 命令在提交成功后，也会立刻打印：

- `planned_output_dir=...`：预计保存目录
- `submitted api_job_id=...`：服务端任务 id

### requirement 的写法建议

这里最容易犯错的一点是：`--requirement` 不等于“最终发给模型的完整 prompt”。

### 模板选择建议

- 物品、Icon、小动物：推荐优先使用 `food`、`object` 模板，单次通常可以生成 `8` 个 `64x64` 像素对象。
- 人物、主角、怪物角色：推荐优先使用 `pixel_char` 模板，单次通常可以生成 `2` 个 `128x128` 对象。
- 具体模板名称、输出尺寸和数量以 `pixel-gen-template-info` 返回为准；如果模板列表变化，优先相信接口返回。
- 批量生成时，可以在 `--requirement` 里分别描述多个对象的外观，也可以一句话描述整体需求，让服务端按模板数量补充变体。尽量一次性生成模板支持的最大数量，因为价格和质量通常没有区别，多生成一些更方便挑选。

- 模板会先根据自己的默认配置决定一次生成几个对象，例如 `cat_2` 默认是 `8` 个。
- 服务端会结合模板的 `target_count`，把你的 `requirement` 解析并包装成真正的生成 prompt。并对你的 prompt 进行一定的润色或精简。
- 所以对于 `cat`、`cat_2` 等批量模板，`--requirement` 更适合写“这一批要生成什么”，而不是写成“生成一只……白色背景……完整角色……”这种单图式 prompt。

更具体地说：

- 如果模板默认就是批量生成 `8` 个 sprite，那么 `--requirement "猫咪"` 不是“只生成 1 只”，而是会被服务端理解成“生成 8 个猫咪”。
- 如果你想让 8 个 sprite 更有区分度，应该在 `requirement` 里直接描述一批变体，例如：`三花、橘猫、奶牛猫、暹罗、英短、美短、狸花、纯白猫，每一只都带着不同的帽子。`
- 不要在 `requirement` 里重复写模板已经隐含的约束，例如很多 `pixel-gen` 模板本身就默认是白底/透明底，这种情况下再写“白色背景”通常是冗余的，只做内容的描述，一切的其他部分模板内部都会自动化掉。
- 不要把“生成一个角色”的说法机械地套到批量模板上；单体模板和批量模板的 `requirement` 写法应该不同。

推荐示例：

```bash
python3 skills/meowart_api.py \
  pixel-gen-run \
  --template-name "cat_2" \
  --requirement "三花、橘猫、奶牛猫、暹罗、英短、美短、狸花、纯白猫"
```

如果你只是想快速试一下模板是否能跑通，甚至可以更短：

```bash
python3 skills/meowart_api.py \
  pixel-gen-run \
  --template-name "cat_2" \
  --requirement "猫咪"
```

此时服务端仍会按照该模板默认的 `target_count` 去生成一整批结果，而不是只生成 1 张。

如果你只是想先看有哪些模板，可以先执行：

```bash
python3 skills/meowart_api.py pixel-gen-template-info
```

如果模板信息里写了 `supports_direction: true`，那么这个模板支持设置朝向。
设置方式不是单独传 `--direction`，而是放在 `--template-config` 里，例如：

```bash
python3 skills/meowart_api.py \
  pixel-gen-run \
  --template-name "pixel_character_large" \
  --requirement "A fox rogue with twin daggers" \
  --template-config '{"direction":"left"}'
```

可以先用 `pixel-gen-template-info` 查看模板返回的 `directions` 和 `default_direction`，再决定传什么值。

如果需要查看完整命令列表，可以运行：

```bash
python3 skills/meowart_api.py --help
```

## 6. HD 资产生成

HD Gen 是非像素高清资产入口，适合透明 PNG 角色、高清 icon、物品包等。

先查看可用模板：

```bash
python3 skills/meowart_api.py hd-gen-template-info
```

提交并等待高清生成：

```bash
python3 skills/meowart_api.py \
  hd-gen-run \
  --template-name "hd_char_1" \
  --requirement "A cheerful fantasy alchemist girl with green cloak" \
  --template-config '{"direction":"front"}' \
  --output-dir ./outputs/hd_alchemist
```

常用参数：

- `--template-name`
- `--requirement`
- `--template-config '{}'`
- `--reference-file ./reference.png`
- `--reference-files ./ref2.png`，可重复
- `--hd-remove-bg-mode batch|single`
- `--output-dir ./outputs/hd_asset`

已经有任务 id 时：

```bash
python3 skills/meowart_api.py hd-gen-poll --api-job-id <api_job_id>
python3 skills/meowart_api.py hd-gen-download --api-job-id <api_job_id> --output-dir ./outputs/hd_download
```

## 7. Remove Background

像素图通常用：

```bash
python3 skills/meowart_api.py \
  remove-background-run \
  --image-file ./pixel_image.png \
  --method pixel
```

高清图使用：
```bash
python3 skills/meowart_api.py \
  remove-background-run \
  --image-file ./hd_image.png \
  --method hd
```



## 8. Pixelate

```bash
python3 skills/meowart_api.py \
  pixelate-run \
  --image-file ./input.png
```

这个命令适合先把较大的 AI 图收敛成更干净的小尺寸像素图，再继续做去背景等处理。

## 9. Self-Loop Image Generation

```bash
python3 skills/meowart_api.py \
  self-loop-run \
  --image-file ./tile.png \
  --direction horizontal
```

`self-loop-run` 默认使用 `basic` 模式，适合单方向横向或纵向补缝。如果需要四向连续的完整循环图，使用 `full` 模式：

```bash
python3 skills/meowart_api.py \
  self-loop-run \
  --image-file ./tile.png \
  --mode full
```

常用参数是 `--image-file`、`--direction` 和 `--mode`。横向卷轴背景通常使用 `--direction horizontal`，纵向场景使用 `--direction vertical`，四向平铺素材使用 `--mode full`。

## 10. Texture Generator

生成单张可平铺像素纹理：

```bash
python3 skills/meowart_api.py \
  texture-gen-run \
  --prompt "mossy cracked stone floor" \
  --texture-name "砖墙" \
  --texture-name "破碎小石块" \
  --output-dir ./outputs/mossy_stone_texture
```

常用参数：

- `--prompt`：纹理需求。
- `--texture-name`：参考纹理名，可重复，也可以逗号分隔。内置参考包括 `水面`、`带气泡的岩浆`、`砖墙`、`木板`、`破碎小石块`、`金属板`、`凝固中的熔岩`、`火山岩带熔岩纹理`。
- `--padding-mode no_padding|padded`
- `--edge-fill-pixels 1`
- `--no-self-loop`：跳过默认四方连续后处理。

## 11. Tileset Generator

生成 dual-grid 15 terrain tileset：

```bash
python3 skills/meowart_api.py \
  tileset-gen-run \
  --prompt "lush grass foreground plus shallow blue water background" \
  --output-dir ./outputs/grass_water_tileset
```

可选使用已有纹理作为前景和背景参考：

```bash
python3 skills/meowart_api.py \
  tileset-gen-run \
  --prompt "mossy stone foreground plus lava background" \
  --foreground-texture ./stone_texture.png \
  --background-texture ./lava_texture.png \
  --texture-reference-mode white_region_fill \
  --output-dir ./outputs/stone_lava_tileset
```

常用参数：

- `--tileset-mode dual-grid-15`
- `--foreground-texture ./foreground.png`
- `--background-texture ./background.png`
- `--texture-reference-size 64`
- `--texture-reference-mode white_region_fill|texture_block_fill`

## 12. Map Presets And Isometric Map Generators

地图生成前必须先搜索内置 preset。命中合适图片时直接下载复用：

```bash
python3 skills/meowart_api.py \
  map-reference-search \
  --query "ocean water" \
  --workflow-id pixel_isometric_gen \
  --tile-size 1x1 \
  --limit 8
```

直接下载搜索结果：

```bash
python3 skills/meowart_api.py \
  map-reference-search \
  --query "desert" \
  --workflow-id pixel_hex_isometric_gen \
  --download \
  --limit 6 \
  --output-dir ./outputs/desert_hex_presets
```

也可以按 preset id 下载：

```bash
python3 skills/meowart_api.py \
  map-reference-download \
  --preset-id pixel-isometric-xxxxxxxxxxxxxxxx \
  --output-dir ./outputs/map_presets
```

没有合适 preset 时再生成新的等角地图块。像素等角小地块通常需要两张参考图：

```bash
python3 skills/meowart_api.py \
  isometric-gen-run \
  --prompt "two cozy forest RPG isometric pixel tiles with mossy stones" \
  --reference-image ./preset_01.png \
  --reference-image ./preset_02.png \
  --similar-tiles \
  --output-dir ./outputs/forest_isometric
```

像素六角等角地图块：

```bash
python3 skills/meowart_api.py \
  hex-isometric-gen-run \
  --prompt "two ocean hex isometric pixel tiles with coral and shallow water" \
  --reference-image ./hex_01.png \
  --reference-image ./hex_02.png \
  --similar-tiles \
  --output-dir ./outputs/ocean_hex
```

高清等角地图块可以直接用后端模板参考图；大块模式可传 2 到 4 张参考图：

```bash
python3 skills/meowart_api.py \
  hd-isometric-gen-run \
  --prompt "modern hospital block with clean roads and plaza" \
  --template modern \
  --mode standard \
  --similar-tiles \
  --output-dir ./outputs/modern_hd_isometric
```

高清六角等角地图块：

```bash
python3 skills/meowart_api.py \
  hd-hex-isometric-gen-run \
  --prompt "clean sci-fi hex platform with glowing edge lights" \
  --template clean_scifi \
  --mode standard \
  --similar-tiles \
  --output-dir ./outputs/scifi_hd_hex
```

常用参数：

- `map-reference-search --query "关键词"`：搜索内置 preset，关键词可用 `ocean`、`desert`、`grassland`、`modern`、`clay`、`hex` 等。
- `--workflow-id pixel_isometric_gen|pixel_hex_isometric_gen|hd_isometric_gen|hd_hex_isometric_gen|tileset_gen`
- `--template-id ocean|desert|grassland|modern|clay|clean_scifi|...`
- `--tile-size 1x1|2x2|7-cell|tileset-template`
- `--asset-kind reference|template`
- `isometric-gen-run --mode standard|edit|tetraploid|road`
- `hex-isometric-gen-run --mode standard|edit|tetraploid|heptaploid`
- `hd-isometric-gen-run --mode standard|tetraploid|style_quad`
- `hd-hex-isometric-gen-run --mode standard|tetraploid`

## 13. Animate

```bash
python3 skills/meowart_api.py \
  animate-run \
  --image-file ./sprite.png \
  --prompt "slime bouncing" \
  --is-pixel \
  --output-format webp
```

默认示例只展示像素风动画。`--output-format` 常见可选值有 `webp`、`gif` 和 `spritesheet`：

- `webp`：默认选项，适合大多数网页展示
- `gif`：兼容性更直观，适合简单预览或分享
- `spritesheet`：输出序列帧拼图，适合接入游戏或自行控制播放

`animate-run` 会自动提交、轮询并下载生成结果。如果已经有任务 id，也可以用 `animate-poll --api-job-id <id>` 继续等待和下载。

## 13. Sound Effect Generator

生成单条短音效：

```bash
python3 skills/meowart_api.py \
  sound-run \
  --prompt "soft wooden UI button click for cozy pixel RPG" \
  --duration 1 \
  --output-dir ./outputs/ui_click
```

生成一组音效包：

```bash
python3 skills/meowart_api.py \
  sound-run \
  --prompt "8-bit fantasy combat sound pack: sword slash, shield block, coin pickup, potion drink" \
  --sound-pack \
  --count 4 \
  --duration 1 \
  --output-dir ./outputs/combat_sfx_pack
```

常用参数：

- `--duration`：`0.5` 或 `1` 到 `10` 秒整数。
- `--loop`：请求可循环短音。
- `--sound-pack --count N`：生成 N 条不同音效。
- `--variants --count N`：生成同一音效的 N 个版本。
- `--temperature`：映射 ElevenLabs prompt influence，范围 0 到 1。
- `--no-normalize-volume`：跳过默认峰值归一化。
- `--provider-api-key`：临时传 ElevenLabs key；优先使用后端环境变量。

已经有任务 id 时：

```bash
python3 skills/meowart_api.py sound-poll --api-job-id workflow-elevenlabs_generator-xxxx
```

## 14. Music Generator

只生成结构化音乐 prompt，不生成音频：

```bash
python3 skills/meowart_api.py \
  music-run \
  --prompt "A cozy pixel RPG village theme with flute, kalimba, soft strings, loop-friendly"
```

生成 30 秒 demo 音频：

```bash
python3 skills/meowart_api.py \
  music-run \
  --prompt "A cozy pixel RPG village theme with flute, kalimba, soft strings, loop-friendly" \
  --audio-generate \
  --demo
```

可选传参考图，参数可以重复：

```bash
python3 skills/meowart_api.py \
  music-run \
  --prompt "Music inspired by this scene" \
  --reference-image ./scene.png
```

常用参数：

- `--prompt`：音乐需求；如果传了参考图，可以为空。
- `--reference-image`：参考图片，可重复。
- `--audio-generate`：实际生成音乐音频；不传时只生成音乐描述。
- `--demo`：配合 `--audio-generate` 使用，生成低成本 30 秒试听。
- `--max-wait` / `--poll-interval`：控制轮询等待。

`music-run` 会保存提交响应、最终 job 响应，并在音频生成成功时下载返回里的音频文件。已经有 job id 时可以用：

```bash
python3 skills/meowart_api.py music-poll --api-job-id workflow-music_generator-xxxx
```

## 15. 输出目录

这些 `*-run` 命令默认会在脚本目录下创建：

```bash
./.meow_art/<timestamp>_<command>/
```

通常会保存：

- `meta.json`
- `submit_response.json`
- `job_response.json`
- 下载得到的 PNG、GIF、WebP、spritesheet、MP3、WAV、OGG 等输出文件

如需自定义目录，可使用 `--work-dir` 或 `--output-dir`。更细的行为差异直接看脚本源码即可。
