# 图片 → 可编辑 PPTX

## B0：输入与任务目录

创建唯一目录，例如 `image2pptx_runs/<时间戳>-<主题>/`。源图、提示词、生成层、layout 和 QA 各归其位。源图必须是用户当前指定图片；续做时允许复用明确指定的旧资产。
先读源图尺寸，逐项建立 `elements.json`：元素名称、`source_bbox:[x,y,w,h]`、表示方式 `native_text/native_shape/image/provided_asset`、所在层、选择原因。没有图标时记录原因，不生成空图标表。
模式记为 `hybrid`（默认）或用户指定的 `raster`。先以代表页验证视觉与可编辑性，再处理其余页。

## B1：图片层与底色

按 SKILL.md 决定哪些元素需要图片。直接透明输出可用且效果干净时不必加绿幕；不要再次对原生透明 PNG 抠绿。
需要色键时运行 `probe_palette.py` 查看候选色；选择与前景不冲突的底色。金色边缘与绿色容易混色，必要时换洋红或直接透明输出，不能认为 green 永远最优。

## B2：背景

复杂照片/渐变背景通过 imagegen 编辑当前源图，移除将重建的文字、图标、线条、卡片，保留照片构图和光照。不要只给抽象文字描述让模型重新设计。
纯色背景使用 `background_color`；不得同时把含同样内容的整页图塞进 background。
提示词要列出保留与移除元素；背景生成后单独查看，尤其检查文字残影、重复线条和新增物体。

## B3：框架

混合模式中简单几何对象写入 `shapes[]`，复杂框架才生成 `frame.png`。每一根简单分隔线独立命名，不能为两根线生成整页透明图。
生成框架时明确排除原生重建元素及图标，保持源图比例、位置、填充、线宽。没有复杂框架时省略 `frame`。
复杂框架默认整体保留；独立移动有价值时可分块，不能切断连续光效/连接线。`slice_grid.py --auto` 与 `frame_parts_to_icons.py` 可用于生成后透明框架的分块回放。

## B4：图标与艺术字

普通纯色字母/数字优先文本框。渐变本身不自动等于不可编辑艺术字；按字体形状、用户编辑需求和可用工具判断。
图片图标用 imagegen 从当前源图提取，少量独立资产可直接透明输出。多个资产排网格时逐项编号，格内留白，不画格线。记录所有资产的去向，避免背景、框架、图标三处重复出现。
用户原 LOGO 和二维码直接用原文件。不要生成看似真实却不能扫描的二维码。

## B5：去底与透明层检查

只对使用色键的生成素材运行：

```bash
python3 scripts/chroma_key.py --input frame_raw.png --out frame.png --preset frame-safe --scale 2 --force
python3 scripts/chroma_key.py --input icons_raw.png --out icons_t.png --preset icon-safe --scale 2 --force
# 非绿底时显式设置 --auto-key none --key-color '#ff00ff'
python3 scripts/slice_grid.py icons_t.png icons --grid 2x2 --pad 8 --contact-sheet
python3 scripts/alpha_qa.py frame.png --out-dir qa/frame --key-color '#00ff00' --strict
```

预设是起点，不保证无绿边或无缺线。`--scale 2` 仅超采样，不恢复真实细节。不要通过大范围腐蚀消除绿边，把细线一起擦掉。
检查脚本输出的白/灰/黑底图、前景放大图和报告。可疑色键像素是人工复核提示，不是自动认定错误；如果前景本身含底色，换提取策略，不盲目去色。图标表切片后查看 contact sheet 与 `edge_touch`；不能只检查整表。

每页 `imagegen-assets-manifest.json` 记录**实际生成**的资产：backend、generated_source、copied_to、prompt_file，以及 key_color 或 transparency。未生成的层在元素清单中说明原因，不捏造模型调用。

## B6：定位与 schema

坐标以原图实际 W×H 测量。`source_bbox` 保持源像素；`x/y/w/h` 采用 fraction（分别除 W/H）或全程 px。文字先定字体、字号、粗细和行距，再回校框架内边距和对齐。字体不具备时记录替代，不能把默认字体渲染称为精确复刻。

```json
{
  "slide_width_in": 13.333333,
  "slide_height_in": 7.5,
  "ref_width": 1672,
  "ref_height": 941,
  "units": "fraction",
  "background_color": "#101318",
  "shapes": [
    {"name":"brand-divider", "type":"rect", "x":0.4,"y":0.09,"w":0.003,"h":0.04,
     "fill":"#F4B83E", "source_bbox":[668.8,84.69,5.016,37.64]}
  ],
  "icons": [],
  "texts": [
    {"name":"title", "text":"演示标题", "x":0.06,"y":0.2,"w":0.8,"h":0.15,
     "source_bbox":[100.32,188.2,1337.6,141.15], "size":36, "font":"Microsoft YaHei",
     "color":"#FFFFFF", "bold":true, "line_spacing":1.2}
  ]
}
```

- 多页放进 `slides[]`，页面尺寸、units、ref_width/ref_height 与 assets_dir 在顶层。
- 图片路径：`background`、`frame`、`icons[].file`；全幅图片放背景/框架，独立资产用 icons 的坐标。
- `assets_dir` 省略时为 JSON 所在目录；相对路径也以 JSON 所在目录为基准，便于整包迁移。
- `background_color` 可与照片层共存作为底色；层序是底色 → background → frame → shapes → icons → texts。此合成器不支持任意 z-order，需要其它层序时使用支持该功能的工具，不要交付遮挡错误。
- shapes 支持 rect、rounded_rect、oval/ellipse、line、chevron、parallelogram、trapezoid、diamond。`line` 的 w/h 是终点相对起点的有符号偏移，水平/竖直线允许为0；粗直条可用 rect。
- 形状字段：fill、opacity（填充）、line、line_width（pt）、radius、rotation、shadow。旋转和阴影仅在真实PPT渲染中可靠验证；简易预览不精确支持。
- 文字字号可用 size（pt）、size_ratio（源文字像素高/源图高）、size_pct、size_px。换算：`pt=size_ratio×slide_height_in×72`。不要把缩略图像素当源图像素。
- 文本支持 bold、font、color、align、valign、line_spacing（倍数）与 runs 混合样式。普通正文不要全部加粗；本地简易预览对 runs 换行和字体替换仍有限制。

## B7：文字核对

视觉读取所有文字，与用户原稿对照。普通字母代码不要为追求外观都变成图片。对多行文字检查实际换行、字号、内边距、行距；标题和正文分开设置。
`source_bbox` 先圈住源图真实对象，再换算最终坐标；若生成框架轻微漂移，记录 frame_anchor、dx/dy 和原因，校准最终贴框文字。

## B8：合成

```bash
python3 scripts/layout_guard.py source.png layout.json --strict
python3 scripts/compose_pptx.py layout.json editable.pptx --preview-dir preview
python3 scripts/placement_qa.py source.png layout.json --preview preview/slide_01.png --out-dir qa/placement
python3 scripts/visual_compare_qa.py source.png preview/slide_01.png --out-dir qa/compare
```

`compose_pptx` 的 PNG 是 Pillow 近似预览，不是 PowerPoint 截图。可用时再用 PowerPoint/LibreOffice 渲染实际 PPTX，优先检查字体、换行和溢出。没有真实渲染器时明确记录未验证项。

## B9：验收与交付

执行 [quality-checks.md](quality-checks.md)。机械校验、透明层质量、视觉还原、真实PPT渲染分别记录状态，不合并为“全部通过”。局部失败只修局部；同一资产两轮无改善时换表示方式或说明限制，不无限重生图。
交付可编辑 PPTX、布局 JSON、使用素材、提示词与来源记录。使用相对路径打包后在另一目录验证可重合成；不要将私人客户素材提交到公共代码仓库。
