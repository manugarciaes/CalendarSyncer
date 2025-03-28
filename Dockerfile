FROM python:3.11-slim

WORKDIR /app

# Install required packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create a requirements.txt file from pyproject.toml
COPY pyproject.toml /app/
RUN python -c "import re; \
    content = open('pyproject.toml').read(); \
    deps = re.findall(r'\"([^\"]+)>=([^\"]+)\"', content); \
    with open('requirements.txt', 'w') as f: \
    f.write('\n'.join([pkg + '>=' + ver for pkg, ver in deps]))"

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/

# Make the entrypoint script executable
RUN chmod +x /app/docker-entrypoint.sh

# Expose port
EXPOSE 5000

# Set the entrypoint script
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--reuse-port", "--reload", "main:app"]