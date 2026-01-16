# -*- coding: utf-8 -*-
"""
PushPlus 推送客户端
负责将图片和消息推送到微信
"""

import asyncio
import aiohttp
import requests
import base64
from pathlib import Path
from typing import Optional, Dict, Any
from PIL import Image
import io
from image_utils import upload_image_to_imgbb


class PushPlusClient:
    """
    PushPlus 微信推送客户端
    
    支持：
    - 发送文本消息
    - 发送 HTML 格式消息（嵌入图片）
    - 发送 Markdown 消息
    """
    
    API_URL = "http://www.pushplus.plus/send"
    
    def __init__(self, token: str, imgbb_api_key: str = ""):
        """
        初始化客户端
        
        Args:
            token: PushPlus Token（从 http://www.pushplus.plus/ 获取）
            imgbb_api_key: ImgBB API Key (可选，用于图床功能)
        """
        self.token = token
        self.imgbb_api_key = imgbb_api_key
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 aiohttp 会话"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """关闭会话"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _image_to_base64(self, image_path: str, max_width: int = 300) -> str:
        """
        将图片转换为 Base64 编码
        
        Args:
            image_path: 图片路径
            max_width: 最大宽度（用于压缩）
            
        Returns:
            Base64 编码的图片数据（带 data URI 前缀）
        """
        img = Image.open(image_path)
        
        # 转换为 RGB 模式
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 初始缩放
        if img.width > max_width:
            scale = max_width / img.width
            new_height = int(img.height * scale)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        # 压缩图片到极小尺寸（适应 PushPlus 2万字限制）
        target_size = 12 * 1024  # 目标 12KB
        quality = 70
        buffer = io.BytesIO()
        img.save(buffer, 'JPEG', quality=quality)
        
        # 循环压缩
        while buffer.tell() > target_size:
            buffer = io.BytesIO()
            
            if quality > 20:
                quality -= 10
                img.save(buffer, 'JPEG', quality=quality)
            else:
                # 进一步缩小尺寸
                new_width = int(img.width * 0.8)
                new_height = int(img.height * 0.8)
                if new_width < 50: 
                    break
                    
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                quality = 60 
                img.save(buffer, 'JPEG', quality=quality)
        
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return f"data:image/jpeg;base64,{img_base64}"
    
    async def push_text(self, 
                        content: str, 
                        title: str = "AI 家庭漫画管家") -> Dict[str, Any]:
        """
        发送文本消息
        """
        payload = {
            'token': self.token,
            'title': title,
            'content': content,
            'template': 'txt'
        }
        
        return await self._send(payload)
    
    async def push_html(self, 
                        content: str, 
                        title: str = "AI 家庭漫画管家") -> Dict[str, Any]:
        """
        发送 HTML 格式消息
        """
        payload = {
            'token': self.token,
            'title': title,
            'content': content,
            'template': 'html'
        }
        
        return await self._send(payload)
    


    async def push_image(self, 
                         image_path: str, 
                         title: str = "今日家庭漫画",
                         description: str = "") -> Dict[str, Any]:
        """
        发送图片消息
        
        优先使用 ImgBB 图床，失败则降级为 Base64
        
        Args:
            image_path: 图片路径
            title: 消息标题
            description: 可选的描述文字
            
        Returns:
            API 响应
        """
        try:
            image_src = None
            
            # 1. 优先尝试 ImgBB 上传
            if self.imgbb_api_key:
                print("[推送] 正在尝试上传图片到 ImgBB...")
                image_src = upload_image_to_imgbb(image_path, self.imgbb_api_key)
            
            # 2. 如果 ImgBB 失败或未配置，降级到 Base64 (高压缩)
            if not image_src:
                reason = "未配置 Key" if not self.imgbb_api_key else "上传失败"
                print(f"[推送] ImgBB 不可用 ({reason})，使用 Base64 降级发送...")
                # 注意：Base64 仍需保持极小尺寸以适应微信限制
                image_src = self._image_to_base64(image_path)
            
            # 构建 HTML 内容
            html_content = f'''
            <div style="font-family: Arial, sans-serif; max-width: 100%;">
                <h2 style="color: #333; margin-bottom: 10px;">{title}</h2>
                {f'<p style="color: #666; margin-bottom: 15px;">{description}</p>' if description else ''}
                <img src="{image_src}" style="max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />
                <p style="color: #999; font-size: 12px; margin-top: 10px; text-align: center;">
                    由 AI 家庭漫画管家自动生成
                </p>
            </div>
            '''
            
            return await self.push_html(html_content, title)
            
        except Exception as e:
            msg = f"发送图片准备失败: {e}"
            print(f"[推送] {msg}")
            return {'code': -1, 'msg': msg}
    
    async def push_comic_collage(self,
                                  image_path: str,
                                  date_str: str = "",
                                  photo_count: int = 0) -> Dict[str, Any]:
        """
        发送漫画连环画
        """
        description = ""
        if date_str or photo_count:
            parts = []
            if date_str:
                parts.append(f"📅 {date_str}")
            if photo_count:
                parts.append(f"📷 共 {photo_count} 张精选照片")
            description = " | ".join(parts)
        
        return await self.push_image(
            image_path, 
            title="🎨 今日家庭漫画连环画",
            description=description
        )
    
    async def _send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送请求到 PushPlus API
        """
        try:
            session = await self._get_session()
            
            async with session.post(self.API_URL, json=payload) as resp:
                result = await resp.json()
                
                if result.get('code') == 200:
                    print(f"[推送] 发送成功: {result.get('msg')}")
                else:
                    # 组合详细错误信息
                    error_detail = result.get('data', '')
                    if error_detail:
                        result['msg'] = f"{result.get('msg')} ({error_detail})"
                    
                    print(f"[推送] 发送失败: {result}")
                
                return result
                
        except Exception as e:
            msg = f"请求异常: {e}"
            print(f"[推送] {msg}")
            return {'code': -1, 'msg': msg}
    
    # ========== 同步版本的方法 ==========
    
    def push_text_sync(self, content: str, title: str = "AI 家庭漫画管家") -> Dict[str, Any]:
        """发送文本消息（同步版本）"""
        return asyncio.run(self.push_text(content, title))
    
    def push_image_sync(self, 
                        image_path: str, 
                        title: str = "今日家庭漫画",
                        description: str = "") -> Dict[str, Any]:
        """发送图片消息（同步版本）"""
        return asyncio.run(self.push_image(image_path, title, description))
    
    def push_comic_collage_sync(self,
                                 image_path: str,
                                 date_str: str = "",
                                 photo_count: int = 0) -> Dict[str, Any]:
        """发送漫画连环画（同步版本）"""
        return asyncio.run(self.push_comic_collage(image_path, date_str, photo_count))


class MockPushPlusClient(PushPlusClient):
    """
    模拟推送客户端（用于测试）
    
    当 PushPlus Token 未配置时使用此类
    """
    
    def __init__(self, token: str = "", imgbb_api_key: str = ""):
        super().__init__(token, imgbb_api_key)
    
    async def _send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """模拟发送请求"""
        print(f"[模拟推送] 标题: {payload.get('title')}")
        print(f"[模拟推送] 模板: {payload.get('template')}")
        content = payload.get('content', '')
        if len(content) > 100:
            print(f"[模拟推送] 内容: {content[:100]}... (共 {len(content)} 字符)")
        else:
            print(f"[模拟推送] 内容: {content}")
        
        return {'code': 200, 'msg': '[模拟] 推送成功', 'data': 'mock_message_id'}


def get_push_client(token: str, imgbb_api_key: str = "") -> PushPlusClient:
    """
    获取推送客户端
    
    Args:
        token: PushPlus Token
        imgbb_api_key: ImgBB API Key
        
    Returns:
        如果 token 有效返回真实客户端，否则返回模拟客户端
    """
    if token and len(token) > 10:
        return PushPlusClient(token, imgbb_api_key)
    else:
        print("[推送] Token 未配置，使用模拟客户端")
        return MockPushPlusClient(token, imgbb_api_key)


if __name__ == '__main__':
    # 测试代码
    print("[推送] 模块加载成功")
    
    # 使用模拟客户端测试
    client = get_push_client("")
    
    async def test():
        result = await client.push_text("这是一条测试消息", "测试标题")
        print(f"结果: {result}")
    
    asyncio.run(test())
