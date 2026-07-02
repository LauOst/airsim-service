# 使用官方 Python 镜像
FROM python:3.10-slim

# 工作目录
WORKDIR /app

# 将 sdk 加入 Python 搜索路径
ENV PYTHONPATH=/app/sdk

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制整个项目
COPY . .

# 对外开放端口
EXPOSE 8888

# 启动 FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8888"]