# -*- coding: utf-8 -*-
"""
RTSP 视频流捕获模块
负责连接摄像头并抓取画面
"""

import cv2
import numpy as np
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from queue import Queue, Empty


class RTSPCapture:
    """
    RTSP 视频流捕获器
    
    功能：
    - 连接 RTSP 视频流
    - 抓取当前画面
    - 自动重连机制
    - 后台线程持续拉流（保持流畅）
    """
    
    def __init__(self, rtsp_url: str, reconnect_interval: int = 5):
        """
        初始化捕获器
        
        Args:
            rtsp_url: RTSP 流地址
            reconnect_interval: 重连间隔（秒）
        """
        self.rtsp_url = rtsp_url
        self.reconnect_interval = reconnect_interval
        
        self._cap: Optional[cv2.VideoCapture] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._running = False
        self._connected = False
        self._capture_thread: Optional[threading.Thread] = None
        
        # 连接状态回调
        self._on_status_change: Optional[Callable[[bool, str], None]] = None
    
    def set_status_callback(self, callback: Callable[[bool, str], None]):
        """
        设置连接状态变化回调
        
        Args:
            callback: 回调函数，参数为 (是否连接, 状态消息)
        """
        self._on_status_change = callback
    
    def _notify_status(self, connected: bool, message: str):
        """通知状态变化"""
        self._connected = connected
        if self._on_status_change:
            try:
                self._on_status_change(connected, message)
            except Exception as e:
                print(f"[RTSP] 回调执行出错: {e}")
    
    def connect(self) -> bool:
        """
        连接 RTSP 流
        
        Returns:
            是否连接成功
        """
        import os
        
        try:
            print(f"[RTSP] 正在连接: {self.rtsp_url}")
            
            # 释放旧的连接
            if self._cap is not None:
                self._cap.release()
            
            # 设置 FFMPEG 选项增加超时和使用 TCP
            # 格式: rtsp_url?tcp 或通过环境变量
            os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp|stimeout;10000000'
            
            # 创建新的 VideoCapture，使用 CAP_FFMPEG 后端
            self._cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            
            # 设置超时和缓冲
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self._cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)  # 10秒打开超时
            self._cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)   # 5秒读取超时
            
            # 尝试读取一帧检查连接
            ret, frame = self._cap.read()
            
            if ret and frame is not None:
                with self._frame_lock:
                    self._latest_frame = frame
                
                self._notify_status(True, "连接成功")
                print(f"[RTSP] 连接成功，画面尺寸: {frame.shape[1]}x{frame.shape[0]}")
                return True
            else:
                self._notify_status(False, "无法读取画面")
                print("[RTSP] 连接失败：无法读取画面")
                return False
                
        except Exception as e:
            self._notify_status(False, f"连接异常: {e}")
            print(f"[RTSP] 连接异常: {e}")
            return False
    
    def start_background_capture(self):
        """
        启动后台捕获线程
        
        后台线程会持续拉取视频流，保持 _latest_frame 更新
        """
        if self._running:
            return
        
        self._running = True
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()
        print("[RTSP] 后台捕获线程已启动")
    
    def stop_background_capture(self):
        """停止后台捕获线程"""
        self._running = False
        if self._capture_thread:
            self._capture_thread.join(timeout=2)
        print("[RTSP] 后台捕获线程已停止")
    
    def _capture_loop(self):
        """后台捕获循环"""
        while self._running:
            try:
                if self._cap is None or not self._cap.isOpened():
                    # 尝试重连
                    self._notify_status(False, "连接断开，正在重连...")
                    if self.connect():
                        continue
                    else:
                        time.sleep(self.reconnect_interval)
                        continue
                
                # 读取一帧
                ret, frame = self._cap.read()
                
                if ret and frame is not None:
                    with self._frame_lock:
                        self._latest_frame = frame
                    
                    if not self._connected:
                        self._notify_status(True, "连接恢复")
                else:
                    # 读取失败，可能断流
                    self._notify_status(False, "读取失败")
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"[RTSP] 捕获循环异常: {e}")
                time.sleep(1)
        
        # 清理
        if self._cap:
            self._cap.release()
    
    def capture(self, force_fresh: bool = True) -> Optional[np.ndarray]:
        """
        抓取当前画面
        
        Args:
            force_fresh: 是否强制获取最新帧（丢弃缓冲区中的旧帧）
        
        Returns:
            画面帧（numpy 数组），如果失败返回 None
        """
        if force_fresh and self._cap and self._cap.isOpened():
            # 使用 grab() 快速丢弃缓冲区中的旧帧
            # grab() 比 read() 快很多，只获取帧但不解码
            for _ in range(10):
                self._cap.grab()
            
            # 读取最新帧
            ret, frame = self._cap.read()
            
            if ret and frame is not None:
                with self._frame_lock:
                    self._latest_frame = frame
                print(f"[RTSP] 获取到最新帧")
                return frame.copy()
        
        # 如果强制刷新失败，使用缓存帧
        with self._frame_lock:
            if self._latest_frame is not None:
                print(f"[RTSP] 使用缓存帧")
                return self._latest_frame.copy()
        
        # 最后尝试直接读取
        if self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if ret and frame is not None:
                with self._frame_lock:
                    self._latest_frame = frame
                return frame.copy()
        
        return None
    
    def capture_and_save(self, 
                         output_dir: str, 
                         filename_prefix: str = "capture") -> Optional[str]:
        """
        抓取画面并保存到文件
        
        Args:
            output_dir: 输出目录
            filename_prefix: 文件名前缀
            
        Returns:
            保存的文件路径，如果失败返回 None
        """
        # 强制获取最新帧
        frame = self.capture(force_fresh=True)
        
        if frame is None:
            print("[RTSP] 抓取失败：无法获取画面")
            return None
        
        try:
            # 确保目录存在
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{filename_prefix}_{timestamp}.jpg"
            filepath = Path(output_dir) / filename
            
            # 保存图片
            cv2.imwrite(str(filepath), frame)
            
            print(f"[RTSP] 抓拍保存: {filepath}")
            return str(filepath)
            
        except Exception as e:
            print(f"[RTSP] 保存图片失败: {e}")
            return None
    
    def is_connected(self) -> bool:
        """
        检查是否已连接
        
        Returns:
            是否已连接
        """
        return self._connected and self._cap is not None and self._cap.isOpened()
    
    def release(self):
        """释放资源"""
        self._running = False
        
        if self._capture_thread:
            self._capture_thread.join(timeout=2)
        
        if self._cap:
            self._cap.release()
            self._cap = None
        
        self._notify_status(False, "已断开连接")
        print("[RTSP] 资源已释放")
    
    def get_frame_info(self) -> dict:
        """
        获取当前帧信息
        
        Returns:
            包含宽、高、通道数的字典
        """
        with self._frame_lock:
            if self._latest_frame is not None:
                h, w, c = self._latest_frame.shape
                return {'width': w, 'height': h, 'channels': c}
        
        return {'width': 0, 'height': 0, 'channels': 0}
    
    def update_url(self, new_url: str):
        """
        更新 RTSP URL
        
        Args:
            new_url: 新的 RTSP 地址
        """
        self.rtsp_url = new_url
        
        # 如果正在运行，重新连接
        if self._running:
            if self._cap:
                self._cap.release()
            self.connect()


class MockRTSPCapture(RTSPCapture):
    """
    模拟 RTSP 捕获器（用于测试）
    
    生成随机彩色图像代替真实视频流
    """
    
    def __init__(self, rtsp_url: str = "", reconnect_interval: int = 5):
        super().__init__(rtsp_url, reconnect_interval)
        self._connected = True
    
    def connect(self) -> bool:
        """模拟连接成功"""
        print(f"[模拟RTSP] 连接: {self.rtsp_url}")
        self._connected = True
        self._notify_status(True, "[模拟] 连接成功")
        return True
    
    def capture(self) -> Optional[np.ndarray]:
        """生成模拟画面"""
        # 生成 640x480 的随机图像
        frame = np.random.randint(100, 200, (480, 640, 3), dtype=np.uint8)
        
        # 添加一些图案让它看起来不那么随机
        cv2.rectangle(frame, (50, 50), (590, 430), (200, 200, 200), 2)
        cv2.putText(frame, "MOCK CAMERA", (180, 250), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(frame, datetime.now().strftime("%H:%M:%S"), (250, 300),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1)
        
        return frame
    
    def is_connected(self) -> bool:
        return True
    
    def release(self):
        print("[模拟RTSP] 释放资源")
        self._connected = False


def get_rtsp_capture(rtsp_url: str) -> RTSPCapture:
    """
    获取 RTSP 捕获器
    
    Args:
        rtsp_url: RTSP 流地址
        
    Returns:
        如果 URL 有效返回真实捕获器，否则返回模拟捕获器
    """
    if rtsp_url and rtsp_url.startswith('rtsp://'):
        return RTSPCapture(rtsp_url)
    else:
        print("[RTSP] URL 无效，使用模拟捕获器")
        return MockRTSPCapture(rtsp_url)


if __name__ == '__main__':
    # 测试代码
    print("[RTSP] 模块加载成功")
    
    # 使用模拟捕获器测试
    capture = get_rtsp_capture("")
    capture.connect()
    
    frame = capture.capture()
    if frame is not None:
        print(f"[RTSP] 捕获成功: {frame.shape}")
    
    capture.release()
