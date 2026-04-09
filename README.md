# 无边图像浏览 MVP

给本地图片和视频堆成山的人准备的桌面小工具。

你文件夹里那些 `00001.png`、`00002.png`、`final_final_really_final.png`、还有一堆你自己都不想承认生成过的实验图，终于可以稍微体面一点地被翻出来看了。

这个项目目前是一个基于 **Python + CustomTkinter** 的本地媒体浏览器，主要服务于这类场景：

- Stable Diffusion 产图堆太多，目录已经长得像垃圾填埋场
- 想按目录快速翻图，不想先等一轮慢吞吞的全库扫描
- 想顺手看 Prompt、Negative Prompt、模型、采样器、Seed、Steps、CFG
- 想给图打标签、收藏、移动、删除
- 想要一个滚动时尽量别抽风、别撕裂、别一滑就满屏卡片重绘的列表

## 现在能干什么

### 动态浏览当前目录

程序按你选择的根目录递归读取媒体文件，直接从文件系统拿结果。

它会跳过这些目录：

- `thumbnails`
- `.thumbnails`
- `thumbs`
- `.thumbs`

因为谁会真心想把缓存缩略图也当成作品集的一部分翻呢。

### 支持的媒体类型

图片：

- PNG
- JPG / JPEG
- WEBP
- BMP

视频：

- MP4
- MKV
- WEBM
- MOV
- AVI

### 按时间倒序看最新文件

新图优先显示，最新生成的东西会排在前面。

终于不用在几千张图里考古找刚跑出来的那一张。

### 虚拟化网格滚动

列表不是那种老派做法：一口气给每个项目都造一堆 widget，然后滚起来像在拖一头快断气的牛。

当前实现使用 `tk.Canvas` + tile 复用，只保留视口附近需要显示的少量卡片。大目录下依然会忙，但至少忙得有点技术含量。

### 缩略图按需加载

缩略图直接从原始媒体读取并处理：

- 不依赖预扫描全库
- 不把当前 UI 建立在磁盘缩略图缓存上
- 后台线程加载，主线程负责显示

如果你看到某些图还没出来，通常只是它正在路上，不是它在跟你玩消失。

### 右侧详情面板

选中项目后可以查看：

- 路径
- 类型
- 尺寸 / 时长
- 模型
- 采样器
- Seed
- Steps
- CFG
- Prompt
- Negative Prompt

多行 Prompt / Negative Prompt 也已经处理，不会再只读第一行然后装作事情已经办完了。

### 收藏、标签、移动

你可以对项目做这些操作：

- 收藏切换
- 添加标签
- 移动文件
- 打开所在目录
- 复制 Prompt

这些状态会存进本地 SQLite，不需要为了一个星标按钮搞成什么企业级平台奇观。

### 右键菜单

在列表项上右键可以直接：

- 删除
- 使用默认应用打开
- 使用文件管理器打开
- 查看 Meta Data

### 双击打开

双击缩略图，会直接使用系统默认应用打开对应文件。

因为有时候你根本不想研究 UI，只想把图点开看大图。

## 项目结构

```text
main.py                  程序入口
py_inf/app.py            启动 MainWindow
py_inf/ui/               界面层
py_inf/domain/           业务逻辑
py_inf/data/             SQLite 数据层
py_inf/core/             元数据提取、缩略图、文件操作
py_inf/services/         设置、缓存、后台任务
.app/data/               本地配置和数据库
```

### 核心架构大意

- **文件系统是媒体真相源**：浏览时递归读取目录
- **SQLite 是轻量状态库**：保存收藏、标签和部分元数据记录
- **元数据按路径提取**：图片读 PNG 文本信息 / sidecar JSON，视频走 `ffprobe`
- **缩略图按需生成**：直接从原图或视频抽帧，不靠预扫全库养一座缓存坟场
- **UI 重点在 `MediaGrid`**：滚动、虚拟化、tile 复用、异步结果回填，全在这里折腾

## 安装

先准备 Python 3.11+。

安装依赖：

```bash
python -m pip install -r requirements.txt
```

`requirements.txt` 目前包含：

- `customtkinter`
- `Pillow`
- `send2trash`
- `watchdog`

如果你要看视频信息或视频缩略图，还得让这些东西在 PATH 里能被找到：

- `ffmpeg`
- `ffprobe`

少了它们，视频相关功能就会表现出一种“我也想努力，但系统不配合”的冷淡气质。

## 运行

```bash
python main.py
```

启动后：

1. 点击“添加目录”
2. 选择你的图片/视频根目录
3. 左侧切换目录、类型、收藏过滤
4. 顶部搜索文件名
5. 中间滚动浏览，右侧看详情

## 配置文件

运行后会在项目目录下生成：

```text
.app/data/settings.json
.app/data/media.db
.app/logs/
.app/thumbs/
```

其中常用配置在：

```json
{
  "scan_roots": [
    "G:\\sd-webui-aki\\outputs\\txt2img-images"
  ],
  "page_size": 60,
  "thumb_size": 220,
  "preview_size": 640,
  "last_query": "",
  "theme": "dark"
}
```

### 关于 `page_size`

这个值控制每次从当前目录拿多少项。

数字太大，首次加载更重。
数字太小，翻到底部会更频繁地继续取下一页。

别把它当成某种神秘性能开关，它没那么玄学，但也别乱拧到离谱。

## 目前的一些现实情况

这是 MVP。

意思很明确：

- 它已经能干活
- 它已经比“在资源管理器里盲翻几万张图”体面不少
- 它还有很多地方值得继续收拾

比如：

- 更丰富的元数据展示
- 更细的搜索能力
- 更稳的超大目录性能
- 更完整的视频交互
- 更顺手的批量整理
- 更聪明的标签 / 聚类 / 关系分析

## 开发

安装依赖：

```bash
python -m pip install -r requirements.txt
```

运行应用：

```bash
python main.py
```

快速语法检查：

```bash
python -m py_compile main.py py_inf/app.py py_inf/core/*.py py_inf/data/*.py py_inf/domain/*.py py_inf/services/*.py py_inf/ui/*.py
```

启动冒烟测试：

```bash
python -c "import sys; sys.path.insert(0, 'X:/SDPulgin/py-inf'); from py_inf.ui.main_window import MainWindow; app = MainWindow(); app.update_idletasks(); app.update(); app.destroy(); print('ok')"
```

## 给未来的开发者一点上下文

这个项目前期踩过几个非常具体的坑：

- 预扫描媒体在大目录上体验很差，后来改成目录动态加载
- 缩略图缓存方案引发过串图和理解偏差，当前主流程是直接从原始文件读取并内存处理
- 滚动闪烁和撕裂问题折腾过多轮，最后转成 `Canvas` 虚拟化 tile
- Prompt / Negative Prompt 解析不能偷懒，尤其是多行文本，偷懒一次，显示就会开始阴阳怪气

如果你准备继续改 `py_inf/ui/grid.py`，建议先深呼吸，再动手