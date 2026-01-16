
import asyncio
import os
from config_manager import get_config_manager
from push_client import get_push_client
from pathlib import Path

async def debug_push():
    config = get_config_manager()
    token = config.get('pushplus_token')
    imgbb_key = config.get('imgbb_api_key')
    
    if not token:
        print("Error: No PushPlus token found in config.")
        return

    print(f"Testing with token: {token[:4]}***{token[-4:] if len(token) > 4 else ''}")
    print(f"ImgBB Key: {imgbb_key[:4]}... if present")
    
    client = get_push_client(token, imgbb_key)
    
    # Test 1: Simple Text
    print("\n--- Test 1: Text Message ---")
    try:
        result = await client.push_text("This is a test message from debug script.", "Debug Test")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Exception: {e}")

    # Test 2: HTML Message (Small)
    print("\n--- Test 2: HTML Message (Small) ---")
    try:
        result = await client.push_html("<b>Bold Text</b>", "Debug HTML")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Exception: {e}")
        
    # Test 3: Large Image Message
    print("\n--- Test 3: Large Image Message ---")
    try:
        # Create a large dummy image with noise (hard to compress)
        import numpy as np
        from PIL import Image
        
        # 1080p noise image
        noise = np.random.randint(0, 255, (1920, 1080, 3), dtype=np.uint8)
        img = Image.fromarray(noise)
        
        img_path = "debug_test_image_large.jpg"
        img.save(img_path)
        
        print(f"Created large image: {os.path.getsize(img_path) / 1024:.2f} KB")
        
        result = await client.push_image(img_path, "Debug Large Image")
        print(f"Result: {result}")
        
        # Cleanup
        if os.path.exists(img_path):
            os.remove(img_path)
            
    except Exception as e:
        print(f"Exception: {e}")
        
    await client.close()

if __name__ == "__main__":
    asyncio.run(debug_push())
