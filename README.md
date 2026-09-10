# anime-enhance

[![CPU regression tests](https://github.com/Castorice7/anime-enhance/actions/workflows/tests.yml/badge.svg)](https://github.com/Castorice7/anime-enhance/actions/workflows/tests.yml) · [Changelog](CHANGELOG.md) · [Releases](https://github.com/Castorice7/anime-enhance/releases) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

当前版本：`0.1.0`。这是一个面向 Windows x64 的本地工具，不是 HoYoverse / miHoYo 官方产品。

本地二次元图片超分、视频精准抽帧与附近候选帧筛选工具。适用于游戏画面、动画、PV、MMD 与二次元图片。

**默认保真 2×，保留原文件与透明通道。** 使用 FFmpeg、yt-dlp 和 Real-ESRGAN-ncnn-vulkan，增强在本机 GPU 上执行，不上传图片到云端。

Local anime image upscaling and timestamp-aware video frame extraction for Windows. Faithful 2× by default; original files and PNG alpha preserved. CLI works independently, with optional agent-assisted visual review.

## 功能

- PNG / JPG / JPEG / WebP 输入，输出无损 PNG。
- 保真、清晰、超清三档；明确要求 4× 或超清时才输出 4×。
- 本地视频或公开 URL 原分辨率抽帧，无播放器截图、无插帧。
- 使用真实展示时间戳，支持可变帧率，记录实际时间和偏差。
- 默认 ±1 秒、约 21 帧搜索，保存原始候选、前三名及联系表。
- 每次使用独立输出目录，记录模型、参数、哈希与推理日志。

## 安装（Windows x64）

需要 **64-bit Python 3.12**、加入 PATH 的 **FFmpeg / FFprobe**，以及支持 Vulkan 的 NVIDIA / AMD / Intel GPU 与驱动。FFmpeg 可从[官方下载页](https://ffmpeg.org/download.html)获取 Windows 构建。首次安装需要联网。

下载仓库 ZIP 并解压，或使用 Git 克隆。进入项目目录执行：

```powershell
py -3.12 setup.py
.\run.cmd doctor
.\run.cmd --version
```

没有 `py` 时，确认 `python --version` 为 3.12 后使用 `python setup.py`。安装创建 `tools/venv` 独立环境，不修改系统 Python 包。工具和模型从上游下载并校验 SHA-256；哈希用于复现，不是发行者签名。`doctor` 检查文件与路径，实际 GPU 工作状态需用图片命令或集成测试验证。

安装完成后可运行 `.\run.cmd doctor --deep`，用临时 8×8 图片执行一次真实 NCNN 推理；检查不会使用或覆盖你的图片，也不会把测试图写入 `output`。

移动整个项目后建议重新创建 `tools/venv`；Windows Python 虚拟环境不承诺可搬移。

## 图片增强

把图片拖到 **`repair-image.cmd`** 即可保真 2×，或执行：

```powershell
.\run.cmd image ".\input\图片.png"
.\run.cmd image ".\input\图片.webp" --level 清晰
.\run.cmd image ".\input\图片.jpg" --level 清晰 --scale 4
.\run.cmd image ".\input\图片.png" --level 超清
.\run.cmd image "D:\pictures\one.png" "D:\pictures\two.jpeg"
```

结果在 `output/<独立任务目录>/`。放文件到 input 本身不会触发后台处理。

| 等级 | 默认输出 | 处理方式 |
| --- | --- | --- |
| 保真 / faithful | 2× | 65% 动漫超分 + 35% 原图 Lanczos 插值；无额外锐化 |
| 清晰 / clear | 2×，可指定 4× | 85% 动漫超分；低强度线条锐化 |
| 超清 / ultra | 4× | 原生 4× 动漫超分；无额外锐化 |

默认 `realesrgan-x4plus-anime` 模型原生 4×，2× 输出由原生结果缩至 2×。三档是此工具的预设，不是三个独立模型。alpha 不经过神经网络，使用原 alpha 双线性插值并输出 RGBA；保留可用 ICC / DPI，按 EXIF 方向正常显示。

## 视频抽帧

```powershell
# 最近实际 PTS 帧，然后保真 2×
.\run.cmd video ".\video\PV.mp4" --time 01:32.417

# 公开 URL：下载最高公开可访问视频流，再抽帧与增强
.\run.cmd video "https://www.youtube.com/watch?v=QbPtrnmGlZ8" --time 01:32.417

# 前后 1 秒搜索，直接增强启发式第一名
.\run.cmd video ".\video\PV.mp4" --time 01:32 --nearby

# 先看候选，再按序号选择并增强
.\run.cmd video ".\video\PV.mp4" --time 01:32 --nearby --extract-only
.\run.cmd choose ".\frames\任务目录\frames.json" --rank 1 --reason "脸部清晰，无遮挡，构图接近指定时刻"

# 主体区域：归一化 x、y、width、height
.\run.cmd video ".\video\PV.mp4" --time 01:32 --nearby --roi 0.3 0.1 0.4 0.6

.\run.cmd search "Honkai Star Rail Robin Sway to My Beat"
.\run.cmd download "https://www.youtube.com/watch?v=QbPtrnmGlZ8"
```

时间支持 `92.417`、`01:32.417`、`1分32.417秒`。视频流 start_time 为起点；选择最近真实展示时间戳，等距取较早帧，越界报错。不存在的画面不通过插帧生成。

下载使用 yt-dlp `bv/b`，按分辨率、帧率与码率排序，仅下载视频流，保留原编码。来源和格式记录在 `video/<任务>/source.json`。最高画质指当次正常公开可访问版本，不代表母版；网络、地区和站点限制可能导致失败。不绕过 DRM、付费墙或登录限制。

`search` 返回结果与已核实频道标记，目前预置星穹铁道英文官方频道。它不会仅凭标题含“官方”认定来源，也不自行判断同名 PV 的语言和版本。其他官方来源需要核实发布者。

## 最佳帧搜索与视觉复核

候选通过 FFmpeg 原分辨率解码为 PNG；JPG 联系表仅供预览，不参与增强。排序综合主体/动漫脸部清晰度、全局清晰度、压缩块代理分数、时间距离和镜头变化代理。

**CLI 评分是启发式，不能可靠判定睁眼、表情自然度、字幕遮挡与复杂转场残影。** 自动结果标记 `visual_review=pending`；使用 choose 表示调用者完成视觉复核，并保存原因。所有原帧与之前的选择保留。

图片增强、URL 下载、抽帧可独立使用。可选自然语言流程需要能读图并执行本地命令的助手：参考 [AGENTS.md](AGENTS.md)，在该工作区说“修复这张图”默认保真 2×；说“某 PV 1:32 附近”时，助手定位官方来源、查看候选并选择增强。单独双击脚本不会获得自然语言或视觉理解能力。

## GPU 与配置

`config.json` 的 GPU 默认 null，由 NCNN 自动选择。多显卡机器可使用 `--gpu 0`；设备编号见 `output/<任务>/inference.log`。可创建不提交到 Git 的 `config.local.json`：

```json
{"gpu_id": 0, "tile_size": 64}
```

显存不足可把 tile 从 128 调为 64。默认限制原生 4× 中间图不超过 1.6 亿像素，超过时明确报错。

## 验证

安装后执行实际 GPU / NCNN / FFmpeg 集成测试：

```powershell
.\tools\venv\Scripts\python.exe tests\verify_workflow.py
```

测试自行生成几何图、透明渐变、JPEG/WebP 与无损可变帧率视频，不依赖用户图片或第三方角色素材。校验 2×/4×、alpha、源文件不变、独立输出、真实 PTS 与已知帧像素。几何测试证明管线可运行，不证明所有动漫素材的视觉质量。

无需 GPU 的基础测试：

```powershell
.\tools\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

发布验证见 [docs/VALIDATION.md](docs/VALIDATION.md)。其他 GPU 和在线站点仍可能因机器/网络不同而表现不同。

## 边界与许可证

- 不接入扩散模型、生成式补画、GFPGAN、CodeFormer、换脸、五官或手指重建。
- Real-ESRGAN 是 GAN 训练的学习型超分，仍可能估计、平滑或改变局部细节；不承诺细节绝对不变或恢复真实丢失信息。
- 支持 8-bit SDR；16-bit 图片、动画图片、HDR 视频、非方形像素视频明确报错。
- 准确索引会解码视频，长片的时间与磁盘开销较大。
- 安装和启动脚本面向 Windows x64 + Python 3.12；Linux/macOS 未适配。waifu2x 未启用。

运行数据保存在 input、video、frames、output、models、tools 六个目录，均被 Git 忽略。仓库不分发游戏 PV、角色图片、已下载模型或二进制程序，依赖由安装脚本从上游获取。

项目脚本采用 [MIT License](LICENSE)。第三方组件保留各自许可，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。本项目与米哈游 / HoYoverse 无隶属或官方合作关系；示例链接仅说明命令用法。
