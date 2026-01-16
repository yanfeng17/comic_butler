# -*- coding: utf-8 -*-
"""
ModelScope AI 视觉服务客户端
负责人物分类、审美打分和漫画重绘
"""

import os
import io
import asyncio
import aiohttp
import base64
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from PIL import Image
import requests


class VisionClient:
    """
    ModelScope AI 视觉服务客户端
    
    集成以下模型：
    - 人体检测: damo/cv_tinynas_human-detection_damoyolo
    - 审美打分: damo/cv_resnet50_image-quality-assessment_mos
    - 漫画重绘: damo/cv_unet_person-image-cartoon-comic_compound-models (DCT-Net 漫画风)
    """
    
    # ModelScope API 基础地址
    API_BASE = "https://api-inference.modelscope.cn/api-inference/v1/models"
    
    # 模型配置 - 使用最新可用的模型
    MODELS = {
        'detection': 'damo/cv_tinynas_human-detection_damoyolo',
        'quality': 'damo/cv_resnet50_image-quality-assessment_mos',
        # DCT-Net 人像卡通化模型 - 漫画风格
        'cartoon': 'damo/cv_unet_person-image-cartoon-comic_compound-models',
    }
    
    # 人物相关的类别标签
    PERSON_LABELS = ['person', 'people', 'human', 'man', 'woman', 'child', 'boy', 'girl']
    
    def __init__(self, token: str, max_retries: int = 3):
        """
        初始化客户端
        
        Args:
            token: ModelScope API Token
            max_retries: 最大重试次数
        """
        self.token = token
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
        }
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 aiohttp 会话"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=120)  # 2分钟超时
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """关闭会话"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _image_to_base64(self, image_path: str, max_size_kb: int = 1024) -> str:
        """
        将图片转换为 Base64，并进行压缩
        
        Args:
            image_path: 图片路径
            max_size_kb: 最大文件大小（KB）
            
        Returns:
            Base64 编码的图片数据
        """
        img = Image.open(image_path)
        
        # 转换为 RGB 模式
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 压缩图片
        quality = 95
        while quality > 20:
            buffer = io.BytesIO()
            img.save(buffer, 'JPEG', quality=quality)
            size_kb = buffer.tell() / 1024
            
            if size_kb <= max_size_kb:
                buffer.seek(0)
                return base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            quality -= 10
        
        # 如果还是太大，缩小尺寸
        scale = 0.8
        while scale > 0.2:
            new_size = (int(img.width * scale), int(img.height * scale))
            resized = img.resize(new_size, Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            resized.save(buffer, 'JPEG', quality=70)
            size_kb = buffer.tell() / 1024
            
            if size_kb <= max_size_kb:
                buffer.seek(0)
                return base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            scale -= 0.1
        
        # 返回最终结果
        buffer.seek(0)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    async def _call_api(self, model_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用 ModelScope API
        
        Args:
            model_key: 模型键名
            payload: 请求载荷
            
        Returns:
            API 响应
        """
        model_name = self.MODELS[model_key]
        url = f"{self.API_BASE}/{model_name}"
        
        session = await self._get_session()
        
        for attempt in range(self.max_retries):
            try:
                async with session.post(url, json=payload, headers=self._get_headers()) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    
                    error_text = await resp.text()
                    print(f"[AI服务] API 错误 (尝试 {attempt + 1}/{self.max_retries}): {resp.status} - {error_text}")
                    
                    # 如果是 429 (限流) 或 5xx 错误，等待后重试
                    if resp.status == 429 or resp.status >= 500:
                        await asyncio.sleep(2 ** attempt)  # 指数退避
                        continue
                    
                    # 其他错误直接返回
                    return {'error': error_text, 'status': resp.status}
                    
            except asyncio.TimeoutError:
                print(f"[AI服务] 请求超时 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    
            except Exception as e:
                print(f"[AI服务] 请求失败 (尝试 {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
        
        return {'error': 'Max retries exceeded', 'status': -1}
    
    async def classify_image(self, image_path: str) -> Tuple[bool, str, float]:
        """
        检测图片中是否有人物
        
        Args:
            image_path: 图片路径
            
        Returns:
            (是否有人物, 检测到的类别, 置信度)
        """
        try:
            img_base64 = self._image_to_base64(image_path, max_size_kb=512)
            
            payload = {
                'input': {
                    'image': f'data:image/jpeg;base64,{img_base64}'
                }
            }
            
            result = await self._call_api('detection', payload)
            
            if 'error' in result:
                print(f"[AI服务] 人体检测失败: {result['error']}")
                return (False, 'error', 0.0)
            
            # 解析人体检测结果
            # damoyolo 返回格式: {'output': {'scores': [...], 'boxes': [...], 'labels': [...]}}
            output = result.get('output', result.get('Data', {}))
            
            if isinstance(output, dict):
                scores = output.get('scores', [])
                boxes = output.get('boxes', [])
                labels = output.get('labels', [])
                
                # 如果检测到任何人体框，则认为有人
                if scores and len(scores) > 0:
                    max_score = max(scores) if isinstance(scores, list) else float(scores)
                    return (True, 'person', float(max_score))
                
                # 也可能是其他返回格式
                if 'label' in output or 'class' in output:
                    label = output.get('label', output.get('class', 'unknown'))
                    score = output.get('score', output.get('confidence', 0.5))
                    if 'person' in str(label).lower() or 'human' in str(label).lower():
                        return (True, str(label), float(score))
            
            # 检测到0个人体
            return (False, 'no_person', 0.0)
            
        except Exception as e:
            print(f"[AI服务] 人体检测异常: {e}")
            return (False, 'error', 0.0)
    
    async def score_image(self, image_path: str) -> float:
        """
        评估图片的审美质量分数
        
        Args:
            image_path: 图片路径
            
        Returns:
            质量分数 (0-1)
        """
        try:
            img_base64 = self._image_to_base64(image_path, max_size_kb=512)
            
            payload = {
                'input': {
                    'image': f'data:image/jpeg;base64,{img_base64}'
                }
            }
            
            result = await self._call_api('quality', payload)
            
            if 'error' in result:
                print(f"[AI服务] 打分失败: {result['error']}")
                return 0.0
            
            # 解析结果
            output = result.get('output', result.get('Data', {}))
            
            if isinstance(output, dict):
                # 尝试不同的键名
                score = output.get('score', output.get('mos', output.get('quality', 0)))
                
                # 确保分数在 0-1 范围内
                if isinstance(score, (int, float)):
                    # 如果分数大于1，可能是 0-100 或 0-5 的评分系统
                    if score > 1:
                        if score > 5:
                            score = score / 100  # 假设是百分制
                        else:
                            score = score / 5  # 假设是5分制
                    return float(max(0, min(1, score)))
            
            elif isinstance(output, (int, float)):
                score = output
                if score > 1:
                    if score > 5:
                        score = score / 100
                    else:
                        score = score / 5
                return float(max(0, min(1, score)))
            
            return 0.0
            
        except Exception as e:
            print(f"[AI服务] 打分异常: {e}")
            return 0.0
    
    async def cartoon_image(self, image_path: str, output_path: str) -> bool:
        """
        将人物照片转换为漫画风格
        
        Args:
            image_path: 输入图片路径
            output_path: 输出图片路径
            
        Returns:
            是否转换成功
        """
        try:
            img_base64 = self._image_to_base64(image_path, max_size_kb=1024)
            
            payload = {
                'input': {
                    'image': f'data:image/jpeg;base64,{img_base64}'
                }
            }
            
            result = await self._call_api('cartoon', payload)
            
            if 'error' in result:
                print(f"[AI服务] 漫画重绘失败: {result['error']}")
                return False
            
            # 解析结果
            output = result.get('output', result.get('Data', {}))
            
            # 获取输出图片
            output_image = None
            
            if isinstance(output, dict):
                # 尝试获取图片数据
                output_image = output.get('output_img', output.get('image', output.get('result')))
            elif isinstance(output, str):
                output_image = output
            
            if output_image:
                # 处理 Base64 图片数据
                if isinstance(output_image, str):
                    # 移除可能的 data URI 前缀
                    if 'base64,' in output_image:
                        output_image = output_image.split('base64,')[1]
                    
                    # 解码并保存图片
                    img_data = base64.b64decode(output_image)
                    
                    # 确保输出目录存在
                    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(output_path, 'wb') as f:
                        f.write(img_data)
                    
                    print(f"[AI服务] 漫画重绘成功: {output_path}")
                    return True
            
            print("[AI服务] 漫画重绘返回结果格式异常")
            return False
            
        except Exception as e:
            print(f"[AI服务] 漫画重绘异常: {e}")
            return False
    
    # ========== 同步版本的方法（供非异步环境使用）==========
    
    def classify_image_sync(self, image_path: str) -> Tuple[bool, str, float]:
        """分类图片（同步版本）"""
        return asyncio.run(self.classify_image(image_path))
    
    def score_image_sync(self, image_path: str) -> float:
        """图片打分（同步版本）"""
        return asyncio.run(self.score_image(image_path))
    
    def cartoon_image_sync(self, image_path: str, output_path: str) -> bool:
        """漫画重绘（同步版本）"""
        return asyncio.run(self.cartoon_image(image_path, output_path))


class MockVisionClient(VisionClient):
    """
    模拟 AI 视觉客户端（用于测试）
    
    当 ModelScope Token 未配置时使用此类
    """
    
    def __init__(self, token: str = "", max_retries: int = 3):
        super().__init__(token, max_retries)
    
    async def classify_image(self, image_path: str) -> Tuple[bool, str, float]:
        """模拟分类：始终返回有人"""
        print(f"[模拟AI] 分类图片: {image_path}")
        await asyncio.sleep(0.5)  # 模拟延迟
        return (True, 'person', 0.95)
    
    async def score_image(self, image_path: str) -> float:
        """模拟打分：返回随机分数"""
        import random
        print(f"[模拟AI] 打分图片: {image_path}")
        await asyncio.sleep(0.5)
        return round(random.uniform(0.4, 0.95), 3)
    
    async def cartoon_image(self, image_path: str, output_path: str) -> bool:
        """模拟重绘：复制原图"""
        import shutil
        print(f"[模拟AI] 重绘图片: {image_path} -> {output_path}")
        await asyncio.sleep(1)
        
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(image_path, output_path)
            return True
        except Exception as e:
            print(f"[模拟AI] 复制失败: {e}")
            return False


def get_vision_client(token: str) -> VisionClient:
    """
    获取 AI 视觉客户端
    
    Args:
        token: ModelScope API Token
        
    Returns:
        如果 token 有效返回真实客户端，否则返回模拟客户端
        
    注意：
        目前 ModelScope API-Inference 对部分模型支持不完善，
        如遇到 "record not found" 错误，请在 ModelScope 网站上确认
        模型是否支持 API-Inference 调用。
        
        临时解决方案：使用模拟客户端进行功能演示。
        如需使用真实API，请将下方的 USE_MOCK_CLIENT 设为 False。
    """
    # ModelScope API-Inference 不可用，强制使用模拟客户端
    # 人物检测和审美打分使用模拟数据，漫画重绘使用 Gemini API
    USE_MOCK_CLIENT = True
    
    if USE_MOCK_CLIENT:
        print("[AI服务] 使用模拟客户端（人物检测/审美打分）")
        return MockVisionClient(token)
    
    if token and len(token) > 10:
        return VisionClient(token)
    else:
        print("[AI服务] Token 未配置，使用模拟客户端")
        return MockVisionClient(token)


if __name__ == '__main__':
    # 测试代码
    print("[AI服务] 模块加载成功")
    
    # 使用模拟客户端测试
    client = get_vision_client("")
    
    async def test():
        result = await client.classify_image("test.jpg")
        print(f"分类结果: {result}")
        
        score = await client.score_image("test.jpg")
        print(f"评分: {score}")
    
    # asyncio.run(test())
