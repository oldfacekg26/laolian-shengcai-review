# 老脸生财有术复盘 Skill

把录音、转写、PPT、现场照片整理成总结文章，在知识星球中插入正文图片、让用户多选标签、预览确认后发布并核对。

这是 **Agent 工作流 + 三个通用脚本**，不是无需登录、无需审稿的一键群发器。适合支持本地 Skill、文件读写和浏览器工具的 AI 助手。不绑定某个模型，不需要作者的账号、盘符、照片库或浏览器配置。

## 安装

下载本仓库，放到你的助手支持的 Skill 目录，确保目录名为 `laolian-shengcai-review`，内部有 SKILL.md。Codex 用户可放在自己的 `~/.codex/skills/laolian-shengcai-review`；其他助手使用其官方 Skill 安装目录。

也可先克隆再让助手安装：

```sh
git clone https://github.com/oldfacekg26/laolian-shengcai-review.git
```

本地脚本需要 **Python 3.10+**，只用标准库。网页操作优先使用助手自带浏览器，并在同一个浏览器里完成扫码、上传、保存和预览，避免登录态不共享导致重复扫码。备用方案是官方 [agent-browser](https://github.com/vercel-labs/agent-browser)，本次实测版本 0.38.1；按官方说明安装 Chrome 及浏览器工具。录音转写、PPT/PDF 提取使用助手已有工具，不捆绑转写模型。

## 直接这样说

> 用 laolian-shengcai-review 整理这些活动资料，目标编辑页是我给你的知识星球网址。优先用 Codex 内置浏览器完成扫码和编辑；图片插入正文。先让我多选标签和预览，确认后才发布。

使用者需要提供目标编辑页和素材。不猜群 ID，不自动跨账号上传，不发布缺乏材料支撑的现场内容。

## 快速自测

```sh
python -m unittest discover -s tests -v
python scripts/prepare.py --draft examples/article.md --out output --destination "https://wx.zsxq.com/article?groupId=123" --tag "线下聚会" --tag "生财朋友圈"
```

第二条命令只生成本地预览。示例 groupId=123 是占位值，不能拿它进行真实上传。打开输出目录中的 preview.html 查看图片位置；正式使用时换成自己的编辑页。

## 脚本边界

| 文件 | 作用 |
|---|---|
| prepare.py | 图片校验、SHA 清单、有序标签、内容版本、自包含预览；相同输入不清空发布回执 |
| editor_payload.py | 已上传图片 SHA→URL 映射编译成 HTML；校验线上标题、图片顺序/加载状态、标签 |
| browser_step.py | 单步超时与计时；Windows 常驻进程不卡管道；eval 文件兼容；写入失败不自动重试 |

`editor_payload.py compile` 需要 manifest.json 所在目录，以及 `{图片SHA256: 已验证的https图片地址}` 映射。图片必须先经网页正规上传。生成 paste.js 不是上传或发布；执行前备份编辑器并确认可替换正文。

```sh
python scripts/editor_payload.py compile --packet output/版本号 --mapping uploaded.json --out output/payload
python scripts/editor_payload.py verify --expected output/payload/expected.json --actual readback.json
```

readback.json 格式：`{title, images:[{src,loaded}], tags:[...]}`。标签需从帖子详情独立读取，缺失就失败。

## 如何减少等待

先本地完成文章，再一次填入网页；只改标题不重传图片；图片按 SHA 复用；同一连接失败最多两次；浏览器中断后读状态再继续；发布超时先查已有结果，禁止盲点重发。默认单步 30 秒，连接恢复 3 分钟为设计预算，尚无多篇端到端性能保证。

用户原则上只在扫码、标签多选、最终预览确认时介入。浏览器通道应在扫码前选定，不在扫码后切换；网页保留供用户修改，用户改过的在线内容优先，不能用旧草稿覆盖。

## 已验证和未验证

见 [测试报告](TEST_REPORT.md)。已完成一轮 Windows 干净环境线上草稿测试：新 profile、扫码、7 张正文图片、两个有序标签、保存和发布前预览均通过，未点发布。Codex 内置浏览器已确认能打开知识星球登录页并读到“获取登录二维码”；完整扫码到发布链路仍需在内置浏览器单独验收，不能把 agent-browser 的结果冒充为内置浏览器结果。

未验证：其他操作系统完整发布、不同账号全部权限组合、跨天登录保持、未来编辑器改版、大规模/超大文章、连续多篇稳定耗时。不承诺永久免登录或一劳永逸。

## 分享与隐私

仓库仅含通用规则、脚本和合成样例。不要提交个人原始材料、照片、转写、草稿、登录 profile、cookie、验证码和 HAR。本文档是 2026-10-25 发布快照；站点变化需重新做小样本验收。
