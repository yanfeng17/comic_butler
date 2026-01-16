# -*- coding: utf-8 -*-
"""
AI 家庭漫画管家 - 主入口

启动方式：
1. Streamlit 界面模式: streamlit run app.py
2. 后台服务模式: python main.py

使用此入口文件启动时，将在无界面模式下运行定时任务。
"""

import asyncio
import signal
import sys
import os
from datetime import datetime
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from config_manager import get_config_manager
from ranking_manager import RankingManager
from rtsp_capture import get_rtsp_capture
from vision_client import get_vision_client
from push_client import get_push_client
from scheduler import get_scheduler
from image_utils import create_comic_collage, save_collage


# 全局变量
data_dir = Path(__file__).parent / "data"
ranking_manager: RankingManager = None
rtsp_capture = None
running = True


def log(message: str):
    """打印日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")


async def capture_task():
    """抓拍任务"""
    global ranking_manager, rtsp_capture
    
    config = get_config_manager()
    
    try:
        log("开始执行抓拍任务...")
        
        # 确保 RTSP 连接
        if rtsp_capture is None:
            rtsp_capture = get_rtsp_capture(config.get('rtsp_url'))
            rtsp_capture.connect()
            rtsp_capture.start_background_capture()
        
        # 抓拍
        capture_dir = data_dir / "captures"
        image_path = rtsp_capture.capture_and_save(str(capture_dir))
        
        if not image_path:
            log("抓拍失败：无法获取画面")
            return
        
        log(f"抓拍成功: {Path(image_path).name}")
        
        # 人物检测
        vision_client = get_vision_client(config.get('modelscope_token', ''))
        has_person, label, conf = await vision_client.classify_image(image_path)
        
        if not has_person:
            log(f"未检测到人物 (检测到: {label})")
            try:
                os.remove(image_path)
            except:
                pass
            await vision_client.close()
            return
        
        log(f"检测到人物: {label} (置信度: {conf:.2f})")
        
        # 审美打分
        score = await vision_client.score_image(image_path)
        log(f"审美评分: {score:.3f}")
        
        await vision_client.close()
        
        # 检查阈值
        threshold = config.get('quality_threshold', 0.5)
        if score < threshold:
            log(f"评分低于阈值 {threshold}，不入选")
            try:
                os.remove(image_path)
            except:
                pass
            return
        
        # 加入排名
        timestamp = datetime.now().strftime("%H:%M")
        added, removed = ranking_manager.add_image(image_path, score, timestamp)
        
        if added:
            log(f"入选 Top {config.get('top_n')}！")
        else:
            log("评分不足以入选排行榜")
            
    except Exception as e:
        log(f"抓拍任务异常: {e}")


async def push_task():
    """推送任务"""
    global ranking_manager
    
    config = get_config_manager()
    
    try:
        log("开始执行推送任务...")
        
        rankings = ranking_manager.get_rankings()
        if not rankings:
            log("没有可推送的照片")
            return
        
        # 漫画重绘
        vision_client = get_vision_client(config.get('modelscope_token', ''))
        cartoon_dir = data_dir / "cartoons"
        
        for i, item in enumerate(rankings):
            if item.cartoon_path and os.path.exists(item.cartoon_path):
                continue
            
            log(f"正在重绘第 {i+1}/{len(rankings)} 张...")
            
            cartoon_filename = f"cartoon_{Path(item.image_path).stem}.jpg"
            cartoon_path = str(cartoon_dir / cartoon_filename)
            
            success = await vision_client.cartoon_image(item.image_path, cartoon_path)
            
            if success:
                ranking_manager.update_cartoon_path(item.image_path, cartoon_path)
                log(f"第 {i+1} 张重绘完成")
            else:
                log(f"第 {i+1} 张重绘失败")
        
        await vision_client.close()
        
        # 创建拼图
        log("正在生成连环画...")
        cartoon_data = ranking_manager.get_cartoon_paths()
        
        if not cartoon_data:
            log("没有可拼接的图片")
            return
        
        image_paths = [p for p, t in cartoon_data]
        timestamps = [t for p, t in cartoon_data]
        
        collage = create_comic_collage(image_paths, timestamps)
        
        if collage is None:
            log("拼图生成失败")
            return
        
        collage_dir = data_dir / "collages"
        from datetime import date
        collage_filename = f"collage_{date.today().isoformat()}.jpg"
        collage_path = str(collage_dir / collage_filename)
        
        if not save_collage(collage, collage_path):
            log("保存拼图失败")
            return
        
        log(f"连环画生成完成: {collage_filename}")
        
        # 推送
        log("正在推送到微信...")
        push_client = get_push_client(config.get('pushplus_token', ''))
        
        result = await push_client.push_comic_collage(
            collage_path,
            date_str=date.today().strftime("%Y年%m月%d日"),
            photo_count=len(rankings)
        )
        
        await push_client.close()
        
        if result.get('code') == 200:
            log("推送成功！")
        else:
            log(f"推送失败: {result.get('msg')}")
            
    except Exception as e:
        log(f"推送任务异常: {e}")


def capture_task_sync():
    """同步版抓拍任务（给调度器使用）"""
    asyncio.run(capture_task())


def push_task_sync():
    """同步版推送任务（给调度器使用）"""
    asyncio.run(push_task())


def signal_handler(sig, frame):
    """信号处理"""
    global running
    log("收到退出信号，正在关闭...")
    running = False


def main():
    """主函数"""
    global ranking_manager, rtsp_capture, running
    
    log("=" * 50)
    log("AI 家庭漫画管家 - 后台服务模式")
    log("=" * 50)
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 加载配置
    config = get_config_manager()
    log(f"配置已加载: {config.config_path}")
    
    # 验证配置
    is_valid, errors = config.validate()
    if not is_valid:
        log("配置验证失败:")
        for err in errors:
            log(f"  - {err}")
        log("请检查 config.yaml 并重新运行")
        return
    
    # 初始化排名管理器
    ranking_manager = RankingManager(str(data_dir), config.get('top_n', 3))
    log(f"排名管理器已初始化 (Top {config.get('top_n')})")
    
    # 初始化 RTSP 捕获器
    rtsp_capture = get_rtsp_capture(config.get('rtsp_url'))
    if rtsp_capture.connect():
        log("RTSP 连接成功")
        rtsp_capture.start_background_capture()
    else:
        log("RTSP 连接失败，将在任务执行时重试")
    
    # 初始化调度器
    scheduler = get_scheduler()
    scheduler.set_capture_callback(capture_task_sync)
    scheduler.set_push_callback(push_task_sync)
    scheduler.start()
    
    # 配置任务
    if config.get('auto_capture_enabled'):
        interval = config.get('capture_interval', 30)
        scheduler.schedule_capture(interval)
        log(f"定时抓拍已启用: 每 {interval} 秒")
    
    if config.get('auto_push_enabled'):
        push_times = config.get('push_times', [])
        scheduler.schedule_push(push_times)
        log(f"定时推送已启用: {', '.join(push_times)}")
    
    log("后台服务运行中，按 Ctrl+C 退出")
    log("-" * 50)
    
    # 主循环
    try:
        while running:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        log("正在清理资源...")
        
        scheduler.stop()
        
        if rtsp_capture:
            rtsp_capture.release()
        
        log("服务已停止")


if __name__ == "__main__":
    main()
