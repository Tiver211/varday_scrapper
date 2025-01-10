# Используем базовый образ Python
FROM python:3.13.1

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта, кроме указанных в .dockerignore
COPY . .

# Команда для запуска основного скрипта
CMD ["python", "main.py"]
