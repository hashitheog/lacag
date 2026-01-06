# OFFICIAL PLAYWRIGHT IMAGE (Contains Python, Browsers, & OS Deps)
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Work Directory
WORKDIR /app

# Install Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Code
COPY . .

# Environment Variables
ENV PYTHONUNBUFFERED=1

# Start Command
CMD ["python", "main.py"]
