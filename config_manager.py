# -*- coding: utf-8 -*-
"""
配置管理模块
负责读取、保存和管理 YAML 配置文件
"""

import os
import yaml
from typing import Any, Dict, Optional
from pathlib import Path
import threading


class ConfigManager:
    """
    YAML 配置文件管理器
    
    功能：
    - 加载和保存 YAML 配置
    - 支持单项配置的获取和设置
    - 线程安全的配置访问
    - 自动创建默认配置
    """
    
    # 默认配置模板
    DEFAULT_CONFIG = {
        'rtsp_url': 'rtsp://username:password@ip_address:554/stream',
        'siliconflow_token': '',
        'scoring_model': 'THUDM/GLM-4.1V-9B-Thinking',
        'cartoon_model': 'Qwen/Qwen-Image-Edit-2509',
        'pushplus_token': '',
        'imgbb_api_key': '',
        'capture_interval': 30,
        'push_times': ['12:00', '18:00', '21:00'],
        'top_n': 3,
        'quality_threshold': 0.5,
        'enable_face_detection': False,
        'auto_capture_enabled': True,
        'auto_push_enabled': True,
        'cartoon_prompt': "现代清新插画风格，矢量艺术，扁平化设计，明亮的色块，简约时尚，色彩鲜艳，充满活力，保留图片中人物和背景的主要特征",
        'scoring_prompt': """作为一名专业摄影评审，请对这张照片进行审美评分。

评判标准：
1. 构图美感 (20分)
2. 光线运用 (20分)
3. 色彩搭配 (20分)
4. 人物表情/姿态 (20分)
5. 整体氛围 (20分)

请只回复一个0到1之间的小数作为最终评分，例如：0.75
不要加任何其他文字。""",
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为同目录下的 config.yaml
        """
        if config_path is None:
            # Check for environment variable first
            config_path = os.getenv('CONFIG_PATH')
            
            if not config_path:
                # 获取当前模块所在目录
                current_dir = Path(__file__).parent
                config_path = current_dir / 'config.yaml'
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._lock = threading.RLock()  # 可重入锁，保证线程安全
        
        # 加载配置
        self.load()
    
    def load(self) -> Dict[str, Any]:
        """
        从 YAML 文件加载配置
        
        如果配置文件不存在，则创建默认配置
        
        Returns:
            配置字典
        """
        with self._lock:
            if not self.config_path.exists():
                # 配置文件不存在，创建默认配置
                self._config = self.DEFAULT_CONFIG.copy()
                self.save(self._config)
                return self._config
            
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_config = yaml.safe_load(f) or {}
                
                # 合并默认配置（确保所有必需的键都存在）
                self._config = {**self.DEFAULT_CONFIG, **loaded_config}
                return self._config
                
            except yaml.YAMLError as e:
                print(f"[配置管理] YAML 解析错误: {e}")
                self._config = self.DEFAULT_CONFIG.copy()
                return self._config
            except Exception as e:
                print(f"[配置管理] 加载配置失败: {e}")
                self._config = self.DEFAULT_CONFIG.copy()
                return self._config
    
    def save(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        保存配置到 YAML 文件
        
        Args:
            config: 要保存的配置字典，如果为 None 则保存当前配置
            
        Returns:
            是否保存成功
        """
        with self._lock:
            if config is not None:
                self._config = config
            
            try:
                # 确保目录存在
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(
                        self._config, 
                        f, 
                        default_flow_style=False, 
                        allow_unicode=True,
                        sort_keys=False
                    )
                return True
                
            except Exception as e:
                print(f"[配置管理] 保存配置失败: {e}")
                return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取单项配置值
        
        Args:
            key: 配置项的键名
            default: 默认值，当键不存在时返回
            
        Returns:
            配置值
        """
        with self._lock:
            return self._config.get(key, default)
    
    def set(self, key: str, value: Any, auto_save: bool = True) -> bool:
        """
        设置单项配置值
        
        Args:
            key: 配置项的键名
            value: 配置值
            auto_save: 是否自动保存到文件
            
        Returns:
            是否设置成功
        """
        with self._lock:
            self._config[key] = value
            
            if auto_save:
                return self.save()
            return True
    
    def get_all(self) -> Dict[str, Any]:
        """
        获取所有配置
        
        Returns:
            配置字典的副本
        """
        with self._lock:
            return self._config.copy()
    
    def update(self, updates: Dict[str, Any], auto_save: bool = True) -> bool:
        """
        批量更新配置
        
        Args:
            updates: 要更新的配置字典
            auto_save: 是否自动保存到文件
            
        Returns:
            是否更新成功
        """
        with self._lock:
            self._config.update(updates)
            
            if auto_save:
                return self.save()
            return True
    
    def reset_to_default(self, auto_save: bool = True) -> bool:
        """
        重置为默认配置
        
        Args:
            auto_save: 是否自动保存到文件
            
        Returns:
            是否重置成功
        """
        with self._lock:
            self._config = self.DEFAULT_CONFIG.copy()
            
            if auto_save:
                return self.save()
            return True
    
    def validate(self) -> tuple[bool, list[str]]:
        """
        验证配置有效性
        
        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []
        
        with self._lock:
            # 验证 RTSP URL
            rtsp_url = self._config.get('rtsp_url', '')
            if not rtsp_url or not rtsp_url.startswith('rtsp://'):
                errors.append("RTSP 地址无效，必须以 rtsp:// 开头")
            
            # 验证 SiliconFlow Token
            if not self._config.get('siliconflow_token'):
                errors.append("SiliconFlow Token 未配置")
            
            # 验证 PushPlus Token
            if not self._config.get('pushplus_token'):
                errors.append("PushPlus Token 未配置")
            
            # 验证抓拍间隔
            interval = self._config.get('capture_interval', 0)
            if not isinstance(interval, (int, float)) or interval < 5:
                errors.append("抓拍间隔必须为数字且不小于 5 秒")
            
            # 验证 Top N
            top_n = self._config.get('top_n', 0)
            if not isinstance(top_n, int) or top_n < 1 or top_n > 5:
                errors.append("Top N 必须为 1-5 之间的整数")
            
            # 验证质量阈值
            threshold = self._config.get('quality_threshold', 0)
            if not isinstance(threshold, (int, float)) or threshold < 0 or threshold > 1:
                errors.append("质量阈值必须为 0-1 之间的数字")
        
        return (len(errors) == 0, errors)


# 全局配置管理器实例（单例模式）
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """
    获取全局配置管理器实例
    
    Returns:
        ConfigManager 实例
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


if __name__ == '__main__':
    # 测试代码
    cm = get_config_manager()
    print("当前配置:", cm.get_all())
    
    is_valid, errors = cm.validate()
    if not is_valid:
        print("配置验证失败:")
        for err in errors:
            print(f"  - {err}")
    else:
        print("配置验证通过")
