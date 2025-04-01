FROM python:3.11-slim-buster
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ./app .
COPY users.txt .

# Create directories for data storage
RUN mkdir -p /app/data /app/user_data /app/session_data
RUN chmod -R 777 /app/data /app/user_data /app/session_data

# Copy PDF files for indexing
COPY ./app/data/ifrs.pdf /app/data/
COPY ./app/data/blueprint.pdf /app/data/

# Copy and set up entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Make sure a debug message is printed during startup so we know what dirs exist
RUN echo "Directory structure:" && ls -la /app
RUN echo "Data directory contents:" && ls -la /app/data

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 