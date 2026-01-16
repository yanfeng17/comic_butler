# AI 家庭漫画管家

🎨 通过 RTSP 连接家庭监控摄像头，自动抓拍精彩瞬间，AI 打分筛选，生成漫画风格连环画，并推送到微信。

## ✨ 功能特点

- 📹 **RTSP 抓拍**：连接监控摄像头，定时自动抓拍画面
- 👤 **人物检测**：AI 智能识别，只保留有人的画面
- ⭐ **审美打分**：AI 评估图片质量，维护每日 Top N 榜单
- 🎨 **漫画重绘**：将照片转换为漫画插画风格
- 🖼️ **连环画拼接**：按时间顺序拼接成漫画分镜
- 📤 **微信推送**：通过 PushPlus 推送到微信

## 🚀 快速开始

### 1. 安装依赖

```bash
cd comic_butler
pip install -r requirements.txt
```

### 2. 配置

编辑 `config.yaml`：

```yaml
# RTSP 摄像头地址
rtsp_url: "rtsp://admin:password@192.168.1.100:554/stream1"

# ModelScope API Token (从 https://modelscope.cn/my/myaccesstoken 获取)
modelscope_token: "your_token_here"

# PushPlus Token (从 http://www.pushplus.plus/ 获取)
pushplus_token: "your_token_here"

# 抓拍间隔（秒）
capture_interval: 30

# Top N 榜单数量
top_n: 3
```

### 3. 启动

**方式一：Streamlit 可视化界面**

```bash
streamlit run app.py
```

然后打开浏览器访问 http://localhost:8501

**方式二：后台服务模式**

```bash
python main.py
```

## 📋 功能说明

### Streamlit 界面

| 区域 | 功能 |
|------|------|
| 侧边栏 | 配置 RTSP 地址、API Token、抓拍间隔等参数 |
| 控制台 | 立即抓拍测试、漫画重绘、生成连环画、立即推送 |
| 精选展示 | 今日 Top N 照片预览 |
| 日志区 | 实时查看系统运行状态 |

### API 服务

本项目使用 [ModelScope](https://modelscope.cn/) 提供的 AI 模型：

- **人物检测**：`damo/cv_vit_image-classification_coco`
- **审美打分**：`damo/cv_resnet_image-quality-assessment-mos_youtubeUGC`
- **漫画重绘**：`damo/cv_unet_person-image-cartoon-sd-illustration_compound-models`

### 推送服务

使用 [PushPlus](http://www.pushplus.plus/) 将漫画连环画推送到微信：

1. 关注 PushPlus 微信公众号
2. 获取专属 Token
3. 填入配置文件

## 📁 项目结构

```
comic_butler/
├── app.py                 # Streamlit 界面
├── main.py                # 后台服务入口
├── config_manager.py      # 配置管理
├── vision_client.py       # ModelScope AI 客户端
├── image_utils.py         # 图像处理工具
├── ranking_manager.py     # Top N 排名管理
├── push_client.py         # PushPlus 推送
├── scheduler.py           # 定时任务调度
├── rtsp_capture.py        # RTSP 视频流捕获
├── config.yaml            # 配置文件
├── requirements.txt       # 依赖列表
└── data/                  # 数据目录
    ├── captures/          # 原始抓拍
    ├── cartoons/          # 漫画重绘
    └── collages/          # 拼接长图
```

## ⚠️ 注意事项

1. **Token 安全**：请勿将 API Token 提交到公开仓库
2. **网络要求**：需要能够访问 ModelScope 和 PushPlus API
3. **摄像头兼容**：支持标准 RTSP 协议的摄像头

## 📝 更新日志

### v1.0.0 (2026-01-15)

- 初始版本发布
- 支持 RTSP 摄像头连接
- 集成 ModelScope AI 服务
- 实现漫画连环画生成
- 添加 PushPlus 微信推送
- 提供 Streamlit 可视化界面
