# -*- coding: utf-8 -*-
"""
Gemini 图像分析和生成客户端
使用 Google Gemini API 进行图片分析、打分和风格转换
"""

import os
import asyncio
import base64
from pathlib import Path
from typing import Optional, Tuple
import requests
import time
import json
from io import BytesIO
from image_utils import upload_image_to_imgbb

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("[Gemini] google-generativeai 未安装")

from PIL import Image
import io
from config_manager import get_config_manager


class GeminiImageClient:
    """
    Gemini 图像分析和生成客户端
    
    功能：
    - 人物检测
    - 审美打分
    - 吉卜力风格转换
    """
    
    def __init__(self, token: str):
        """
        初始化客户端
        
        Args:
            token: SiliconFlow API Token
        """
        self.token = token
        # self.analysis_model = ... (不再依赖 Gemini SD)
    
    async def classify_image(self, image_path: str) -> Tuple[bool, str, float]:
        """
        检测图片中是否有人物
        
        Args:
            image_path: 图片路径
            
        Returns:
            (是否有人物, 标签, 置信度)
        """
        if not GENAI_AVAILABLE:
            print("[Gemini] google-generativeai 未安装")
            return True, "person", 0.9  # 默认返回有人
        
        try:
            print(f"[AI] 正在分析图片: {Path(image_path).name}")
            
            config = get_config_manager()
            imgbb_key = config.get('imgbb_api_key', '')
            model = config.get('scoring_model', 'THUDM/GLM-4.1V-9B-Thinking') # 复用评分模型
            
            if not self.token or not imgbb_key:
                # 如果没有 Token，默认返回 True (让后续流程处理)
                return True, "unknown", 0.5

            # 1. 上传图片 (如果已经在 score_image 上传过就好，但在检测阶段可能还没上传)
            # 这里为了简单，再次调用 imgbb (或者优化一下流程？)
            # 实际上 app.py 流程是 classify -> score. 
            img_url = upload_image_to_imgbb(image_path, imgbb_key)
            if not img_url:
                return True, "unknown", 0.5
            
            # 2. 调用 API
            url = "https://api.siliconflow.cn/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                         {"type": "image_url", "image_url": {"url": img_url}},
                         {"type": "text", "text": "Is there a person in this image? Answer only Yes or No."}
                    ]
                }],
                "stream": False,
                "max_tokens": 10
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code != 200:
                print(f"[AI] 检测API失败: {response.text}")
                return True, "unknown", 0.5
                
            content = response.json()['choices'][0]['message']['content'].lower()
            has_person = "yes" in content or "是" in content
            
            return has_person, "person" if has_person else "background", 0.8 if has_person else 0.2

        except Exception as e:
            print(f"[AI] 分析异常: {e}")
            return True, "unknown", 0.5
            

    
    async def score_image(self, image_path: str) -> float:
        """
        对图片进行审美打分 (SiliconFlow)
        
        Args:
            image_path: 图片路径
            
        Returns:
            0-1之间的审美评分
        """
        try:
            print(f"[AI] 正在评分: {Path(image_path).name}")
            
            config = get_config_manager()
            imgbb_key = config.get('imgbb_api_key', '')
            model = config.get('scoring_model', 'THUDM/GLM-4.1V-9B-Thinking')
            
            if not self.token:
                print("[AI] 未配置 SiliconFlow Token")
                import random
                return round(random.uniform(0.5, 0.9), 3)
            if not imgbb_key:
                print("[AI] 未配置 ImgBB API Key (需要图片URL)")
                import random
                return round(random.uniform(0.5, 0.9), 3)

            # 1. 上传图片到 ImgBB
            img_url = upload_image_to_imgbb(image_path, imgbb_key)
            if not img_url:
                print("[AI] 图片上传失败，无法评分")
                return 0.6
                
            # 2. 调用 Chat Completions API
            url = "https://api.siliconflow.cn/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            prompt = config.get('scoring_prompt', """作为一名专业摄影评审，请对这张照片进行审美评分。
                    
                    评判标准：
                    1. 构图美感 (20分)
                    2. 光线运用 (20分)
                    3. 色彩搭配 (20分)
                    4. 人物表情/姿态 (20分)
                    5. 整体氛围 (20分)
                    
                    请只回复一个0到1之间的小数作为最终评分，例如：0.75
                    不要加任何其他文字。
                    """)
            
            payload = {
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": img_url}},
                        {"type": "text", "text": prompt}
                    ]
                }],
                "stream": False
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            
            if response.status_code != 200:
                print(f"[AI] 评分API请求失败: {response.text}")
                return 0.6
                
            result = response.json()
            content = result['choices'][0]['message']['content']
            # 清理可能存在的 Model Thinking 标签
            content = content.replace('<|begin_of_box|>', '').replace('<|end_of_box|>', '')
            print(f"[AI] 原始响应内容: {content}")
            
            # 3. 解析评分
            import re
            numbers = re.findall(r'0\.\d+|\d+\.?\d*', content)
            
            score = 0.6
            if numbers:
                # 尝试找到看起来像 0-1 之间的小数
                for num_str in numbers:
                    try:
                        val = float(num_str)
                        if 0 <= val <= 1:
                            score = val
                            break
                        elif 1 < val <= 100: # 如果是百分制
                             score = val / 100
                             break
                    except:
                        continue
            
            print(f"[AI] 审美评分: {score:.3f} (Model: {model})")
            return score
            
        except Exception as e:
            print(f"[AI] 评分异常: {e}")
            import random
            return round(random.uniform(0.5, 0.8), 3)
    
    async def cartoon_image(self, image_path: str, output_path: str) -> Tuple[bool, str]:
        """
        将图片转换为漫画风格 (SiliconFlow)
        """
        try:
            # 读取配置
            config = get_config_manager()
            imgbb_key = config.get('imgbb_api_key', '')
            model = config.get('cartoon_model', 'Kwai-Kolors/Kolors')
            
            if not self.token:
                return False, "未配置 SiliconFlow Token"
            if not imgbb_key:
                return False, "未配置 ImgBB API Key"

            # 1. 上传图片到 ImgBB 获取 URL
            print(f"[AI] 正在上传图片: {Path(image_path).name}...")
            img_url = upload_image_to_imgbb(image_path, imgbb_key)
            if not img_url:
                return False, "ImgBB 上传失败"

            # 2. 调用 SiliconFlow Image Generation API
            print(f"[AI] 正在调用重绘模型: {model}...")
            url = "https://api.siliconflow.cn/v1/images/generations"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            
            prompt = config.get('cartoon_prompt', "变成日系动漫风格，保持人物特征")
            
            payload = {
                "model": model,
                "prompt": prompt,
                "image": img_url, # SiliconFlow Qwen-Image-Edit 可能支持此字段
                "n": 1,
                "size": "1024x1024"
            }
            
            # 针对 Kolors 的特殊处理（如果 Kolors 不支持 I2I，这可能会失败或变成 T2I）
            # 但用户指定 Kolors 作为重绘模型，我们尝试传 image 参数。
            
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                timeout=120
            )
            
            if response.status_code != 200:
                print(f"[AI] 重绘API失败: {response.text}")
                return False, f"API请求失败: {response.text}"
                
            data = response.json()
            if 'data' in data and len(data['data']) > 0:
                output_url = data['data'][0]['url']
                print(f"[AI] 生成成功，下载图片: {output_url}")
                
                 # 4. 下载并保存结果
                img_res = requests.get(output_url, timeout=30)
                if img_res.status_code == 200:
                    image = Image.open(BytesIO(img_res.content))
                    if image.mode in ('RGBA', 'P'):
                        image = image.convert('RGB')
                    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                    image.save(output_path)
                    return True, ""
                else:
                    return False, "下载生成图片失败"
            
            return False, "API未返回图片数据"

        except Exception as e:
            msg = f"[AI] 转换异常: {e}"
            print(msg)
            return False, msg
    
    async def _local_cartoonize(self, image_path: str, output_path: str) -> bool:
        """
        使用 OpenCV 进行本地卡通化处理（吉卜力风格近似）
        """
        try:
            import cv2
            import numpy as np
            
            print("[OpenCV] 使用本地吉卜力风格处理...")
            
            # 读取图片
            img = cv2.imread(image_path)
            if img is None:
                return False
            
            # 1. 多次双边滤波 - 创造平滑的水彩效果
            for _ in range(3):
                img = cv2.bilateralFilter(img, 9, 75, 75)
            
            # 2. 转换为灰度图
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 3. 高斯模糊后进行边缘检测
            gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.adaptiveThreshold(
                gray_blur, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                blockSize=9,
                C=2
            )
            
            # 4. 颜色量化 - 减少颜色数量
            data = np.float32(img.reshape((-1, 3)))
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
            _, labels, centers = cv2.kmeans(data, 16, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
            centers = np.uint8(centers)
            quantized = centers[labels.flatten()].reshape(img.shape)
            
            # 5. 调整为暖色调（吉卜力风格）
            # 增加橙色/黄色调
            hsv = cv2.cvtColor(quantized, cv2.COLOR_BGR2HSV)
            hsv[:, :, 0] = np.clip(hsv[:, :, 0].astype(np.int32) - 5, 0, 179).astype(np.uint8)  # 色相偏暖
            hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.1, 0, 255).astype(np.uint8)  # 饱和度
            hsv[:, :, 2] = np.clip(hsv[:, :, 2] * 1.05, 0, 255).astype(np.uint8)  # 亮度
            warm = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
            
            # 6. 合并边缘
            edges_colored = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            cartoon = cv2.bitwise_and(warm, edges_colored)
            
            # 7. 轻微模糊使边缘更柔和
            cartoon = cv2.GaussianBlur(cartoon, (3, 3), 0)
            
            # 确保输出目录存在
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # 保存结果
            cv2.imwrite(output_path, cartoon)
            print(f"[OpenCV] 吉卜力风格处理完成: {output_path}")
            return True
            
        except Exception as e:
            print(f"[OpenCV] 本地处理失败: {e}")
            return False
    
    async def close(self):
        """关闭客户端"""
        pass


def get_gemini_client(token: str) -> Optional[GeminiImageClient]:
    """
    获取 AI 客户端 (SiliconFlow)
    
    Args:
        token: SiliconFlow API Token
    """
    if token and len(token) > 10:
        return GeminiImageClient(token)
    else:
        print("[AI] Token 未配置")
        return None



if __name__ == '__main__':
    # 测试代码
    print("[Gemini] 模块加载成功")
    print(f"[Gemini] google-generativeai 可用: {GENAI_AVAILABLE}")
