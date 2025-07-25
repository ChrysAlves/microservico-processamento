# microservico-processamento/Dockerfile (Versão de Depuração Final)

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y \
    python3 \
    python3-pip \
    libreoffice \
    unoconv \
    python3-uno \
    libmagic1 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/output_normalizado

COPY . .

CMD ["python3", "-u", "main.py"]