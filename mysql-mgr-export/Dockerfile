# 使用 Python 作为基础镜像
FROM python:3.6-slim

# 设置阿里云 PyPI 源
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# 设置工作目录
WORKDIR /app

# 复制代码文件到容器
COPY mysql_mgr_exporter.py /app/
COPY requirements.txt /app/

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 启动 Exporter
CMD ["python", "mysql_mgr_exporter.py"]
