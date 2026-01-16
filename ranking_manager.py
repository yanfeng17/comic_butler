# -*- coding: utf-8 -*-
"""
Top N 排名管理模块
负责维护每日得分最高的 N 张照片
"""

import os
import json
import shutil
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import threading


@dataclass
class RankedImage:
    """排名图片数据结构"""
    image_path: str           # 图片路径
    score: float              # 审美评分
    timestamp: str            # 拍摄时间 (HH:MM)
    capture_time: str         # 完整拍摄时间戳
    cartoon_path: str = ""    # 漫画重绘后的路径
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RankedImage':
        """从字典创建"""
        return cls(**data)


class RankingManager:
    """
    Top N 排名管理器
    
    功能：
    - 维护当天得分最高的 N 张照片
    - 自动清理被淘汰的低分照片
    - 持久化存储排名数据
    - 按日期归档历史数据
    """
    
    def __init__(self, data_dir: str, top_n: int = 3):
        """
        初始化排名管理器
        
        Args:
            data_dir: 数据目录路径
            top_n: 保留的最高分照片数量
        """
        self.data_dir = Path(data_dir)
        self.top_n = top_n
        self._rankings: List[RankedImage] = []
        self._current_date: str = ""
        self._lock = threading.RLock()
        
        # 确保目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "captures").mkdir(exist_ok=True)
        (self.data_dir / "cartoons").mkdir(exist_ok=True)
        (self.data_dir / "collages").mkdir(exist_ok=True)
        (self.data_dir / "archive").mkdir(exist_ok=True)
        
        # 加载今日数据
        self._load_today()
    
    def _get_ranking_file_path(self, date_str: str) -> Path:
        """获取排名数据文件路径"""
        return self.data_dir / f"ranking_{date_str}.json"
    
    def _load_today(self):
        """加载今日排名数据"""
        today = date.today().isoformat()
        
        with self._lock:
            # 如果日期变化，先归档昨日数据
            if self._current_date and self._current_date != today:
                self._archive_old_data(self._current_date)
            
            self._current_date = today
            ranking_file = self._get_ranking_file_path(today)
            
            if ranking_file.exists():
                try:
                    with open(ranking_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self._rankings = [RankedImage.from_dict(item) for item in data]
                except Exception as e:
                    print(f"[排名管理] 加载排名数据失败: {e}")
                    self._rankings = []
            else:
                self._rankings = []
    
    def _save_rankings(self):
        """保存排名数据到文件"""
        ranking_file = self._get_ranking_file_path(self._current_date)
        
        try:
            with open(ranking_file, 'w', encoding='utf-8') as f:
                json.dump([item.to_dict() for item in self._rankings], 
                         f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[排名管理] 保存排名数据失败: {e}")
    
    def _archive_old_data(self, old_date: str):
        """归档旧日期的数据"""
        try:
            archive_dir = self.data_dir / "archive" / old_date
            archive_dir.mkdir(parents=True, exist_ok=True)
            
            # 移动排名文件
            old_ranking_file = self._get_ranking_file_path(old_date)
            if old_ranking_file.exists():
                shutil.move(str(old_ranking_file), 
                           str(archive_dir / old_ranking_file.name))
            
            print(f"[排名管理] 已归档 {old_date} 的数据")
            
        except Exception as e:
            print(f"[排名管理] 归档失败: {e}")
    
    def add_image(self, 
                  image_path: str, 
                  score: float,
                  timestamp: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        添加图片到排名池
        
        如果图片分数足够高则加入排名，可能淘汰低分图片
        
        Args:
            image_path: 图片路径
            score: 图片审美分数
            timestamp: 时间戳 (HH:MM)，如果为 None 则使用当前时间
            
        Returns:
            (是否入选, 被淘汰的图片路径或 None)
        """
        # 确保日期正确
        today = date.today().isoformat()
        if self._current_date != today:
            self._load_today()
        
        if timestamp is None:
            timestamp = datetime.now().strftime("%H:%M")
        
        capture_time = datetime.now().isoformat()
        
        with self._lock:
            # 创建新的排名项
            new_item = RankedImage(
                image_path=image_path,
                score=score,
                timestamp=timestamp,
                capture_time=capture_time
            )
            
            # 如果还没满，直接加入
            if len(self._rankings) < self.top_n:
                self._rankings.append(new_item)
                self._rankings.sort(key=lambda x: x.score, reverse=True)
                self._save_rankings()
                print(f"[排名管理] 图片入选 Top {self.top_n}，分数: {score:.3f}")
                return (True, None)
            
            # 检查是否能挤掉最低分的图片
            lowest = self._rankings[-1]
            if score > lowest.score:
                # 淘汰最低分图片
                removed_path = lowest.image_path
                self._rankings.remove(lowest)
                
                # 添加新图片
                self._rankings.append(new_item)
                self._rankings.sort(key=lambda x: x.score, reverse=True)
                self._save_rankings()
                
                # 删除被淘汰的图片文件
                self._cleanup_image(lowest)
                
                print(f"[排名管理] 图片入选，淘汰旧图片 (旧分数: {lowest.score:.3f}, 新分数: {score:.3f})")
                return (True, removed_path)
            
            print(f"[排名管理] 图片未入选，分数 {score:.3f} 低于最低分 {lowest.score:.3f}")
            
            # 不再自动删除未入选的图片，保留给预览功能使用
            # 预览图片会在用户关闭预览时或后续抓拍时清理
            
            return (False, None)
    
    def _cleanup_image(self, item: RankedImage):
        """清理被淘汰的图片文件"""
        try:
            if item.image_path and os.path.exists(item.image_path):
                os.remove(item.image_path)
                print(f"[排名管理] 已删除图片: {item.image_path}")
        except Exception as e:
            print(f"[排名管理] 删除图片失败: {e}")
        
        try:
            if item.cartoon_path and os.path.exists(item.cartoon_path):
                os.remove(item.cartoon_path)
                print(f"[排名管理] 已删除漫画: {item.cartoon_path}")
        except Exception as e:
            print(f"[排名管理] 删除漫画失败: {e}")
    
    def get_rankings(self) -> List[RankedImage]:
        """
        获取当前排名列表
        
        Returns:
            按分数降序排列的图片列表
        """
        today = date.today().isoformat()
        if self._current_date != today:
            self._load_today()
        
        with self._lock:
            return self._rankings.copy()
    
    def update_cartoon_path(self, image_path: str, cartoon_path: str) -> bool:
        """
        更新图片对应的漫画重绘路径
        
        Args:
            image_path: 原始图片路径
            cartoon_path: 漫画重绘后的路径
            
        Returns:
            是否更新成功
        """
        with self._lock:
            for item in self._rankings:
                if item.image_path == image_path:
                    item.cartoon_path = cartoon_path
                    self._save_rankings()
                    return True
            return False
    
    def get_cartoon_paths(self) -> List[Tuple[str, str]]:
        """
        获取所有漫画图片路径和时间戳
        
        Returns:
            [(漫画路径, 时间戳), ...] 按拍摄时间排序
        """
        with self._lock:
            # 按拍摄时间排序
            sorted_items = sorted(self._rankings, key=lambda x: x.capture_time)
            return [(item.cartoon_path or item.image_path, item.timestamp) 
                    for item in sorted_items if item.cartoon_path or item.image_path]
    
    def remove_image(self, image_path: str) -> bool:
        """
        删除指定的排名照片
        
        Args:
            image_path: 要删除的图片路径
            
        Returns:
            是否删除成功
        """
        with self._lock:
            for item in self._rankings:
                if item.image_path == image_path:
                    self._rankings.remove(item)
                    self._cleanup_image(item)
                    self._save_rankings()
                    print(f"[排名管理] 已删除照片: {image_path}")
                    return True
            return False
    
    def clear_today(self):
        """清空今日排名数据"""
        with self._lock:
            # 删除所有图片文件
            for item in self._rankings:
                self._cleanup_image(item)
            
            self._rankings = []
            self._save_rankings()
            print("[排名管理] 已清空今日数据")
    
    def set_top_n(self, top_n: int):
        """
        设置 Top N 数量
        
        如果减少数量，会淘汰多余的低分图片
        
        Args:
            top_n: 新的 Top N 数量
        """
        if top_n < 1 or top_n > 10:
            return
        
        with self._lock:
            self.top_n = top_n
            
            # 淘汰多余的图片
            while len(self._rankings) > self.top_n:
                lowest = self._rankings.pop()
                self._cleanup_image(lowest)
            
            self._save_rankings()
    
    def get_history_dates(self) -> List[str]:
        """
        获取有历史数据的日期列表
        
        Returns:
            日期字符串列表，格式 YYYY-MM-DD
        """
        archive_dir = self.data_dir / "archive"
        if not archive_dir.exists():
            return []
        
        return sorted([d.name for d in archive_dir.iterdir() if d.is_dir()], 
                     reverse=True)
    
    def get_history_rankings(self, date_str: str) -> List[RankedImage]:
        """
        获取历史日期的排名数据
        
        Args:
            date_str: 日期字符串 YYYY-MM-DD
            
        Returns:
            排名列表
        """
        archive_file = self.data_dir / "archive" / date_str / f"ranking_{date_str}.json"
        
        if not archive_file.exists():
            return []
        
        try:
            with open(archive_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [RankedImage.from_dict(item) for item in data]
        except Exception as e:
            print(f"[排名管理] 读取历史数据失败: {e}")
            return []


if __name__ == '__main__':
    # 测试代码
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = RankingManager(tmpdir, top_n=3)
        print(f"[排名管理] 当前排名: {manager.get_rankings()}")
        print("[排名管理] 模块加载成功")
