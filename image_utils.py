# -*- coding: utf-8 -*-
"""
图像处理工具模块
负责图像拼接、水印添加等美化处理
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Union
from PIL import Image, ImageDraw, ImageFont
import io
import requests
import base64


def get_default_font(size: int = 24) -> ImageFont.FreeTypeFont:
    """
    获取默认字体
    
    尝试加载系统字体，如果失败则使用默认字体
    
    Args:
        size: 字体大小
        
    Returns:
        字体对象
    """
    # Windows 系统常用中文字体路径
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
        "C:/Windows/Fonts/simhei.ttf",     # 黑体
        "C:/Windows/Fonts/simsun.ttc",     # 宋体
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
        "/System/Library/Fonts/PingFang.ttc",  # macOS
    ]
    
    for font_path in font_paths:
        try:
            if os.path.exists(font_path):
                return ImageFont.truetype(font_path, size)
        except Exception:
            continue
    
    # 如果都失败，使用默认字体
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def add_timestamp_watermark(
    image: Image.Image,
    timestamp: str,
    position: str = "bottom_right",
    font_size: int = 24,
    opacity: int = 180
) -> Image.Image:
    """
    在图片上添加半透明时间水印
    
    Args:
        image: PIL Image 对象
        timestamp: 时间戳字符串（如 "14:35"）
        position: 水印位置，支持 "bottom_right", "bottom_left", "top_right", "top_left"
        font_size: 字体大小
        opacity: 不透明度（0-255）
        
    Returns:
        添加水印后的图片
    """
    # 创建一个透明图层用于绘制水印
    watermark_layer = Image.new('RGBA', image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark_layer)
    
    # 获取字体
    font = get_default_font(font_size)
    
    # 获取文本边界框
    bbox = draw.textbbox((0, 0), timestamp, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # 添加内边距
    padding = 10
    
    # 计算水印位置
    if position == "bottom_right":
        x = image.width - text_width - padding
        y = image.height - text_height - padding
    elif position == "bottom_left":
        x = padding
        y = image.height - text_height - padding
    elif position == "top_right":
        x = image.width - text_width - padding
        y = padding
    elif position == "top_left":
        x = padding
        y = padding
    else:
        x = image.width - text_width - padding
        y = image.height - text_height - padding
    
    # 绘制半透明背景
    bg_padding = 5
    draw.rectangle(
        [x - bg_padding, y - bg_padding, 
         x + text_width + bg_padding, y + text_height + bg_padding],
        fill=(0, 0, 0, opacity // 2)
    )
    
    # 绘制文字
    draw.text((x, y), timestamp, font=font, fill=(255, 255, 255, opacity))
    
    # 合并图层
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    result = Image.alpha_composite(image, watermark_layer)
    return result


def create_comic_collage(
    image_paths: List[str],
    timestamps: Optional[List[str]] = None,
    padding: int = 20,
    background_color: Tuple[int, int, int] = (255, 255, 255),
    max_width: int = 800,
    add_watermarks: bool = True
) -> Optional[Image.Image]:
    """
    将多张图片竖向拼接成漫画连环画
    
    功能：
    - 图片之间添加白色外边距
    - 每张图片右下角添加半透明时间水印
    - 自动调整图片宽度以保持一致
    
    Args:
        image_paths: 图片路径列表
        timestamps: 时间戳列表，与图片一一对应（如 ["14:35", "15:20"]）
        padding: 图片间的留白像素
        background_color: 背景颜色 RGB 元组
        max_width: 最大宽度，图片将缩放至此宽度
        add_watermarks: 是否添加时间水印
        
    Returns:
        拼接后的 PIL Image 对象，如果失败返回 None
    """
    if not image_paths:
        print("[图像处理] 没有图片可供拼接")
        return None
    
    # 如果没有提供时间戳，使用空列表
    if timestamps is None:
        timestamps = [None] * len(image_paths)
    
    # 确保时间戳数量与图片数量一致
    while len(timestamps) < len(image_paths):
        timestamps.append(None)
    
    # 加载并处理所有图片
    processed_images = []
    
    for i, (path, timestamp) in enumerate(zip(image_paths, timestamps)):
        try:
            # 加载图片
            img = Image.open(path)
            
            # 转换为 RGBA 模式
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # 计算缩放比例，保持宽度一致
            scale = max_width / img.width
            new_height = int(img.height * scale)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # 添加时间水印
            if add_watermarks and timestamp:
                img = add_timestamp_watermark(img, timestamp)
            
            processed_images.append(img)
            
        except Exception as e:
            print(f"[图像处理] 加载图片失败 {path}: {e}")
            continue
    
    if not processed_images:
        print("[图像处理] 没有成功加载任何图片")
        return None
    
    # 计算拼接后的总高度
    total_height = sum(img.height for img in processed_images)
    total_height += padding * (len(processed_images) + 1)  # 顶部、底部和图片间的间距
    
    # 创建背景画布
    canvas = Image.new('RGBA', (max_width + padding * 2, total_height), 
                       (*background_color, 255))
    
    # 拼接图片
    current_y = padding
    for img in processed_images:
        canvas.paste(img, (padding, current_y), img)
        current_y += img.height + padding
    
    # 转换为 RGB 模式（用于保存为 JPEG）
    final_image = canvas.convert('RGB')
    
    return final_image


def save_collage(
    image: Image.Image,
    output_path: str,
    quality: int = 90
) -> bool:
    """
    保存拼接后的图片
    
    Args:
        image: PIL Image 对象
        output_path: 输出文件路径
        quality: JPEG 质量（1-100）
        
    Returns:
        是否保存成功
    """
    try:
        # 确保目录存在
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 根据扩展名确定格式
        ext = Path(output_path).suffix.lower()
        if ext in ['.jpg', '.jpeg']:
            image.save(output_path, 'JPEG', quality=quality)
        elif ext == '.png':
            image.save(output_path, 'PNG')
        else:
            # 默认保存为 JPEG
            image.save(output_path, 'JPEG', quality=quality)
        
        return True
        
    except Exception as e:
        print(f"[图像处理] 保存图片失败: {e}")
        return False


def image_to_base64(image: Union[Image.Image, str], format: str = 'JPEG') -> str:
    """
    将图片转换为 Base64 编码字符串
    
    Args:
        image: PIL Image 对象或图片文件路径
        format: 图片格式（JPEG 或 PNG）
        
    Returns:
        Base64 编码的图片数据（包含 data URI 前缀）
    """
    import base64
    
    # 如果是路径，先加载图片
    if isinstance(image, str):
        image = Image.open(image)
    
    # 确保是 RGB 模式
    if image.mode == 'RGBA' and format == 'JPEG':
        # 创建白色背景
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')
    
    # 转换为字节流
    buffer = io.BytesIO()
    image.save(buffer, format=format, quality=85)
    buffer.seek(0)
    
    # 编码为 Base64
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    # 返回带 data URI 前缀的字符串
    mime_type = 'image/jpeg' if format == 'JPEG' else 'image/png'
    return f"data:{mime_type};base64,{img_base64}"


def compress_image(
    image_path: str,
    max_size_kb: int = 1024,
    output_path: Optional[str] = None
) -> str:
    """
    压缩图片到指定大小以内
    
    Args:
        image_path: 输入图片路径
        max_size_kb: 最大文件大小（KB）
        output_path: 输出路径，如果为 None 则覆盖原文件
        
    Returns:
        压缩后的图片路径
    """
    if output_path is None:
        output_path = image_path
    
    img = Image.open(image_path)
    
    # 确保是 RGB 模式
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    
    # 初始质量
    quality = 95
    
    while quality > 10:
        buffer = io.BytesIO()
        img.save(buffer, 'JPEG', quality=quality)
        size_kb = buffer.tell() / 1024
        
        if size_kb <= max_size_kb:
            # 保存到文件
            with open(output_path, 'wb') as f:
                f.write(buffer.getvalue())
            return output_path
        
        quality -= 5
    
    # 如果还是太大，缩小尺寸
    scale = 0.9
    while scale > 0.1:
        new_size = (int(img.width * scale), int(img.height * scale))
        resized = img.resize(new_size, Image.Resampling.LANCZOS)
        
        buffer = io.BytesIO()
        resized.save(buffer, 'JPEG', quality=70)
        size_kb = buffer.tell() / 1024
        
        if size_kb <= max_size_kb:
            with open(output_path, 'wb') as f:
                f.write(buffer.getvalue())
            return output_path
        
        scale -= 0.1
    
    # 最终保存，不管大小
    img.save(output_path, 'JPEG', quality=50)
    return output_path


if __name__ == '__main__':
    # 测试代码
    print("[图像处理] 模块加载成功")
    
    # 测试字体加载
    font = get_default_font(24)
    print(f"[图像处理] 字体加载: {font}")


def upload_image_to_imgbb(image_path: str, api_key: str) -> Optional[str]:
    """
    将图片上传到 ImgBB
    
    Args:
        image_path: 图片路径
        api_key: ImgBB API Key
        
    Returns:
        成功时返回图片 URL，失败返回 None
    """
    if not api_key:
        print("[ImgBB] 未配置 API Key，跳过上传")
        return None
        
    try:
        print(f"[ImgBB] 正在上传: {os.path.basename(image_path)}...")
        
        with open(image_path, "rb") as file:
            url = "https://api.imgbb.com/1/upload"
            payload = {
                "key": api_key,
                "image": base64.b64encode(file.read()),
            }
            res = requests.post(url, payload)
        
        if res.status_code == 200:
            data = res.json()
            if data['success']:
                img_url = data['data']['url']
                print(f"[ImgBB] 上传成功: {img_url}")
                return img_url
            else:
                print(f"[ImgBB] API返回错误: {data}")
        else:
            print(f"[ImgBB] HTTP错误: {res.status_code} - {res.text}")
            
    except Exception as e:
        print(f"[ImgBB] 上传异常: {e}")
        
    return None
