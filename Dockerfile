# Dùng Python 3.10.10
FROM python:3.10.10-slim

# Set working dir
WORKDIR /app

# Copy file requirements và cài thư viện
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ source code
COPY . .

# Chạy bot
CMD ["python", "phone-alert-spam.py"]
