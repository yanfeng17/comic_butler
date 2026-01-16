
import requests
import os

def test_tmpsh():
    # Create a dummy image
    from PIL import Image
    img = Image.new('RGB', (100, 100), color = 'green')
    img_path = "test_tmpsh.jpg"
    img.save(img_path)
    
    print(f"Testing upload to user.tmplink.cx (Generic)...")
    # Tmp.link usually requires login/token now.
    
    # Try file.io (ephemeral)
    print(f"Testing upload to file.io...")
    try:
        url = "https://file.io"
        with open(img_path, 'rb') as f:
            files = {'file': ('test.jpg', f, 'image/jpeg')}
            response = requests.post(url, files=files, timeout=10)
            
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print(f"Success! URL: {response.json().get('link')}")
            return True
            
    except Exception as e:
        print(f"file.io failed: {e}")

    return False

if __name__ == "__main__":
    test_tmpsh()
