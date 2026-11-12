---
name: GordenImagePPTGen
description: >-
  调用 GPT imagegen技能生成「图片格式的 PPT 文档」——每页一张文字清晰、风格统一的幻灯片图（按场景选择密度，
  也支持简洁/卡通/水墨/科技等任意风格），并合成为每页一张全幅图片的 .pptx。Generates image-based slide decks
  (one rendered image per slide) from a topic or content. 当用户要"做 PPT / 生成图片版 PPT / AI 出图幻灯片 /
  把内容做成 PPT 图片"时使用。本技能**只产出图片型 PPT**（每页 .png + 合成的 .pptx）；若还要可编辑 pptx，接着用 GordenImage2PPTX。
---

# GordenImagePPTGen — 生成图片格式的 PPT

把主题/内容变成「图片型 PPT」：设计 → 出图 → 合成。每页是一张由imagegen生成的图片。必须使用图片生成，不能通过SVG绘制，必须调用图片生成模型。

```
内容 ─▶ A2 设计大纲(outline.json) ─▶ A3 每页提示词 ─▶ A4 GPT imagegen 出图 ─▶ A5 合成图片型 .pptx
```

## 运行时与图片后端（先读）

图片生成的调用方式因运行时而异，**动手前先读 [`references/runtime-notes.md`](references/runtime-notes.md)**。核心约定：

1. **图片一律用 raster 图像生成后端**（Codex 必须调用内置 imagegen；其它运行时用其原生出图工具）。**禁止**用 SVG/HTML/Canvas/代码画图冒充。
2. **禁止在已生成的位图上用代码补字/盖字/改字**。文字错了没关系，后续改成可编辑pptx后支持手动修改。
3. Codex 内置工具出的图默认在 `$CODEX_HOME/generated_images/`，**用完务必复制到本任务输出目录**，并保留默认目录原图。
4. 阶段 A4 必须写 `imagegen-manifest.json`，逐页记录模型生成源图与复制后的 slide 路径；没有 manifest 或任一页缺 `generated_source`，本技能执行失败。

## imagegen 硬门禁

本技能中的“生成图片”只指调用图像生成模型，不指用代码画 PNG。

禁止使用以下方式生成整页幻灯片图：
- Python/PIL、SVG、HTML、Canvas、matplotlib、PowerPoint shapes、截图渲染。
- 先生成可编辑 PPTX，再导出为图片。
- 用代码绘制页面骨架、图表、图标、文字并保存为 PNG。

允许代码做的事仅限：
- 写 `outline.json`、`prompts/NN-*.md`、`imagegen-manifest.json`、`deck.json`。
- 从 `$CODEX_HOME/generated_images/<thread-id>/...png` 复制已生成图片到 `slides/`。
- 裁切/缩放整张已生成图片以统一比例（不得补字或重画局部内容）。
- 合成图片型 PPTX、生成预览、做 QA 检查。

如果 imagegen 不可用，必须停止并说明阻塞原因，不能用代码绘图兜底。

## 全局铁律

1. 🔴 **绝不出占位符图**：本技能产出的是**含全部真实文字(verbatim)的成品幻灯片图**，不是空模板。出图提示词的【页面文字】必须写满真实文字；`outline.json` 的 `visual_generation_prompt`（只描述画面）**禁止单独出图**，必须与全部文字合并后再出（详见 image-prompt-guide 文首铁律）。出现 lorem/占位框/无字卡片即判失败、改提示词重出。
2. **数据零编造**：完全使用用户提供的数据/数值/专名。数据少就把内容做厚（真实的结构化拆解）+ 大字号/中心聚焦排版，**绝不**编造或填充虚假内容。
3. **语言跟随用户**：问答用用户语言；幻灯片内文字用内容语言（默认中文）。
4. **少用绿色**：尽量避免大面积纯绿（下游 GordenImage2PPTX 默认绿幕抠图会冲突）。
5. **页脚干净**：不加页码/logo/水印（除非用户要求）。

## 默认风格与信息密度

以受众和使用场景决定密度。现场投影每页一个重点，标题和正文远距离可读；报告型页面可增加信息密度。用户要求高密度/复杂信息图时再使用对应配方，不把“复杂”当作合格门槛。

- 尊重用户已给的页文，不为撑满版面添加无依据的指标、标签或子结论。
- 统一配色、字号层级与卡片语言；允许相同类型页面复用布局。
- 结构服从内容关系：并列产品用卡片，步骤用流程，数量比较用真实数据图。没有关系就不画箭头。
- 参考图只学合适的布局，不照搬文字/品牌；细则与可选高密度配方见 [image-prompt-guide.md](references/image-prompt-guide.md)。
- 全程统一比例，默认16:9；不要为适配模型输出拉伸文字或图表。

## 工作流（逐项打勾）

```
- [ ] A1 明确：风格 / 受众 / 页数 / 语言；已提供不重复询问，缺少影响设计的信息再问
- [ ] A2 大纲(outline.json)：解构内容 → 按内容选择布局、统一配色、准确记录 detailed_content（见 image-prompt-guide §7 / §1.7）
- [ ] A3 每页提示词：把 outline 落地成 self-contained 提示词（含【全部真实文字 verbatim】），存 prompts/NN-*.md
- [ ] A4 出图：解析后端 → 逐页调用 imagegen 出图（每页含全部真实文字，绝不占位符）→ 复制到输出目录 → 写 imagegen-manifest.json
- [ ] A5 合成：compose_pptx.py 把每页图片做成全幅图片型 .pptx
```

要点：
- **页数**：用户指定就用；没指定按内容量自定（一般 11–20 页，封面+结尾必有）。
- **A3 提示词自包含**：颜色(hex)、版式、**全部文字**、图表形式、字体风格全写死，便于可复现、单页重出。
- **A4**：先确认所有 `prompts/NN-*.md` 就位再开跑；每页必须有一次真实 imagegen 调用；失败/错字只重试该页；复制源图时保留 `$CODEX_HOME/generated_images/...` 原图。
- **imagegen-manifest.json**：必须逐页记录 `slide`、`prompt_file`、`generated_source`、`copied_to`、`backend`。这是阶段 1 的验收证据。
- **A5**：生成 `deck.json`（每个 slide 只有 `background` 指向该页 PNG），跑：

```bash
python3 scripts/compose_pptx.py deck.json out/<topic>-image-deck.pptx
```

## 输出目录结构

```
<topic-slug>/
├── outline.json            # A2 设计大纲（逐页结构化）
├── imagegen-manifest.json  # A4 每页 imagegen 生成证据
├── prompts/NN-*.md         # A3 每页出图提示词（可复现）
├── slides/NN-*.png         # A4 生成的每页图片
├── deck.json               # A5 合成清单（每页 background）
└── out/<topic>-image-deck.pptx
```

## 脚本与依赖

| 脚本 | 干嘛 |
|---|---|
| `scripts/compose_pptx.py` | 把每页图片按 deck.json 合成全幅图片型 .pptx（`--preview-dir` 可出预览） |

- 依赖：`python3` + `python-pptx`、`Pillow`（缺就 `pip3 install python-pptx pillow`）。
- 下一步要可编辑 pptx → 用 **GordenImage2PPTX**；要一键全流程 → 用 **GordenSuperPPTSkill**。
