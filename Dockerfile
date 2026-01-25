# Switch to DaoCloud mirror to avoid FNNAS 401 Unauthorized error
FROM docker.m.daocloud.io/python:3.11-slim-bookworm

WORKDIR /app

# Install system dependencies
# libgl1-mesa-glx and libglib2.0-0 are required for opencv-python-headless or opencv-python
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies in a single layer to minimize size
# Strategy:
# 1. Install CPU-only PyTorch explicitly
# 2. Install requirements (ignoring torch constraints if they conflict, but usually they won't)
# 3. Aggressively remove any nvidia-* packages that pip might have pulled in (crucial for size)
# 4. Replace opencv-python with headless version for server environments
RUN pip install --no-cache-dir --default-timeout=1000 torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --extra-index-url https://download.pytorch.org/whl/cpu \
    && pip uninstall -y opencv-python \
    && pip install --no-cache-dir opencv-python-headless -i https://mirrors.aliyun.com/pypi/simple/ \
    && pip freeze | grep nvidia | xargs -r pip uninstall -y \
    && pip uninstall -y triton

# Copy application code
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV CONFIG_PATH=/app/data/config.yaml

# Run the application
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
