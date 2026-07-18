# 示例：Python Worker 的基础 Dockerfile
FROM python:3.10-slim-bookworm

WORKDIR /app

# 复制依赖清单并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

# 复制所有源代码
COPY mudah_automator.py .
COPY main.py .
COPY tasks.py .

# 启动命令 (假设你的主程序叫 main.py)
CMD ["python", "main.py"]