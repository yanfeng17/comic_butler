# -*- coding: utf-8 -*-
"""
AI 家庭漫画管家 - Streamlit 可视化后台

功能：
- 参数设置（侧边栏）
- 实时调试（立即抓拍/立即推送）
- 今日 Top N 展示
- 实时日志窗格
"""

import streamlit as st
import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
from datetime import datetime, date
from pathlib import Path
import threading
import time
from typing import List, Optional

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from config_manager import get_config_manager
from ranking_manager import RankingManager
from rtsp_capture import get_rtsp_capture, RTSPCapture
from vision_client import get_vision_client
from push_client import get_push_client
from scheduler import get_scheduler
from image_utils import create_comic_collage, save_collage
from gemini_client import get_gemini_client
from detector.local_detector import FaceDetector


# ========== 页面配置 ==========
st.set_page_config(
    page_title="AI 家庭漫画管家",
    page_icon="🎨",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ========== 自定义样式 ==========
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;500;600;700&family=Nunito:wght@300;400;500;600;700&display=swap');
    :root {
        --bg: #0b1220;
        --surface: #111827;
        --surface-alt: #1f2937;
        --border: #253348;
        --text: #f8fafc;
        --muted: #94a3b8;
        --accent: #22c55e;
        --accent-strong: #16a34a;
        --success: #22c55e;
        --warning: #f59e0b;
        --danger: #ef4444;
        --shadow: 0 12px 28px rgba(2, 6, 23, 0.65);
    }
    html, body, [class*="css"] {
        font-family: 'Nunito', sans-serif;
        color: var(--text);
    }
    .stApp {
        background:
            radial-gradient(900px 500px at 15% -10%, rgba(56, 189, 248, 0.12) 0%, rgba(56, 189, 248, 0) 60%),
            radial-gradient(800px 420px at 90% -10%, rgba(34, 197, 94, 0.12) 0%, rgba(34, 197, 94, 0) 60%),
            var(--bg);
    }
    h1, h2, h3 {
        font-family: 'Fredoka', sans-serif;
        color: var(--text);
        letter-spacing: 0.2px;
    }
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        border: 1px solid var(--border);
        background: var(--surface);
        color: var(--text);
        box-shadow: none;
        transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;
    }
    .stButton>button:hover {
        border-color: var(--accent);
        box-shadow: 0 6px 18px rgba(34, 197, 94, 0.18);
        transform: translateY(-1px);
    }
    button[data-testid="baseButton-primary"] {
        background: var(--accent);
        color: #fff;
        border-color: var(--accent-strong);
        box-shadow: 0 10px 24px rgba(34, 197, 94, 0.25);
    }
    button[data-testid="baseButton-primary"]:hover {
        border-color: var(--accent-strong);
        box-shadow: 0 12px 26px rgba(34, 197, 94, 0.32);
    }
    div[data-testid="stMetric"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 12px 16px;
        box-shadow: var(--shadow);
    }
    .section-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 18px 20px;
        box-shadow: var(--shadow);
        margin-bottom: 18px;
    }
    .status-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 14px 16px;
        box-shadow: var(--shadow);
    }
    .status-title {
        color: var(--muted);
        font-size: 0.85rem;
        margin-bottom: 6px;
        letter-spacing: 0.4px;
    }
    .status-value {
        font-family: 'Fredoka', sans-serif;
        font-size: 1.1rem;
    }
    .status-ok { color: var(--success); }
    .status-warn { color: var(--warning); }
    .status-bad { color: var(--danger); }
    .image-card {
        background: var(--surface-alt);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 12px;
    }
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.3px;
        background: var(--surface);
        border: 1px solid var(--border);
        color: var(--muted);
    }
    .badge-success {
        color: var(--success);
        border-color: rgba(34, 197, 94, 0.35);
        background: rgba(34, 197, 94, 0.15);
    }
    .badge-warning {
        color: #fbbf24;
        border-color: rgba(245, 158, 11, 0.4);
        background: rgba(245, 158, 11, 0.15);
    }
    .alert-card {
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 14px 16px;
        margin-bottom: 16px;
    }
    .alert-title {
        font-family: 'Fredoka', sans-serif;
        font-weight: 600;
        margin-bottom: 4px;
    }
    .alert-body {
        color: var(--muted);
        font-size: 0.95rem;
    }
    div[data-testid="stSidebar"] {
        background: #0f172a;
        border-right: 1px solid var(--border);
        color: var(--text);
    }
    div[data-testid="stSidebar"] pre {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 8px 10px;
        color: var(--text);
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 12px;
        line-height: 1.35;
        margin-bottom: 6px;
    }
    .stCaption, .stMarkdown p, .stMarkdown span, .stMarkdown li {
        color: var(--muted);
    }
    .stMarkdown strong {
        color: var(--text);
    }
    label, .stTextInput label, .stTextArea label, .stSelectbox label,
    .stCheckbox label, .stRadio label, .stSlider label {
        color: var(--text);
    }
    .stTextInput input, .stTextArea textarea, .stNumberInput input {
        background: var(--surface);
        color: var(--text);
        border: 1px solid var(--border);
    }
    .stSelectbox div[data-baseweb="select"] > div {
        background: var(--surface);
        color: var(--text);
        border: 1px solid var(--border);
    }
    .stSelectbox svg, .stTextInput svg, .stNumberInput svg {
        color: var(--muted);
    }
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {
        color: #64748b;
    }
    .stMarkdown a {
        color: var(--accent);
    }
    
    /* Hide Streamlit elements */
    div[data-testid="stToolbar"] { visibility: hidden; height: 0%; position: fixed; }
    div[data-testid="stDecoration"] { visibility: hidden; height: 0%; position: fixed; }
    div[data-testid="stStatusWidget"] { visibility: hidden; height: 0%; position: fixed; }
    #MainMenu { visibility: hidden; height: 0%; }
    header { visibility: hidden; height: 0%; }
    footer { visibility: hidden; height: 0%; }
</style>
""", unsafe_allow_html=True)


# ========== 全局状态管理 ==========
class GlobalState:
    def __init__(self):
        self.logs: List[str] = []
        self.ranking_manager: Optional[RankingManager] = None
        self.last_capture_time: Optional[datetime] = None
        self.rtsp_connected: bool = False
        
        # 初始化 ranking_manager
        config = get_config_manager()
        data_dir = Path(__file__).parent / "data"
        self.ranking_manager = RankingManager(str(data_dir), config.get('top_n', 3))

@st.cache_resource
def get_global_state() -> GlobalState:
    return GlobalState()

AUTH_FILE = Path(__file__).parent / "data" / "auth.json"

# ========== Session State 初始化 (仅用于 UI 状态) ==========
def init_session_state():
    """初始化 Session State"""
    # UI 相关的临时状态仍保留在 session_state
    if 'last_capture_result' not in st.session_state:
        st.session_state.last_capture_result = None
    
    if 'last_cartoon_results' not in st.session_state:
        st.session_state.last_cartoon_results = None
    
    if 'scheduler_started' not in st.session_state:
        st.session_state.scheduler_started = False

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if "auth_user" not in st.session_state:
        st.session_state.auth_user = ""


def add_log(message: str):
    """添加日志 (全局)"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {sanitize_log_message(message)}"
    
    # 更新全局日志
    state = get_global_state()
    state.logs.append(log_entry)
    
    # 保留最近 100 条
    if len(state.logs) > 100:
        state.logs = state.logs[-100:]
            
    # 如果在 Streamlit 上下文中，也可以尝试打印到控制台辅助调试
    print(f"[Log] {log_entry}")


LOG_REPLACEMENTS = {
    "✅": "[OK]",
    "❌": "[ERR]",
    "⚠️": "[WARN]",
    "⏰": "[TIMER]",
    "🚀": "[START]",
    "🗑️": "[DEL]",
    "📤": "[PUSH]",
    "🎨": "[ART]",
    "📸": "[CAP]",
    "🤖": "[AI]",
    "🔍": "[SCAN]",
    "👤": "[FACE]",
    "📊": "[STAT]",
    "🏆": "[TOP]",
    "⚙️": "[CFG]",
}

GRID_COLUMNS = 3


def sanitize_log_message(message: str) -> str:
    """将常见 emoji 标记替换为文本标签，提升可读性"""
    sanitized = message
    for emoji, text in LOG_REPLACEMENTS.items():
        sanitized = sanitized.replace(emoji, text)
    return sanitized


def get_today_capture_count() -> int:
    """统计今日抓拍数量"""
    capture_dir = Path(__file__).parent / "data" / "captures"
    if not capture_dir.exists():
        return 0
    date_prefix = date.today().strftime("%Y%m%d")
    return sum(1 for _ in capture_dir.glob(f"capture_{date_prefix}_*.jpg"))


def render_status_card(title: str, value: str, tone: str = "neutral") -> None:
    """渲染状态卡片"""
    tone_class = {
        "ok": "status-ok",
        "warn": "status-warn",
        "bad": "status-bad",
    }.get(tone, "")
    st.markdown(
        f"""
        <div class="status-card">
            <div class="status-title">{title}</div>
            <div class="status-value {tone_class}">{value}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_config_alert():
    """渲染配置缺失提示"""
    config = get_config_manager()
    missing = []
    if not config.get("rtsp_url"):
        missing.append("RTSP 地址")
    if not config.get("siliconflow_token"):
        missing.append("SiliconFlow Token")
    if not config.get("pushplus_token"):
        missing.append("PushPlus Token")
    if not config.get("imgbb_api_key"):
        missing.append("ImgBB API Key")

    if missing:
        st.markdown(
            f"""
            <div class="alert-card">
                <div class="alert-title">配置未完成</div>
                <div class="alert-body">请在左侧补充：{'、'.join(missing)}</div>
            </div>
            """,
            unsafe_allow_html=True
        )


def _hash_password(password: str, salt_bytes: bytes) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, 120000)
    return base64.b64encode(digest).decode("ascii")


def load_auth() -> Optional[dict]:
    """加载鉴权配置"""
    if not AUTH_FILE.exists():
        return None
    try:
        with AUTH_FILE.open("r", encoding="utf-8") as file_handle:
            data = json.load(file_handle)
        if not isinstance(data, dict):
            return None
        if not data.get("username"):
            return None
        if data.get("password_hash") and data.get("salt"):
            return data
    except Exception:
        return None
    return None


def save_auth(username: str, password: str) -> None:
    """保存鉴权配置（哈希）"""
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    salt = secrets.token_bytes(16)
    data = {
        "username": username,
        "salt": base64.b64encode(salt).decode("ascii"),
        "password_hash": _hash_password(password, salt),
    }
    with AUTH_FILE.open("w", encoding="utf-8") as file_handle:
        json.dump(data, file_handle, ensure_ascii=False)


def verify_credentials(auth_data: Optional[dict], username: str, password: str) -> bool:
    """验证用户名和密码"""
    if not auth_data or not username or not password:
        return False
    if username != auth_data.get("username"):
        return False
    try:
        salt = base64.b64decode(auth_data.get("salt", ""))
    except Exception:
        return False
    expected = auth_data.get("password_hash", "")
    actual = _hash_password(password, salt)
    return hmac.compare_digest(actual, expected)


def render_auth_gate() -> bool:
    """渲染鉴权入口，返回是否已通过鉴权"""
    auth_data = load_auth()

    if not auth_data:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("首次使用设置账号")
        st.caption("请设置访问账号密码，后续访问需要登录。")
        with st.form("setup_form"):
            username = st.text_input("用户名", value="admin")
            password = st.text_input("密码", type="password", placeholder="请输入密码")
            confirm = st.text_input("确认密码", type="password", placeholder="请再次输入密码")
            submitted = st.form_submit_button("完成设置", use_container_width=True)

        if submitted:
            if not username or not password:
                st.error("用户名和密码不能为空")
            elif password != confirm:
                st.error("两次输入的密码不一致")
            else:
                save_auth(username.strip(), password)
                st.session_state.authenticated = True
                st.session_state.auth_user = username.strip()
                st.success("设置完成，请进入主界面。")
                st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
        return False

    if st.session_state.authenticated:
        return True

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("登录")
    st.caption("请输入账号密码以进入主界面。")
    with st.form("login_form"):
        username = st.text_input("用户名", value=auth_data.get("username", "admin"))
        password = st.text_input("密码", type="password", placeholder="请输入密码")
        submitted = st.form_submit_button("登录", use_container_width=True)

    if submitted:
        if verify_credentials(auth_data, username.strip(), password):
            st.session_state.authenticated = True
            st.session_state.auth_user = username.strip()
            st.success("登录成功。")
            st.rerun()
        else:
            st.error("账号或密码错误")

    st.markdown("</div>", unsafe_allow_html=True)
    return False


def render_status_bar():
    """渲染运行状态概览"""
    state = get_global_state()
    scheduler_status = get_global_scheduler().get_status()
    rankings = state.ranking_manager.get_rankings()

    rtsp_value = "已连接" if state.rtsp_connected else "未连接"
    rtsp_tone = "ok" if state.rtsp_connected else "bad"
    scheduler_value = "运行中" if scheduler_status.get("running") else "未启动"
    scheduler_tone = "ok" if scheduler_status.get("running") else "warn"
    capture_count = f"{get_today_capture_count()} 张"
    selected_count = f"{len(rankings)} 张"

    cols = st.columns(4)
    with cols[0]:
        render_status_card("RTSP 连接", rtsp_value, rtsp_tone)
    with cols[1]:
        render_status_card("调度器状态", scheduler_value, scheduler_tone)
    with cols[2]:
        render_status_card("今日抓拍", capture_count)
    with cols[3]:
        render_status_card("今日入选", selected_count)





# ========== 核心功能 ==========
async def do_capture_and_score():
    """执行抓拍和打分 - 使用 Gemini API"""
    config = get_config_manager()
    state = get_global_state()
    
    # 每次抓拍时重新创建 RTSP 连接，确保获取最新画面
    rtsp_url = config.get('rtsp_url')
    capture = get_rtsp_capture(rtsp_url)
    
    # 强制重新连接
    capture.release()
    if not capture.connect():
        state.rtsp_connected = False
        add_log("❌ RTSP 连接失败")
        return None, 0.0
    state.rtsp_connected = True
    
    # 抓拍
    add_log("正在抓拍...")
    data_dir = Path(__file__).parent / "data" / "captures"
    image_path = capture.capture_and_save(str(data_dir))
    
    if not image_path:
        add_log("❌ 抓拍失败：无法获取画面")
        return None, 0.0
    
    state.last_capture_time = datetime.now()
    add_log(f"✅ 抓拍成功: {Path(image_path).name}")
    
    # 本地人脸检测 (如果启用)
    if config.get('enable_face_detection', False):
        add_log("🔍 正在进行本地人脸检测...")
        detector = FaceDetector.get_instance()
        if not detector.detect_faces(image_path):
            add_log("⚠️ 未检测到人脸 (YOLO)，跳过评分")
            try:
                os.remove(image_path)
            except: pass
            return None, 0.0
        
        add_log("👤 检测到人脸 (YOLO)，继续分析...")

    # 优先使用 SiliconFlow AI 进行分析
    siliconflow_token = config.get('siliconflow_token', '')
    gemini_client = get_gemini_client(siliconflow_token) if siliconflow_token else None
    
    if gemini_client:
        add_log("🤖 使用 SiliconFlow AI 进行分析...")
        
        # 审美打分
        add_log("正在进行审美打分...")
        score = await gemini_client.score_image(image_path)
        add_log(f"✅ 审美评分: {score:.3f}")
        
        await gemini_client.close()
    else:
        # 降级使用 ModelScope 模拟客户端
        add_log("⚠️ Gemini 不可用，使用模拟评分")
        vision_client = get_vision_client(config.get('modelscope_token', ''))
        has_person, label, conf = await vision_client.classify_image(image_path)
        
        if not has_person:
            add_log(f"⚠️ 未检测到人物")
            try:
                os.remove(image_path)
            except:
                pass
            await vision_client.close()
            return None, 0.0
        
        add_log(f"✅ 检测到人物: {label} (置信度: {conf:.2f})")
        score = await vision_client.score_image(image_path)
        add_log(f"✅ 审美评分: {score:.3f}")
        await vision_client.close()
    
    return image_path, score


async def do_add_to_ranking(image_path: str, score: float, keep_for_preview: bool = False):
    """
    将图片加入排名
    
    入选逻辑：
    - 当精选照片不足 Top N 时，自动入选
    - 当精选照片已满时，比较评分，高于最低分则入选
    
    Args:
        image_path: 图片路径
        score: 评分
        keep_for_preview: 是否保留图片用于预览（即使未入选也不删除）
    """
    config = get_config_manager()
    ranking_manager = get_global_state().ranking_manager
    top_n = config.get('top_n', 3)
    
    # 获取当前排名
    current_rankings = ranking_manager.get_rankings()
    current_count = len(current_rankings)
    
    # 判断是否应该入选
    should_add = False
    reason = ""
    
    if current_count < top_n:
        # 精选照片不足，自动入选
        should_add = True
        reason = f"精选不足 {top_n} 张，自动入选"
    else:
        # 精选已满，比较评分
        lowest_score = current_rankings[-1].score if current_rankings else 0
        if score > lowest_score:
            should_add = True
            reason = f"评分 {score:.3f} 高于最低分 {lowest_score:.3f}"
        else:
            reason = f"评分 {score:.3f} 低于最低分 {lowest_score:.3f}"
    
    if should_add:
        # 添加到排名
        timestamp = datetime.now().strftime("%H:%M")
        added, removed = ranking_manager.add_image(image_path, score, timestamp)
        
        if added:
            add_log(f"🏆 入选 Top {top_n}！{reason}")
            if removed:
                add_log(f"📤 淘汰旧照片: {Path(removed).name}")
            return True
    
    add_log(f"📊 未入选：{reason}")
    return False


async def do_cartoon_redraw():
    """漫画重绘 - 使用 Gemini API"""
    config = get_config_manager()
    ranking_manager = get_global_state().ranking_manager
    rankings = ranking_manager.get_rankings()
    
    if not rankings:
        add_log("⚠️ 没有可重绘的照片")
        return []
    
    # 初始化 AI 客户端 (SiliconFlow)
    siliconflow_token = config.get('siliconflow_token', '')
    if not siliconflow_token:
         add_log("⚠️ SiliconFlow Token 未配置，AI 功能不可用")
    
    gemini_client = get_gemini_client(siliconflow_token)
    if siliconflow_token:
        add_log("🎨 AI 引擎就绪 (SiliconFlow)")
    
    cartoon_dir = Path(__file__).parent / "data" / "cartoons"
    
    results = []
    new_count = 0
    skip_count = 0
    
    for i, item in enumerate(rankings):
        # 如果已经重绘过且文件存在，跳过
        if item.cartoon_path and os.path.exists(item.cartoon_path):
            add_log(f"✅ 第 {i+1} 张已有漫画版本，跳过")
            results.append((item.cartoon_path, item.timestamp))
            skip_count += 1
            continue
        
        add_log(f"正在重绘第 {i+1}/{len(rankings)} 张...")
        
        # 检查原图是否存在
        if not os.path.exists(item.image_path):
            add_log(f"⚠️ 第 {i+1} 张原图不存在，跳过")
            continue
        
        # 生成输出路径
        cartoon_filename = f"cartoon_{Path(item.image_path).stem}.jpg"
        cartoon_path = str(cartoon_dir / cartoon_filename)
        
        # 调用 Gemini API 重绘
        try:
            success, error_msg = await gemini_client.cartoon_image(item.image_path, cartoon_path)
        except ValueError:
             # 兼容旧版本如果不返回元组
            success = await gemini_client.cartoon_image(item.image_path, cartoon_path)
            error_msg = "未知错误"

        if success:
            ranking_manager.update_cartoon_path(item.image_path, cartoon_path)
            results.append((cartoon_path, item.timestamp))
            add_log(f"✅ 第 {i+1} 张重绘完成")
            new_count += 1
        else:
            # 重绘失败，使用原图
            results.append((item.image_path, item.timestamp))
            add_log(f"⚠️ 第 {i+1} 张重绘失败: {error_msg}，将使用原图")
    
    await gemini_client.close()
    
    # 记录总结
    if new_count > 0:
        add_log(f"📊 重绘完成：新重绘 {new_count} 张，跳过 {skip_count} 张")
    elif skip_count > 0:
        add_log(f"📊 所有 {skip_count} 张照片已有漫画版本")
    
    return results


async def do_create_collage():
    """创建拼图"""
    add_log("正在生成漫画连环画...")
    
    # 获取漫画图片路径
    ranking_manager = get_global_state().ranking_manager
    cartoon_data = ranking_manager.get_cartoon_paths()
    
    if not cartoon_data:
        add_log("⚠️ 没有可拼接的图片")
        return None
    
    image_paths = [p for p, t in cartoon_data]
    timestamps = [t for p, t in cartoon_data]
    
    # 创建拼图
    collage = create_comic_collage(image_paths, timestamps)
    
    if collage is None:
        add_log("❌ 拼图生成失败")
        return None
    
    # 保存拼图
    collage_dir = Path(__file__).parent / "data" / "collages"
    collage_filename = f"collage_{date.today().isoformat()}.jpg"
    collage_path = str(collage_dir / collage_filename)
    
    if save_collage(collage, collage_path):
        add_log(f"✅ 连环画生成完成: {collage_filename}")
        return collage_path
    else:
        add_log("❌ 保存拼图失败")
        return None


async def do_push(collage_path: str):
    """推送到微信"""
    config = get_config_manager()
    push_client = get_push_client(
        config.get('pushplus_token', ''),
        config.get('imgbb_api_key', '')
    )
    
    add_log("正在推送到微信...")
    
    ranking_manager = get_global_state().ranking_manager
    photo_count = len(ranking_manager.get_rankings())
    
    result = await push_client.push_comic_collage(
        collage_path,
        date_str=date.today().strftime("%Y年%m月%d日"),
        photo_count=photo_count
    )
    
    await push_client.close()
    
    if result.get('code') == 200:
        add_log("✅ 推送成功！")
        return True
    else:
        add_log(f"❌ 推送失败: {result.get('msg')}")
        return False


async def do_full_pipeline():
    """执行完整流程：重绘 + 拼图 + 推送"""
    # 漫画重绘
    await do_cartoon_redraw()
    
    # 创建拼图
    collage_path = await do_create_collage()
    
    if collage_path:
        # 推送
        await do_push(collage_path)
    
    return collage_path


# ========== 定时任务回调 ==========
def scheduled_capture_task():
    """定时抓拍任务（在后台线程中执行）"""
    async def _run():
        add_log("⏰ 执行定时抓拍...")
        image_path, score = await do_capture_and_score()
        if image_path:
            await do_add_to_ranking(image_path, score)
    
    asyncio.run(_run())


def scheduled_push_task():
    """定时推送任务（在后台线程中执行）"""
    async def _run():
        add_log("⏰ 执行定时推送...")
        await do_full_pipeline()
    
    asyncio.run(_run())


@st.cache_resource
def get_global_scheduler():
    return get_scheduler()

def start_scheduler_if_needed():
    """启动调度器（如果需要）"""
    # 使用 session_state 防止重复启动逻辑 (UI刷新时)
    # 但核心调度器实例必须是全局唯一的 (cache_resource)
    
    scheduler = get_global_scheduler()
    
    # 检查调度器是否已经在运行
    status = scheduler.get_status()
    if status['running'] and st.session_state.scheduler_started:
        return
    
    config = get_config_manager()
    
    if not config.get('auto_capture_enabled') and not config.get('auto_push_enabled'):
        return
    
    scheduler.set_capture_callback(scheduled_capture_task)
    scheduler.set_push_callback(scheduled_push_task)
    
    scheduler.start()
    
    if config.get('auto_capture_enabled'):
        scheduler.schedule_capture(config.get('capture_interval', 30))
    
    if config.get('auto_push_enabled'):
        scheduler.schedule_push(config.get('push_times', []))
    
    st.session_state.scheduler_started = True
    add_log("🚀 调度器已启动")


# ========== 侧边栏 ==========
def render_sidebar():
    """渲染侧边栏设置"""
    st.sidebar.title("设置")

    if st.session_state.get("authenticated"):
        st.sidebar.caption(f"当前用户：{st.session_state.get('auth_user') or 'admin'}")
        if st.sidebar.button("退出登录", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.auth_user = ""
            st.rerun()
        st.sidebar.markdown("---")
    
    config = get_config_manager()
    current_config = config.get_all()
    
    # RTSP 设置
    st.sidebar.subheader("摄像头设置")
    rtsp_url = st.sidebar.text_input(
        "RTSP 地址",
        value=current_config.get('rtsp_url', ''),
        help="格式: rtsp://user:password@ip:port/path"
    )
    
    # API 设置
    st.sidebar.subheader("API 配置")
    siliconflow_token = st.sidebar.text_input(
        "SiliconFlow Token",
        value=current_config.get('siliconflow_token', ''),
        type="password",
        help="点击下方链接注册/获取"
    )
    st.sidebar.markdown("[获取 SiliconFlow Token](https://cloud.siliconflow.cn/i/nSTUhFZV)")
    
    pushplus_token = st.sidebar.text_input(
        "PushPlus Token",
        value=current_config.get('pushplus_token', ''),
        type="password",
        help="用于微信推送"
    )
    st.sidebar.markdown("[获取 PushPlus Token](http://www.pushplus.plus/)")
    
    imgbb_api_key = st.sidebar.text_input(
        "ImgBB API Key (图床)",
        value=current_config.get('imgbb_api_key', ''),
        type="password",
        help="用于更清晰的图片推送"
    )
    st.sidebar.markdown("[获取 ImgBB API Key](https://api.imgbb.com/)")

    # Model Selection
    st.sidebar.subheader("模型选择 (SiliconFlow)")
    
    # Scoring Model
    scoring_models = ["THUDM/GLM-4.1V-9B-Thinking", "Qwen/Qwen3-VL-30B-A3B-Instruct", "自定义"]
    current_scoring = current_config.get('scoring_model', 'THUDM/GLM-4.1V-9B-Thinking')
    
    scoring_index = 0
    if current_scoring in scoring_models:
        scoring_index = scoring_models.index(current_scoring)
    else:
        scoring_index = 2 # Custom
        
    selected_scoring = st.sidebar.selectbox(
        "AI 评分模型",
        scoring_models,
        index=scoring_index
    )
    
    final_scoring_model = selected_scoring
    if selected_scoring == "自定义":
        final_scoring_model = st.sidebar.text_input("输入评分模型名称", value=current_scoring)

    # Cartoon Model
    # 移除了 Kolors，因为是 T2I 模型不适合重绘
    cartoon_models = ["Qwen/Qwen-Image-Edit-2509", "自定义"]
    current_cartoon = current_config.get('cartoon_model', 'Qwen/Qwen-Image-Edit-2509')
    
    cartoon_index = 0
    if current_cartoon in cartoon_models:
        cartoon_index = cartoon_models.index(current_cartoon)
    else:
        # 如果当前配置是旧的 Kolors，或者其他自定义值
        if "Kolors" in current_cartoon:
            cartoon_index = 0 # 默认回 Qwen
        else:
            cartoon_index = 1 # Custom

    selected_cartoon = st.sidebar.selectbox(
        "漫画重绘模型",
        cartoon_models,
        index=cartoon_index
    )
    
    final_cartoon_model = selected_cartoon
    if selected_cartoon == "自定义":
        final_cartoon_model = st.sidebar.text_input("输入重绘模型名称", value=current_cartoon)
    
    # 抓拍设置
    st.sidebar.subheader("抓拍设置")
    capture_interval = st.sidebar.slider(
        "抓拍间隔（秒）",
        min_value=10,
        max_value=300,
        value=current_config.get('capture_interval', 30),
        step=10
    )
    
    auto_capture = st.sidebar.checkbox(
        "启用自动抓拍",
        value=current_config.get('auto_capture_enabled', True)
    )
    
    enable_face_detection = st.sidebar.checkbox(
        "启用人脸检测 (YOLO)",
        value=current_config.get('enable_face_detection', False),
        help="使用本地 YOLOv8 模型检测人脸，无人脸则跳过评分"
    )
    
    # 排名设置
    st.sidebar.subheader("排名设置")
    top_n = st.sidebar.slider(
        "Top N 数量",
        min_value=1,
        max_value=5,
        value=current_config.get('top_n', 3)
    )
    
    
    # 质量阈值保留在配置中，但在 UI 上隐藏（或移动到高级设置）
    # default_quality = current_config.get('quality_threshold', 0.5)

    
    # 推送设置
    st.sidebar.subheader("推送设置")
    push_times_str = st.sidebar.text_input(
        "推送时间",
        value=", ".join(current_config.get('push_times', [])),
        help="逗号分隔，如: 12:00, 18:00, 21:00"
    )
    
    auto_push = st.sidebar.checkbox(
        "启用自动推送",
        value=current_config.get('auto_push_enabled', True)
    )
    
    # 高级提示词设置
    with st.sidebar.expander("高级提示词设置"):
        scoring_prompt = st.text_area(
            "AI 评分标准提示词",
            value=current_config.get('scoring_prompt', ''),
            height=150,
            help="定义 Gemini 如何对照片进行审美评分"
        )
        
        # 漫画风格预设
        CARTOON_PRESETS = {
            "自定义": "",
            "温馨治愈国漫风": "温馨治愈系国漫风格，柔和的赛璐璐上色，明亮的自然光，色彩清新雅致，线条流畅，高品质，细节丰富，画面温暖，保留图片中人物和背景的主要特征",
            "经典淡彩连环画风": "经典中国连环画风格，手绘插画质感，清晰的勾线，淡雅的水彩晕染，复古氛围，细腻的笔触，富有故事感，宁静祥和，保留图片中人物和背景的主要特征",
            "现代清新插画风": "现代清新插画风格，矢量艺术，扁平化设计，明亮的色块，简约时尚，色彩鲜艳，充满活力，保留图片中人物和背景的主要特征"
        }

        # 初始化 Session State (如果尚未初始化)
        if 'cartoon_prompt_text' not in st.session_state:
            initial_prompt = current_config.get('cartoon_prompt', '')
            st.session_state.cartoon_prompt_text = initial_prompt
            
            # 判断当前提示词是否匹配预设
            initial_style = "自定义"
            for name, content in CARTOON_PRESETS.items():
                if name != "自定义" and content.strip() == initial_prompt.strip():
                    initial_style = name
                    break
            st.session_state.style_selection = initial_style

        def on_style_change():
            """当选择预设风格时，更新提示词内容"""
            style = st.session_state.style_selection
            # 无论何种选择（包括自定义），都更新提示词内容
            # 自定义在 CARTOON_PRESETS 中对应空字符串，正好清空
            st.session_state.cartoon_prompt_text = CARTOON_PRESETS[style]
        
        def on_prompt_text_change():
            """当手动修改提示词时，检查是否匹配预设"""
            current = st.session_state.cartoon_prompt_text
            new_style = "自定义"
            for name, content in CARTOON_PRESETS.items():
                if name != "自定义" and content.strip() == current.strip():
                    new_style = name
                    break
            st.session_state.style_selection = new_style

        st.selectbox(
            "选择漫画风格预设",
            options=list(CARTOON_PRESETS.keys()),
            key="style_selection",
            on_change=on_style_change,
            help="选择预设风格自动填充提示词"
        )
        
        cartoon_prompt = st.text_area(
            "漫画重绘风格提示词",
            value=st.session_state.cartoon_prompt_text,  # 这里的 value 其实主要由 key 控制
            key="cartoon_prompt_text",
            on_change=on_prompt_text_change,
            height=150,
            help="定义 AI 如何将照片转换为漫画风格。您可以从上方选择预设，也可以在此处自由编辑。"
        )
    
    # 保存按钮
    if st.sidebar.button("保存设置", use_container_width=True):
        # 解析推送时间
        push_times = [t.strip() for t in push_times_str.split(',') if t.strip()]
        
        # 更新配置
        new_config = {
            'rtsp_url': rtsp_url,
            'siliconflow_token': siliconflow_token,
            'scoring_model': final_scoring_model,
            'cartoon_model': final_cartoon_model,
            'pushplus_token': pushplus_token,
            'imgbb_api_key': imgbb_api_key,
            'capture_interval': capture_interval,
            'auto_capture_enabled': auto_capture,
            'enable_face_detection': enable_face_detection,
            'top_n': top_n,
            # 'quality_threshold': quality_threshold, # 保持原值
            'push_times': push_times,
            'auto_push_enabled': auto_push,
            'scoring_prompt': scoring_prompt,
            'cartoon_prompt': cartoon_prompt,
        }
        
        config.update(new_config)
        
        # 更新排名管理器的 Top N
        get_global_state().ranking_manager.set_top_n(top_n)
        
        # 更新调度器
        if st.session_state.scheduler_started:
            scheduler = get_global_scheduler()
            if auto_capture:
                scheduler.schedule_capture(capture_interval)
            else:
                scheduler.pause_capture()
            
            if auto_push:
                scheduler.schedule_push(push_times)
        
        add_log("⚙️ 设置已保存")
        st.sidebar.success("设置已保存！")
        st.rerun()
    
    # 配置验证
    is_valid, errors = config.validate()
    if not is_valid:
        st.sidebar.warning("⚠️ 配置问题：")
        for err in errors:
            st.sidebar.caption(f"• {err}")

    # 显示全局实时日志
    st.sidebar.markdown("---")
    st.sidebar.subheader("实时日志")
    
    # 自动刷新开关
    auto_refresh = st.sidebar.checkbox("开启实时监控 (自动刷新)", value=True, help="每 2 秒刷新一次界面以查看最新日志")
    st.session_state.auto_refresh = auto_refresh

    log_filter = st.sidebar.selectbox(
        "日志筛选",
        ["全部", "仅错误", "仅警告", "仅成功"]
    )
    
    log_container = st.sidebar.container()
    with log_container:
        state = get_global_state()
        # 显示最近的 15 条日志，倒序
        recent_logs = state.logs[-20:][::-1]
        if log_filter != "全部":
            if log_filter == "仅错误":
                recent_logs = [log for log in recent_logs if "[ERR]" in log]
            elif log_filter == "仅警告":
                recent_logs = [log for log in recent_logs if "[WARN]" in log]
            elif log_filter == "仅成功":
                recent_logs = [log for log in recent_logs if "[OK]" in log]

        if recent_logs:
            for log in recent_logs:
                st.text(log)
        else:
            st.caption("暂无匹配日志")


# ========== 主界面 ==========
def render_main():
    """渲染主界面"""
    st.title("AI 家庭漫画管家")
    st.caption("自动抓拍精彩瞬间，生成漫画风格连环画")

    render_config_alert()
    render_status_bar()
    
    # 调试控制区
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("控制台")
    st.caption("手动触发抓拍、重绘、拼图与推送")

    row1 = st.columns(2)
    row2 = st.columns(2)

    with row1[0]:
        if st.button("立即抓拍测试", use_container_width=True):
            # 清理上一次未入选的预览图片
            if st.session_state.last_capture_result:
                old_result = st.session_state.last_capture_result
                old_path = old_result['path']
                # 检查是否在排名中
                is_in_ranking = False
                for item in get_global_state().ranking_manager.get_rankings():
                    if item.image_path == old_path:
                        is_in_ranking = True
                        break
                # 如果未入选，删除旧图片
                if not is_in_ranking and os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                        add_log(f"🗑️ 已清理上次未入选的预览图片")
                    except:
                        pass
            
            with st.spinner("抓拍中..."):
                async def _capture():
                    image_path, score = await do_capture_and_score()
                    if image_path:
                        # keep_for_preview=True 保留图片用于预览，即使未入选也不删除
                        await do_add_to_ranking(image_path, score, keep_for_preview=True)
                    return image_path, score
                
                image_path, score = asyncio.run(_capture())
                
                if image_path:
                    # 保存抓拍结果用于预览
                    st.session_state.last_capture_result = {
                        'path': image_path,
                        'score': score,
                        'time': datetime.now().strftime("%H:%M:%S")
                    }
                    st.success(f"抓拍成功！评分: {score:.3f}")
                else:
                    st.session_state.last_capture_result = None
                    st.warning("抓拍未成功或未检测到人物")
                
                st.rerun()
        st.caption("即时抓拍并评分")
    
    with row1[1]:
        if st.button("漫画重绘", use_container_width=True):
            with st.spinner("正在重绘..."):
                async def _redraw():
                    return await do_cartoon_redraw()
                
                results = asyncio.run(_redraw())
                
                if results:
                    # 保存重绘结果用于预览
                    st.session_state.last_cartoon_results = results
                    st.success(f"已完成 {len(results)} 张重绘")
                else:
                    st.session_state.last_cartoon_results = None
                    st.warning("没有可重绘的照片")
                
                st.rerun()
        st.caption("对入选照片进行重绘")
    
    with row2[0]:
        if st.button("生成连环画", use_container_width=True):
            with st.spinner("正在生成..."):
                async def _collage():
                    return await do_create_collage()
                
                collage_path = asyncio.run(_collage())
                
                if collage_path:
                    st.success("连环画已生成")
                else:
                    st.warning("生成失败或没有图片")
                
                st.rerun()
        st.caption("将漫画按时间拼接")
    
    with row2[1]:
        if st.button("立即推送", type="primary", use_container_width=True):
            with st.spinner("正在处理..."):
                async def _push():
                    return await do_full_pipeline()
                
                collage_path = asyncio.run(_push())
                
                if collage_path:
                    st.success("推送完成！")
                else:
                    st.warning("推送处理失败")
                
                st.rerun()
        st.caption("推送到微信")

    st.markdown("</div>", unsafe_allow_html=True)
    
    # 显示最新抓拍预览
    if st.session_state.last_capture_result:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("最新抓拍预览")
        
        result = st.session_state.last_capture_result
        is_in_ranking = False
        
        # 检查图片是否在排名中
        rankings = get_global_state().ranking_manager.get_rankings()
        for item in rankings:
            if item.image_path == result['path']:
                is_in_ranking = True
                break
        
        col_preview, col_info = st.columns([2, 1])
        
        with col_preview:
            if os.path.exists(result['path']):
                st.markdown('<div class="image-card">', unsafe_allow_html=True)
                st.image(result['path'], caption=f"抓拍时间: {result['time']}", use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.warning("预览图片已不存在")
        
        with col_info:
            st.metric("评分", f"{result['score']:.3f}")
            st.caption(f"文件: {Path(result['path']).name}")
            
            # 显示入选状态
            if is_in_ranking:
                st.markdown('<span class="badge badge-success">已入选</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="badge badge-warning">未入选</span>', unsafe_allow_html=True)
            
            if st.button("关闭预览", use_container_width=True):
                # 如果图片未入选，删除它
                if not is_in_ranking and os.path.exists(result['path']):
                    try:
                        os.remove(result['path'])
                        add_log(f"🗑️ 已清理未入选的预览图片")
                    except:
                        pass
                st.session_state.last_capture_result = None
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    
    # 显示漫画重绘结果预览
    if st.session_state.last_cartoon_results:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("漫画重绘结果")
        
        results = st.session_state.last_cartoon_results
        columns_per_row = GRID_COLUMNS
        for i, (cartoon_path, timestamp) in enumerate(results):
            if i % columns_per_row == 0:
                cols = st.columns(columns_per_row)
            with cols[i % columns_per_row]:
                st.markdown(f"**#{i+1}** · {timestamp}")
                if cartoon_path and os.path.exists(cartoon_path):
                    st.markdown('<div class="image-card">', unsafe_allow_html=True)
                    st.image(cartoon_path, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.warning("图片不可用")
        
        # 关闭预览按钮
        if st.button("关闭重绘预览", use_container_width=True):
            st.session_state.last_cartoon_results = None
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    
    # 今日 Top N 展示
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("今日精选")
    
    rankings = get_global_state().ranking_manager.get_rankings()
    
    if rankings:
        columns_per_row = GRID_COLUMNS
        for i, item in enumerate(rankings):
            if i % columns_per_row == 0:
                cols = st.columns(columns_per_row)
            with cols[i % columns_per_row]:
                st.markdown(f"**#{i+1}** · {item.timestamp}")
                
                # 显示图片
                display_path = item.cartoon_path if item.cartoon_path and os.path.exists(item.cartoon_path) else item.image_path
                
                if display_path and os.path.exists(display_path):
                    st.markdown('<div class="image-card">', unsafe_allow_html=True)
                    st.image(display_path, use_container_width=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.info("图片不可用")
                
                st.caption(f"评分: {item.score:.3f}")
                
                # 删除按钮
                if st.button("删除", key=f"delete_{i}", use_container_width=True):
                    get_global_state().ranking_manager.remove_image(item.image_path)
                    add_log(f"🗑️ 已删除精选照片 #{i+1}")
                    st.rerun()
    else:
        st.info("今日暂无精选照片，点击「立即抓拍测试」开始捕捉精彩瞬间。")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # 预览最新拼图
    collage_dir = Path(__file__).parent / "data" / "collages"
    today_collage = collage_dir / f"collage_{date.today().isoformat()}.jpg"
    
    if today_collage.exists():
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("今日连环画预览")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image(str(today_collage), caption="今日家庭漫画连环画", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    



# ========== 主函数 ==========
def main():
    """主函数"""
    init_session_state()
    start_scheduler_if_needed()
    if not render_auth_gate():
        return

    render_sidebar()
    render_main()
    
    # 自动刷新逻辑
    if st.session_state.get('auto_refresh', False):
        import time
        time.sleep(2)
        st.rerun()


if __name__ == "__main__":
    main()
