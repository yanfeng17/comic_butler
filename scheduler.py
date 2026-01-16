# -*- coding: utf-8 -*-
"""
任务调度模块
负责定时抓拍和定时推送
"""

import asyncio
import threading
from datetime import datetime
from typing import Optional, Callable, List, Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger


class TaskScheduler:
    """
    任务调度器
    
    功能：
    - 定时抓拍任务
    - 定时推送任务
    - 动态修改任务参数
    """
    
    JOB_ID_CAPTURE = "capture_job"
    JOB_ID_PUSH_PREFIX = "push_job_"
    
    def __init__(self):
        """初始化调度器"""
        self._scheduler = BackgroundScheduler()
        self._capture_callback: Optional[Callable] = None
        self._push_callback: Optional[Callable] = None
        self._running = False
        
        # 任务状态
        self._next_capture_time: Optional[datetime] = None
        self._next_push_times: List[str] = []
    
    def set_capture_callback(self, callback: Callable):
        """
        设置抓拍任务回调
        
        Args:
            callback: 抓拍任务函数
        """
        self._capture_callback = callback
    
    def set_push_callback(self, callback: Callable):
        """
        设置推送任务回调
        
        Args:
            callback: 推送任务函数
        """
        self._push_callback = callback
    
    def start(self):
        """启动调度器"""
        if not self._running:
            self._scheduler.start()
            self._running = True
            print("[调度器] 已启动")
    
    def stop(self):
        """停止调度器"""
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            print("[调度器] 已停止")
    
    def schedule_capture(self, interval_seconds: int):
        """
        配置定时抓拍任务
        
        Args:
            interval_seconds: 抓拍间隔（秒）
        """
        if not self._capture_callback:
            print("[调度器] 错误：未设置抓拍回调函数")
            return
        
        # 移除旧任务
        if self._scheduler.get_job(self.JOB_ID_CAPTURE):
            self._scheduler.remove_job(self.JOB_ID_CAPTURE)
        
        # 添加新任务
        self._scheduler.add_job(
            self._capture_callback,
            IntervalTrigger(seconds=interval_seconds),
            id=self.JOB_ID_CAPTURE,
            name="定时抓拍",
            replace_existing=True
        )
        
        print(f"[调度器] 抓拍任务已配置：每 {interval_seconds} 秒执行一次")
    
    def schedule_push(self, push_times: List[str]):
        """
        配置定时推送任务
        
        Args:
            push_times: 推送时间列表，格式 ["12:00", "18:00", "21:00"]
        """
        if not self._push_callback:
            print("[调度器] 错误：未设置推送回调函数")
            return
        
        # 移除旧的推送任务
        for job in self._scheduler.get_jobs():
            if job.id.startswith(self.JOB_ID_PUSH_PREFIX):
                self._scheduler.remove_job(job.id)
        
        self._next_push_times = push_times.copy()
        
        # 添加新任务
        for i, time_str in enumerate(push_times):
            try:
                hour, minute = map(int, time_str.split(':'))
                
                job_id = f"{self.JOB_ID_PUSH_PREFIX}{i}"
                self._scheduler.add_job(
                    self._push_callback,
                    CronTrigger(hour=hour, minute=minute),
                    id=job_id,
                    name=f"定时推送 {time_str}",
                    replace_existing=True
                )
                
                print(f"[调度器] 推送任务已配置：每日 {time_str}")
                
            except ValueError:
                print(f"[调度器] 无效的时间格式: {time_str}")
    
    def update_capture_interval(self, interval_seconds: int):
        """
        更新抓拍间隔
        
        Args:
            interval_seconds: 新的抓拍间隔（秒）
        """
        self.schedule_capture(interval_seconds)
    
    def update_push_times(self, push_times: List[str]):
        """
        更新推送时间
        
        Args:
            push_times: 新的推送时间列表
        """
        self.schedule_push(push_times)
    
    def pause_capture(self):
        """暂停抓拍任务"""
        job = self._scheduler.get_job(self.JOB_ID_CAPTURE)
        if job:
            job.pause()
            print("[调度器] 抓拍任务已暂停")
    
    def resume_capture(self):
        """恢复抓拍任务"""
        job = self._scheduler.get_job(self.JOB_ID_CAPTURE)
        if job:
            job.resume()
            print("[调度器] 抓拍任务已恢复")
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取调度器状态
        
        Returns:
            状态信息字典
        """
        jobs = []
        for job in self._scheduler.get_jobs():
            job_info = {
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'paused': job.next_run_time is None
            }
            jobs.append(job_info)
        
        return {
            'running': self._running,
            'jobs': jobs
        }
    
    def get_next_capture_time(self) -> Optional[datetime]:
        """获取下次抓拍时间"""
        job = self._scheduler.get_job(self.JOB_ID_CAPTURE)
        if job:
            return job.next_run_time
        return None
    
    def get_next_push_time(self) -> Optional[datetime]:
        """获取最近的下次推送时间"""
        next_time = None
        for job in self._scheduler.get_jobs():
            if job.id.startswith(self.JOB_ID_PUSH_PREFIX) and job.next_run_time:
                if next_time is None or job.next_run_time < next_time:
                    next_time = job.next_run_time
        return next_time


# 全局调度器实例
_scheduler: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    """
    获取全局调度器实例
    
    Returns:
        TaskScheduler 实例
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler


if __name__ == '__main__':
    # 测试代码
    import time
    
    def test_capture():
        print(f"[测试] 执行抓拍任务 - {datetime.now()}")
    
    def test_push():
        print(f"[测试] 执行推送任务 - {datetime.now()}")
    
    scheduler = get_scheduler()
    scheduler.set_capture_callback(test_capture)
    scheduler.set_push_callback(test_push)
    
    scheduler.start()
    scheduler.schedule_capture(5)  # 每5秒抓拍一次
    
    print("调度器状态:", scheduler.get_status())
    
    try:
        time.sleep(15)
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.stop()
