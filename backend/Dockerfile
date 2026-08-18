# Python slim is intentionally used instead of alpine:
# jmcomic -> curl-cffi / Pillow / pycryptodome are more reliable with glibc wheels.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    COMIC_SHELF_DATA=/app/backend/data

WORKDIR /app/backend

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY server.py ./

# Persistent library root:
#   $COMIC_SHELF_DATA/library/<source>/<source_id>/{album.json,remote.json,pages,covers,thumbs}
VOLUME ["/app/backend/data"]
EXPOSE 8000

CMD ["python", "server.py"]
