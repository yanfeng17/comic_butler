
import os
import logging
from modelscope.hub.snapshot_download import snapshot_download
from ultralytics import YOLO

class FaceDetector:
    _instance = None
    _model = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = FaceDetector()
        return cls._instance

    def __init__(self):
        print("[FaceDetector] Initializing Face Detector (Ultralytics + ModelScope)...")
        try:
            # 1. Download model weights from ModelScope
            # This handles caching automatically
            print("[FaceDetector] Downloading/Checking model weights...")
            model_dir = snapshot_download('qianliyx/yolov8s-facedet')
            # The repo contains pytorch_model.onnx
            model_path = os.path.join(model_dir, 'pytorch_model.onnx')
            
            # 2. Load model using Ultralytics
            # Ultralytics supports loading ONNX models directly
            print(f"[FaceDetector] Loading model from {model_path}...")
            self._model = YOLO(model_path)
            
            print("[FaceDetector] Model loaded successfully.")
        except Exception as e:
            print(f"[FaceDetector] Failed to load model: {e}")
            self._model = None

    def detect_faces(self, image_path: str) -> bool:
        """
        Detect if there are faces in the image.
        Returns True if at least one face is detected.
        """
        if not self._model:
            print("[FaceDetector] Model not initialized. Skipping detection (assuming True).")
            return True

        try:
            # Ultralytics inference
            # verbose=False to reduce log noise
            results = self._model(image_path, verbose=False)
            
            if results and len(results) > 0:
                # Check for detected boxes
                # results[0].boxes is the Boxes object
                boxes = results[0].boxes
                
                if boxes and len(boxes) > 0:
                    # Filter by confidence if needed (default usually reasonable)
                    # Let's count high confidence faces
                    # confs = boxes.conf
                    # count = sum(1 for c in confs if c > 0.5)
                    
                    count = len(boxes)
                    print(f"[FaceDetector] Detected {count} faces in {os.path.basename(image_path)}")
                    return True
            
            print(f"[FaceDetector] No face detected in {os.path.basename(image_path)}")
            return False

        except Exception as e:
            print(f"[FaceDetector] Detection error: {e}")
            # Fail safe
            return True
