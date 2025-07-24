import os
import json
import time
import hashlib
import subprocess
import requests
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
import re
import unicodedata

# --- Configurações ---
KAFKA_BROKER = os.environ.get('KAFKA_BROKER', 'kafka:29092')
KAFKA_CONSUMER_TOPIC = 'ingest-requests'
GROUP_ID = 'processing-group'
NORMALIZED_OUTPUT_DIR = '/app/output_normalizado'
SIP_LOCATION_INSIDE_CONTAINER = '/app/temp_ingestao_sip'
MAPOTECA_SERVICE_URL = "http://mapoteca_app:3000/internal/processing-complete"
GESTAO_DADOS_URL = "http://gestao_dados_app:8000"
STORAGE_SERVICE_URL = "http://storage_app:3003/storage/upload"

EXTENSION_MAP = {
    '.pdf': 'pdf', '.doc': 'doc', '.docx': 'docx', '.odt': 'odt',
    '.txt': 'txt', '.xml': 'xml', '.rtf': 'rtf', '.jpg': 'jpg',
    '.jpeg': 'jpg', '.png': 'png', '.gif': 'gif', '.dwg': 'dwg',
}
DOCUMENT_FORMATS_TO_CONVERT = ['pdf', 'doc', 'docx', 'odt', 'txt', 'xml', 'rtf', 'jpg', 'jpeg', 'png', 'gif', 'dwg']

print("--- Microsserviço de Processamento ---")

def sanitize_filename(filename):
    normalized_name = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('utf-8')
    sanitized_name = re.sub(r'[^\w\s.-]', '', normalized_name).strip()
    sanitized_name = re.sub(r'[-\s]+', '_', sanitized_name)
    sanitized_name = re.sub(r'\.+', '.', sanitized_name)
    return sanitized_name

def calculate_checksum(file_path):
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"       ERRO ao calcular checksum: {e}")
        return None

def identify_format_by_extension(filename):
    extension = os.path.splitext(filename)[1].lower()
    return EXTENSION_MAP.get(extension, 'outro')

def normalize_to_pdfa(file_path, output_dir):
    try:
        print(f"       - Normalizando documento para PDF com unoconv...")
        output_filepath = os.path.join(output_dir, os.path.splitext(os.path.basename(file_path))[0] + ".pdf")
        command = ["unoconv", "-f", "pdf", "-o", output_filepath, file_path]
        result = subprocess.run(command, check=True, timeout=120, capture_output=True, text=True, encoding='utf-8')
        if not os.path.exists(output_filepath):
             raise FileNotFoundError(f"unoconv executou mas não criou o arquivo de saída. STDERR: {result.stderr}")
        print(f"       - SUCESSO: Documento normalizado salvo como: {output_filepath}")
        return output_filepath
    except subprocess.CalledProcessError as e:
        print(f"       ERRO no subprocesso do unoconv: STDERR: {e.stderr}")
        return None
    except Exception as e:
        print(f"       ERRO GERAL ao normalizar com unoconv: {e}")
        return None

def enviar_para_storage(file_path, bucket, key):
    try:
        print(f"       -> Enviando '{key}' para o bucket '{bucket}'...")
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(key), f)}
            data = {'bucket': bucket, 'key': key}
            response = requests.post(STORAGE_SERVICE_URL, files=files, data=data, timeout=30)
            response.raise_for_status()
            print(f"       -> SUCESSO: Arquivo enviado para o storage.")
            return response.json()
    except requests.exceptions.RequestException as e:
        print(f"       -> ERRO: Falha ao enviar arquivo para o storage: {e}")
        return None

def notificar_mapoteca(metadados: dict):
    try:
        print(f"     -> Notificando Mapoteca em {MAPOTECA_SERVICE_URL}...")
        response = requests.post(MAPOTECA_SERVICE_URL, json=metadados, timeout=15)
        response.raise_for_status()
        print(f"     -> SUCESSO: Mapoteca notificado!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"     -> ERRO CRÍTICO: Falha ao notificar o Mapoteca: {e}")
        return False

def enviar_metadados_para_gestao(payload_aip: dict):
    try:
        url = f"{GESTAO_DADOS_URL}/aips/"
        print(f"     -> Enviando metadados do AIP para {url}...")
        response = requests.post(url, json=payload_aip, timeout=15)
        if response.status_code == 201:
            print(f"     -> SUCESSO: Metadados do AIP registrados!")
            return True
        else:
            print(f"     -> ERRO: Falha ao registrar metadados. Status: {response.status_code}, Resposta: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"     -> ERRO DE CONEXÃO: Não foi possível se conectar ao serviço de Gestão de Dados: {e}")
        return False

# --- Lógica de Conexão ---
consumer = None
while consumer is None:
    try:
        print("Tentando se conectar ao Kafka...")
        consumer = KafkaConsumer(
            KAFKA_CONSUMER_TOPIC,
            bootstrap_servers=[KAFKA_BROKER],
            auto_offset_reset='earliest',
            group_id=GROUP_ID,
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        print(">>> Conectado ao Kafka! Aguardando tarefas... <<<")
    except NoBrokersAvailable:
        print("Kafka indisponível. Tentando novamente em 10s...")
        time.sleep(10)

# --- Loop Principal ---
for message in consumer:
    try:
        data = message.value
        transfer_id = data.get('transferId')
        ra = data.get('ra', 'sem-ra')
        sip_directory = os.path.join(SIP_LOCATION_INSIDE_CONTAINER, transfer_id)
        
        print(f"\n[*] Nova tarefa! Processando pedido: {transfer_id} para o RA: {ra}")
        if not os.path.isdir(sip_directory):
            continue
        
        for original_filename in os.listdir(sip_directory):
            original_file_path = os.path.join(sip_directory, original_filename)
            if not os.path.isfile(original_file_path):
                continue
            
            sanitized_filename = sanitize_filename(original_filename)
            sanitized_file_path = os.path.join(sip_directory, sanitized_filename)
            
            if original_file_path != sanitized_file_path:
                os.rename(original_file_path, sanitized_file_path)
            
            print(f"   -> Processando arquivo: {original_filename} (como {sanitized_filename})")
            
            checksum = calculate_checksum(sanitized_file_path)
            formato = identify_format_by_extension(sanitized_filename)
            
            print(f"       - Checksum (Original): {checksum}")
            print(f"       - Formato: {formato}")

            normalized_file_path = None
            if formato in DOCUMENT_FORMATS_TO_CONVERT:
                normalized_file_path = normalize_to_pdfa(sanitized_file_path, NORMALIZED_OUTPUT_DIR)
            
            if not checksum:
                continue

            # ALTERAÇÃO: Monta os caminhos do Minio com a estrutura {RA}/{nome_do_arquivo}
            caminho_minio_original = f"{ra}/{sanitized_filename}"
            caminho_minio_preservacao = f"{ra}/{os.path.basename(normalized_file_path)}" if normalized_file_path else None

            enviar_para_storage(sanitized_file_path, 'originals', caminho_minio_original)
            if normalized_file_path:
                enviar_para_storage(normalized_file_path, 'preservation', caminho_minio_preservacao)

            payload_para_mapoteca = {
                "transferId": transfer_id,
                "status": "COMPLETED" if normalized_file_path else "FAILED",
                "message": "" if normalized_file_path else "Falha na normalização do arquivo."
            }
            
            arquivo_original_data = {
                "nome": sanitized_filename,
                "nome_original": original_filename,
                "caminho_minio": caminho_minio_original,
                "checksum": checksum,
                "formato": formato,
            }
            
            payload_para_gestao = {
                "transfer_id": transfer_id,
                "originais": [arquivo_original_data],
                "preservados": []
            }

            if normalized_file_path:
                checksum_preservacao = calculate_checksum(normalized_file_path)
                arquivo_preservado_data = {
                    "nome": os.path.basename(normalized_file_path),
                    "caminho_minio": caminho_minio_preservacao,
                    "checksum": checksum_preservacao,
                    "formato": "pdf",
                }
                payload_para_gestao["preservados"].append(arquivo_preservado_data)

            enviar_metadados_para_gestao(payload_para_gestao)
            notificar_mapoteca(payload_para_mapoteca)

        print(f"[*] Processamento do pedido {transfer_id} concluído.")

    except Exception as e:
        print(f"ERRO inesperado no loop principal: {e}")