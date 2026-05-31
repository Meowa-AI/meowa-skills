---
name: game-assets
description: Create, edit, and pipeline game assets with MeowArt for pixel sprites, HD assets, backgrounds, UI mockups, seamless loops, texture tiles, dual-grid tilesets, background removal, pixel cleanup, simple animation, sound effects, and music/BGM generation. Use when Codex needs to produce or refine game art or audio in this project, especially when choosing MeowArt commands, sizing canvases, selecting templates, generating music or SFX audio, or turning generated assets into game-ready files.
---

# Meowart Game Asset

## 快速入口

- 需要先判断用哪个命令、参数怎么写、输出会落到哪里时，先读 [`meowart_api.md`](./meowart_api.md)。
- 需要确认精确 CLI 参数、请求结构、轮询逻辑、下载逻辑，或者准备扩展脚本时，直接读 [`meowart_api.py`](./meowart_api.py)。
- 需要快速执行资产生成任务时，先看下面的“核心规则”，再按后文的“实战指南”选择具体工作流。
- 需要高清非像素角色、图标、物品包、透明 PNG 时，优先看“HD 资产生成”，通常从 `hd-gen-template-info` 选模板，再用 `hd-gen-run`。
- 需要游戏 BGM、主题曲、场景音乐时，优先看“音乐生成”，通常从 `music-run` 的 prompt-only 模式开始。
- 需要 UI 点击、攻击、拾取、环境、技能等短音效时，优先看“音效生成”，使用 `sound-run` / `sfx-run`。
- 需要可平铺 texture、地表纹理、terrain tileset、dual-grid 地形过渡图时，优先看“Texture / Tileset 生成”，使用 `texture-gen-run` 或 `tileset-gen-run`。
- `meowart_api.py` 默认带 bootstrap 自动更新：正常执行命令前会检查远端 manifest，发现新版 runner 会校验 SHA-256 后执行缓存版本。需要排查时用 `bootstrap-status`；需要关闭时传 `--no-bootstrap` 或设置 `MEOWART_BOOTSTRAP=0`。

## 核心路由规则

- 不要调用裸 `/generate` 或 `/api/generate`。MeowArt 后端没有这两个 endpoint；像素资产提交固定走 `POST /api/pixel-gen`，轮询固定走 `GET /api/pixel-gen/jobs?id=...`。如果看到 404 并提到 `/generate`，优先修正 skill/脚本 endpoint，而不是判断 API key 无效。
- 只要用户目标明确是像素 sprite / 小图标 / 道具 / 角色 / 怪物 / NPC，默认先走 `pixel-gen-template-info` 选模板，再用 `pixel-gen-run`。触发词包括：像素图、pixel art、pixel、sprite、spritesheet、角色、怪物、NPC、道具、物品、icon、UI 小图标、game asset、透明素材。
- 明确要非像素高清角色、高清 icon、高清物品包、透明 HD 资产时，走 `hd-gen-template-info` + `hd-gen-run`，不要退回通用 `gemini-generate-content`。
- 明确要单张可平铺 texture / material tile / 地表纹理时，走 `texture-gen-run`。明确要 terrain tileset / dual-grid 15 tiles / 草地水面过渡图时，走 `tileset-gen-run`。只有“tile”是普通小道具或像素小图标时才走 `pixel-gen-run`。
- 明确要短音效、SFX、UI 点击、攻击、爆炸、拾取、环境音片段时，走 `sound-run`。需要一组音效用 `--sound-pack`，需要同一音效多个抽卡版本用 `--variants`。
- 不要因为需求里出现“背景”“场景”“人物”“自由风格探索”就自动改用 `gemini-generate-content`。如果最终资产需要保持像素网格，`pixel-gen-run` 是默认入口。
- `gemini-generate-content` 只用于非像素概念图、高清/插画资产、大幅完整背景概念稿、UI 整体视觉稿，或明确没有合适 pixel template 且用户接受 fallback 的情况。
- 像素资产 fallback 到通用生成时，必须把它当作中间稿：先用 `gemini-generate-content` 生成白底/固定尺寸图，再用 `pixelate-run` 收敛像素，再按需求用 `remove-background-run --method pixel` 去白底，最后校验尺寸、透明通道和边缘清晰度。
- 如果用户明确“不使用 template”，可以跳过 `pixel-gen-run`，但仍要按上面的 fallback 链路处理，不能把通用生成结果直接当作最终像素资产。


## AI生图基础
- 基本原理：
  - 原理一：输出的图片的各个位置的画风可以做到非常一致，但是不一定能够和输入图一致（输出的各个位置本质上还在一个图上，而输入是经过了深度网络转换）。
  - 原理二：VLM通常有一些默认的输出尺寸，如果输入尺寸和这些尺寸不一致可能有隐含的形变（缩放，裁剪），会产生一些意料之外的情况，尽量避免。
- 常用方法：保证输入和输出相同尺寸，且让参考图和生成的图在一张图上，这样不仅可以严格控制风格一致性，也能精准修改画面的指定位置。
  - 留白生成：在参考图中放上数个参考对象，并留出空白，通过 prompt 引导大模型在空白处生成新的对象。这样确保了参考对象和生成的对象出现在一张画布。基于原理一，这可以让生成的对象的风格严格和参考对象一致。
  - 批量生成：一次性生成 N 个对象，由于这 N 个对象在一张画布上，基于原理一，因此也能确保彼此的风格是一致的。
  - 轮廓生成：先用 python 或者让用户在图片中 Mark 出要修改的区域，然后通过 prompt 引导大模型修改指定位置，或者生成指定轮廓的图。这样可以严格的控制生成出来对象的外形，位置，大小等 （尽量确保输入输出都是标准尺寸，反之隐含的偏移，导致 mark 不准）
  
## 画布尺寸注意事项
使用 AI 生图时，输入输出尺寸是一个非常重要的参数！

### 推荐尺寸
下面这些尺寸可以作为调用 nano banana 时优先采用的标准目标尺寸。调用生图工具时，尽量确保输入输出图片尺寸一致且符合下述尺寸。。

| 比例 | 1k | 2k |
| --- | --- | --- |
| `1:1` | `1024 x 1024` | `2048 x 2048` |
| `3:4` | `896 x 1200` | `1792 x 2400` |
| `4:3` | `1200 x 896` | `2400 x 1792` |
| `2:3` | `848 x 1264` | `1696 x 2528` |
| `3:2` | `1264 x 848` | `2528 x 1696` |
| `9:16` | `768 x 1376` | `1536 x 2752` |
| `16:9` | `1376 x 768` | `2752 x 1536` |
| `1:4` | `512 x 2064` | `1024 x 4128` |
| `4:1` | `2064 x 512` | `4128 x 1024` |
| `1:8` | `352 x 2928` | `704 x 5856` |
| `8:1` | `2928 x 352` | `5856 x 704` |
| `9:21` | `336 x 792` | `672 x 1584` |
| `21:9` | `792 x 336` | `1584 x 672` |

### 最佳实践
- 除非 API 的官方说明明确写明“支持任意尺寸输入，并且不会引入隐含缩放/裁剪问题”，否则最佳实践是先把输入图片整理为模型的标准目标尺寸之一。
- 如果任务是局部修改，而不是整图重绘，那么“输入尺寸 = 输出尺寸”几乎应视为默认前提，且都是 Nano banana 的标准尺寸
- 如果原图不是标准尺寸，先决定是 padding，还是 Crop；不要把这个决定留给模型隐式处理。
- 如果后续还要继续多轮编辑，第一轮就应把画布尺寸固定下来，后面每一轮都保持一致，这样最容易维持对位关系和像素稳定性。
- Sprite 生成：默认使用 meowart api 的 `pixel-gen-run`，生成的 sprite 通常是白色背景或透明背景。只有 fallback 到通用生成时，才需要在 prompt 里明确约束 sprite 背景色为白色，并在生成后继续 `pixelate-run` 和去背景。


## 像素风格注意事项

### 为什么像素图更敏感
- 像素图本质上依赖严格的像素网格，普通图片即使发生轻微缩放很多时候肉眼还能接受，但像素图一旦被错误缩放，边缘、色块和像素颗粒都会被破坏。
- 大模型在做隐含缩放时，采用的通常是双线性采样一类的连续插值（兼容主流的高清图），但对像素图会明显伤害清晰的像素边界。
- 像素图如果必须缩放，原则上应使用邻近采样，而不是双线性或其他平滑插值。
- 因此对于像素资产，最稳妥的做法是先把输入整理到目标尺寸，再要求输出保持同尺寸，确保不要发生缩放。

### 像素风格的最佳实践
- 像素风格图片尽量不要做拉伸，只做整数倍且等比例 resize，且必须使用邻近采样。
- 对像素风格的 sprite，例如角色、物品、icon 通常都是较小尺寸的 `32x32`、`64x64`、`128x128` 这类 `2^n` 的方形尺寸 , 因此`1K` 和 `1024 x 1024`是Sprite 生成的最优解。
- 如果是基于参考图生成，最佳做法是先把参考图 padding 到合适的 `2^n` 方形，再用邻近采样等比例放大到 `1024 x 1024`，送入 nano banana 生成，并继续输出同样的 `1024 x 1024` （2K则是 2048）。 生成完成后，再用邻近采样等比例缩回目标 sprite 尺寸。这样很多情况下即使不依赖完美像素算法，也能得到严格对齐、边界干净的“完美像素”结果。
- 同时，因为像素块天然是 `1:1` 的方形，在 `1:1` 画布里也更容易保持较高的像素块质量。
- 如果是背景图生成等场景，最好一次性生成目标尺寸附近的图，之后稍微 crop 即可，减少缩放导致的像素挤压效应。

## MeowArt API 相关文档

- [`meowart_api.md`](./meowart_api.md)：面向日常使用的快速说明，重点整理了最常用的命令入口、鉴权方式和典型调用示例。适合在已经明确需求后，直接查“该用哪个命令、参数怎么写”。
- [`meowart_api.py`](./meowart_api.py)：实际调用 MeowArt API 的脚本封装，包含各个子命令的参数定义、请求发送、轮询、下载和输出目录处理逻辑。遇到需要更细粒度控制参数、确认底层行为，或者扩展新调用方式时，应直接阅读这个脚本。
- Bootstrap 只更新 CLI runner；`SKILL.md` 的触发描述和路由说明如果发生变化，仍需要用户更新 skill 并重启 Codex 后才能被当前 agent 稳定识别。

## 输出目录规则

- 用户要求一批资产或统一位置时，先创建本次任务专用资产根目录，例如 `./.meowart-test/<task_slug>/` 或项目约定的 `assets/generated/<task_slug>/`；之后所有生成、后处理、动画命令都显式传这个根目录下的子目录作为 `--output-dir`。
- `--work-dir` 是命令日志/元数据目录；`--output-dir` 才是图片、动画、sprite 等资产目录。只有 `meta.json` 的目录通常不是最终资产目录。
- `credits-balance`、`pixel-gen-template-info` 这类查询命令通常只生成 JSON；`gemini-generate-content` 和各类 `*-run` 命令才会下载资源文件。
- `hd-gen-template-info` 只查询模板；`hd-gen-run` 会提交高清生成任务、轮询并下载透明 PNG 或资产包输出。
- `sound-run` / `sfx-run` 会下载 `mp3`/`wav`/`ogg` 等音频文件；如果用 `--sound-pack` 或 `--variants`，通常会有多条音频。
- `texture-gen-run` 会下载单张纹理 PNG，并在开启默认 `--self-loop` 时返回四方连续纹理；`tileset-gen-run` 会下载 dual-grid tileset PNG。
- `music-run` 的 prompt-only 模式通常只保存 `submit_response.json` 和 `job_response.json`；只有传 `--audio-generate` 并成功生成音频时，才会下载 `mp3` 等音频文件。
- 任务完成后，用图片尺寸/帧数做一次快速校验，确认关键文件实际落在用户指定的统一目录下。

## 实战指南
- 多做对齐：每次生图图片之前，尽量先确认好需求。生成之后也让用户确认一下品质（或者你自己确认），最好不要一上来就大规模生成，而是先选一两个模板，
- 文档编写：随着开发，交流，生成的过程，最好持续的更新文档，例如写到项目根目录下的 `AGENTS.md`里，在里面开一个章节，记录美术相关的只是，例如美术风格，资产要求（如画布尺寸，sprite 尺寸等），资产分布，生成过程的记录等。这可以让提高整体美术开发的效率和一致性。

### 场景生成
- 非像素的游戏背景图、场景概念图、氛围稿，通常优先使用通用的 `gemini-generate-content`。
- 像素背景要先判断最终交付物：如果是单张可平铺地表纹理，优先使用 `texture-gen-run`；如果是地形过渡 tileset，优先使用 `tileset-gen-run`；如果是可拆分场景素材、道具组、UI 小图标或角色周边资产，优先使用 `pixel-gen-run` 选择模板生成；如果是大幅完整场景概念稿且没有合适模板，才使用 `gemini-generate-content` 生成中间稿，然后用 `pixelate-run` 收敛成像素风最终稿。
- 固定尺寸非像素背景图：直接走通用生成模式，在描述里明确风格、主体和镜头关系。这里最重要的是先选一个接近最终画布的尺寸比例，例如 `16:9`，这样后续通常只需要轻微 crop，不必再做大幅缩放。
- 如果用户明确要 `2K`、`16:9` 等尺寸，不要只在 prompt 里写尺寸；同时传 `generationConfig.imageConfig`，例如：
  ```bash
  python3 skills/game-assets/meowart_api.py gemini-generate-content \
    --text "Generate a 2K 16:9 game background..." \
    --generation-config '{"responseModalities":["TEXT","IMAGE"],"imageConfig":{"aspectRatio":"16:9","imageSize":"2K"}}' \
    --output-dir ./outputs/background_2k_16x9
  ```
  生成后必须检查实际尺寸；`16:9 2K` 期望是 `2752 x 1536`。
- 无限循环背景图：先生成一张普通背景图(最好在 prompt 中提前说明这是横向游戏还是纵向游戏的背景,否则图片的横纵比或者内容太差，可能无法改造为自我循环)。如果最终要求像素图，先按上面的像素背景规则生成或 `pixelate-run` 收敛，再调用 `self-loop-run`，把它转成横向或纵向可无缝循环的背景，用于卷轴场景或重复平铺纹理。需要四向连续时传 `--mode full`。

### 角色 / 道具 / Icon / Sprite 生成
- 人物、怪物、道具、Icon 这类资源，通常先通过 `pixel-gen-template-info` 查看可用模板。选择模板生成之前如果条件允许，可选择几个备选项，将 `preview_image_url` 的图片下载下来，并在对话窗口里直接展示给用户，进行一次风格的对齐。
- 不同模板的主要差异在于美术风格、单张图片尺寸，以及一次可批量生成的数量。原则上模板本身都是通用的，都可以通过 prompt 生成任意内容；但选一个更合适的模板，会明显提高结果确定性，也更容易维持整个项目的美术统一。
- 模板选择建议：
  - 物品、Icon、小动物：优先考虑 `food`、`object` 模板（这两个模板最好看也最通用），单次通常可以生成 `8` 个 `64x64` 像素对象。
  - 人物、主角、怪物角色：优先考虑 `pixel_char` 模板，单次通常可以生成 `2` 个 `128x128` 对象。
  - 具体模板名称和批量数量仍以 `pixel-gen-template-info` 的返回为准；如果服务端模板列表发生变化，先按返回信息调整。
- 正式生成时使用 `pixel-gen-run`，模板通常都已经自带了一套风格，因此无需再大量的笔墨去描述风格，只用简单描述一下外观，批量生成多个内容的时候可以说清楚每一个物体的类型（例如折耳猫，波斯猫……）。
- 对于批量模板，`requirement` 更接近“这一批要生成什么”，而不是最终直接发给模型的完整 prompt。系统会结合模板自己的 `target_count` 再包装成真正的生成提示词。例如 `cat_2` 默认会生成 `8` 个 sprite，因此写 `猫咪` 也会被解释成“生成 8 个猫咪”；如果想让这一批结果更有区分度，应该直接写变体列表，例如“三花、橘猫、奶牛猫、暹罗、英短、美短、狸花、纯白猫”。
- 批量生成时，既可以在 `requirement` 里分别描述多个对象的外观，也可以用一句话简单描述整体需求，让服务端的 Agent 自己细化。尽量一次性生成模板支持的最大数量，因为同一模板下价格和质量通常没有区别，多生成一些更方便挑选。
- 对于 pixel-gen 模板，像“白色背景”“像素风格”这类模板本身已经隐含的约束，通常不需要在 `requirement` 里重复强调，除非这次任务确实要覆盖模板默认行为。
- 如果是横版过关游戏，或者类吸血鬼幸存者游戏，优先考虑带 `direction` 的模板，用 `left` 或 `right` 这类侧面视角会更贴合游戏表现；如果还是用普通模板，也要在 prompt 里明确写清楚角色视角。
- 当前这套模板主要面向 Pixel 风格 Sprite；如果要做高清二次元、厚涂、插画风角色，只能先用通用的 `gemini-generate-content` 生成，再自行抠图或后处理。
- 如果用户明确“不使用 template”但要像素角色，走通用生图生成白底单角色，再按顺序执行：`pixelate-run` 收敛成像素图，`remove-background-run --method pixel` 去白底，最后校验 PNG 是 `RGBA` 且尺寸符合接入需求。默认不要手动传 `--pixel-size`，优先让服务端自动估计；只有明确目标尺寸或已验证参数时才指定，例如同一输入下 `--pixel-size 16` 可能比 `--pixel-size 8` 更接近 `128x128` sprite。
- 人物主角、Boss、立绘感更强的角色，通常更适合选单次只生成 `1` 到 `2` 个的大尺寸模板。批量敌人、批量道具、Icon 等，则更适合一次生成 `8` 个左右的模板，提高效率并确保同批资源风格一致。
- 不同模板生成出来的 sprite 尺寸可能不同，接入游戏代码时要注意统一 resize。像素图只能使用邻近采样，并尽量保持整数倍缩放，例如 `2x`、`3x`；不要使用 `0.85x`、`1.2x` 这类非整数缩放，否则会破坏像素质感。

### HD 资产生成
- 非像素高清角色、道具、Icon、物品包、透明 PNG 资产，使用 `hd-gen-template-info` 查看模板，再用 `hd-gen-run` 生成。
- `hd_gen_grid_2x2` 模板偏角色或少量高清资产，`hd_gen_grid_4x4` 模板偏批量 icon / sprite pack；具体以 `hd-gen-template-info` 的 `workflow_id`、`agent_type`、`output_size`、`supported_config_keys` 为准。
- 如果模板支持方向，使用 `--template-config '{"direction":"front"}'`、`left`、`right`、`back` 等值；如果模板支持数量，用 `target_count` 放进 `--template-config`。
- HD 资产默认会做 HD 去背景，`--hd-remove-bg-mode batch` 通常更快，`single` 更适合 batch 模式失败或边缘质量需要逐张优化时重试。
- 典型命令：
  ```bash
  python3 skills/game-assets/meowart_api.py hd-gen-template-info
  python3 skills/game-assets/meowart_api.py hd-gen-run \
    --template-name "hd_char_1" \
    --requirement "A cheerful fantasy alchemist girl with green cloak" \
    --template-config '{"direction":"front"}' \
    --output-dir ./outputs/hd_alchemist
  ```

### Texture / Tileset 生成
- 单张可平铺纹理、地表材质、墙面、水面、岩浆、木板、石块等，使用 `texture-gen-run`。默认会追加 self-loop 后处理，输出 512x512 左右的四方连续纹理。
- `texture-gen-run` 可以传参考纹理名：`--texture-name "水面"`，也可以重复传或用逗号写一组。当前内置参考包括 `水面`、`带气泡的岩浆`、`砖墙`、`木板`、`破碎小石块`、`金属板`、`凝固中的熔岩`、`火山岩带熔岩纹理`。
- 如果只是想快速生成普通纹理草稿，可以不传 `--texture-name`，后端会使用默认三张参考。若要降低成本或只要非连续中间稿，可以传 `--no-self-loop`。
- 地形过渡 tileset、dual-grid 15 tile atlas、草地/水面/岩浆等前景背景混合边缘，使用 `tileset-gen-run`。可选传 `--foreground-texture` 和 `--background-texture` 让 tileset 贴近已有纹理。
- 典型命令：
  ```bash
  python3 skills/game-assets/meowart_api.py texture-gen-run \
    --prompt "mossy cracked stone floor" \
    --texture-name "砖墙" \
    --texture-name "破碎小石块" \
    --output-dir ./outputs/mossy_stone_texture

  python3 skills/game-assets/meowart_api.py tileset-gen-run \
    --prompt "lush grass foreground plus shallow blue water background" \
    --output-dir ./outputs/grass_water_tileset
  ```

### 动画生成
- 角色或物体的攻击、死亡、移动、跳跃、弹跳等动作，通常使用 `animate-run`。
- 输出通常会包含 `gif`、`webp`、`png` 三种格式；其中 `png` 一般已经去掉背景，可以直接作为 sprite sheet 接入游戏。
- 最佳顺序通常不是一开始就做动画，而是先把静态 Sprite 做出来，并在游戏里验证尺寸、透视、美术风格、碰撞盒、游戏性都没有问题后，再进入动画阶段。
- 这样做的原因是 `animate-run` 相对更慢、费用也更高，更适合作为资产定稿前的最后一步，而不是前期反复试错的主流程。
- 动画接口偶尔会返回临时 `502` 或轮询异常：如果提交阶段已经打印 `api_job_id`，用 `animate-poll --api-job-id <id>` 复查并下载；如果提交阶段没有拿到 job id，直接重试 `animate-run`。

### 音效生成
- 短音效、UI 反馈、攻击、受击、拾取、爆炸、魔法、环境音片段，使用 `sound-run`（别名 `sfx-run` / `sound-effect-run`）。它走后端 `elevenlabs_generator` 工作流，会先优化音效 prompt，再生成音频。
- 单个音效默认 `--duration 2` 秒；支持 `0.5` 或 `1` 到 `10` 秒整数。需要可循环环境短音时传 `--loop`。
- 需要一组不同音效时传 `--sound-pack --count N`；需要同一个音效多个版本供挑选时传 `--variants --count N`。`--sound-pack` 和 `--variants` 不能同时使用。
- 默认会做峰值音量归一化，输出更适合直接接入游戏；如果要保留原始响度，可以传 `--no-normalize-volume`。
- 如果后端没有配置 ElevenLabs key，可以临时用 `--provider-api-key` 传入，但更推荐后端环境变量配置，避免密钥进入命令历史。
- 典型命令：
  ```bash
  python3 skills/game-assets/meowart_api.py sound-run \
    --prompt "soft wooden UI button click for cozy pixel RPG" \
    --duration 1 \
    --output-dir ./outputs/ui_click

  python3 skills/game-assets/meowart_api.py sound-run \
    --prompt "8-bit fantasy combat sound pack: sword slash, shield block, coin pickup, potion drink" \
    --sound-pack \
    --count 4 \
    --duration 1 \
    --output-dir ./outputs/combat_sfx_pack
  ```

### 音乐生成
- 游戏 BGM、场景音乐、主题曲方向探索，通常使用 `music-run`。默认不生成音频，只生成结构化英文音乐描述，包括 `name`、`summary` 和 `timestamps_detail`，适合先让用户确认音乐方向。
- 需要快速试听时，使用 `music-run --audio-generate --demo`，会调用 30 秒 demo 音频生成并下载返回的音频文件。正式 3 分钟音乐再使用 `--audio-generate` 且不传 `--demo`，避免前期反复试错成本过高。
- `--prompt` 可以写中文或英文；如果有游戏截图、场景图或参考图，可以重复传 `--reference-image ./scene.png`，让音乐 prompt runner 结合画面氛围生成描述。如果只传参考图不写 prompt，服务端会按参考图生成音乐方向。
- 默认音乐目标是 loop-friendly，适合 BGM 接入。Prompt 中仍应明确使用场景、情绪、节奏、乐器、人声限制等，例如“村庄白天市场、温暖、长笛和 kalimba、无 vocals、可循环”。
- 输出结果里重点看 `result.name`、`result.summary`、`result.timestamps_detail`。音频模式还要检查 `result.audio_path`、`metadata.model`、`metadata.audio_bytes` 和本地下载的 `mp3` 文件大小。
- 已有任务 id 时，用 `music-poll --api-job-id workflow-music_generator-...` 复查并下载音频。生成失败或超时时，先看 `job_response.json` 和 `meta.json`，不要盲目重复提交正式音频任务。

### UI 生成
- 目前工具里没有真正端到端的 UI 生成接口，但可以通过通用生图和其他 API 组合出一套可用流程。这里的通用生图只适合整体 UI 视觉稿；如果用户要的是像素 UI 小图标、按钮 sprite、道具栏格子等独立像素资产，仍按核心路由规则优先用 `pixel-gen-run`。
- 第一步：先截取真实游戏画面。
- 第二步：使用 `gemini-generate-content` 做通用生成，例如让模型“在这个游戏画面左上角添加一个角色状态栏 UI，包含血量，经验，头像等，并保持整体美术风格一致”。
- 第三步：拿到视觉稿后，一般有两条路线。
  - 编程复刻：根据视觉稿，用代码来复刻 UI。这条路线更可控，生成之前可以先给用户看一下 UI是否符合要求。。
  - 提取非像素 UI PNG asset：继续使用通用生图，把 prompt 改成“将画面左上角人物角色状态栏的 UI 提取到白色背景上，删除其他所有背景、人物和 UI，只保留角色状态栏，并保持白色背景”。得到结果后，再调用 `remove-background-run` 去除白底；最后结合 crop 或手工微调尺寸，就可以得到可直接用于游戏中的非像素 UI PNG。
