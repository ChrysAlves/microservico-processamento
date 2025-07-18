# microservico-processamento/Dockerfile (Versão Definitiva)

FROM python:3.9-bullseye

# Instala as dependências de sistema para python-magic (libmagic1) e LibreOffice
RUN apt-get update && \
    apt-get install -y libmagic1 libreoffice-writer --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Garante que o diretório de saída para os PDFs exista
RUN mkdir -p /app/output_normalizado

COPY . .

CMD ["python3", "-u", "main.py"]