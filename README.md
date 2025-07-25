# Microsserviço de Processamento

## 📋 Visão Geral

O **Microsserviço de Processamento** é o "Departamento de Qualidade e Montagem" da arquitetura de preservação digital. Ele atua como o operário especializado que transforma as caixas originais (SIPs - Submission Information Packages) em caixas perfeitamente preservadas (AIPs - Archival Information Packages).

### Função Principal
- Recebe SIPs através do Kafka
- Processa e valida arquivos digitais
- Normaliza documentos para formatos de preservação (PDF/A)
- Calcula checksums para integridade
- Cria AIPs estruturados
- Envia metadados para o sistema de gestão
- Notifica o Mapoteca sobre a conclusão do processamento

## 🏗️ Arquitetura e Comunicação

### Posição na Arquitetura
```
Front-End → Middleware → Mapoteca → Ingestão → [KAFKA] → PROCESSAMENTO → Gestão de Dados
                                                    ↓
                                               Storage (MinIO)
```

### Comunicações do Microsserviço

#### 📥 **ENTRADA (Consome)**
- **Kafka Topic**: `ingest-requests`
  - Recebe mensagens sobre novos SIPs prontos para processamento
  - Formato da mensagem:
    ```json
    {
      "transferId": "uuid-do-pedido",
      "ra": "numero-do-ra-usuario"
    }
    ```

#### 📤 **SAÍDA (Produz)**
- **API REST → Gestão de Dados**: `POST /aips/`
  - Envia metadados completos dos AIPs criados
  
- **API REST → Mapoteca**: `POST /internal/processing-complete`
  - Notifica conclusão do processamento
  
- **API REST → Storage**: `POST /storage/upload`
  - Envia arquivos originais e normalizados para o MinIO

### Restrições de Comunicação
- ✅ **PODE** comunicar com: Gestão de Dados, Mapoteca, Storage
- ❌ **NÃO PODE** comunicar diretamente com: Front-End, Ingestão, Acesso
- 🔄 **Comunicação Assíncrona**: Apenas via Kafka (consumo)
- 🔄 **Comunicação Síncrona**: APIs REST para notificações e envio de dados

## 🔄 Fluxos de Operação

### Fluxo Principal de Processamento

1. **Recepção via Kafka**
   ```
   Kafka (ingest-requests) → Microsserviço de Processamento
   ```

2. **Processamento do SIP**
   - Localiza arquivos no diretório temporário
   - Sanitiza nomes de arquivos
   - Calcula checksums SHA-256
   - Identifica formatos por extensão

3. **Normalização**
   - Converte documentos para PDF usando LibreOffice/unoconv
   - Mantém arquivos originais intactos
   - Gera versões de preservação

4. **Armazenamento**
   ```
   Processamento → Storage (MinIO)
   ├── Bucket 'originals': arquivos originais
   └── Bucket 'preservation': arquivos normalizados
   ```

5. **Registro de Metadados**
   ```
   Processamento → Gestão de Dados
   ```

6. **Notificação de Conclusão**
   ```
   Processamento → Mapoteca
   ```

### Estrutura de Dados Processados

#### Metadados Enviados para Gestão de Dados
```json
{
  "transfer_id": "uuid-do-pedido",
  "originais": [
    {
      "nome": "documento_sanitizado.pdf",
      "nome_original": "Documento Original.pdf",
      "caminho_minio": "12345/documento_sanitizado.pdf",
      "checksum": "sha256-hash",
      "formato": "pdf"
    }
  ],
  "preservados": [
    {
      "nome": "documento_sanitizado.pdf",
      "caminho_minio": "12345/documento_sanitizado.pdf",
      "checksum": "sha256-hash-preservacao",
      "formato": "pdf"
    }
  ]
}
```

#### Notificação para Mapoteca
```json
{
  "transferId": "uuid-do-pedido",
  "status": "COMPLETED|FAILED",
  "message": "mensagem-de-status"
}
```

## 🛠️ Tecnologias e Dependências

### Stack Tecnológico
- **Linguagem**: Python 3
- **Container**: Docker (Ubuntu 22.04)
- **Mensageria**: Apache Kafka
- **Processamento de Documentos**: LibreOffice + unoconv
- **HTTP Client**: requests

### Dependências Python
```
kafka-python    # Cliente Kafka
python-magic    # Identificação de tipos de arquivo
requests        # Cliente HTTP
```

### Dependências do Sistema
- LibreOffice (conversão de documentos)
- unoconv (interface de linha de comando para LibreOffice)
- python3-uno (bindings Python para LibreOffice)

## 📁 Estrutura do Projeto

```
microservico-processamento/
├── main.py              # Aplicação principal
├── requirements.txt     # Dependências Python
├── Dockerfile          # Configuração do container
├── start.sh            # Script de inicialização
├── README.md           # Este arquivo
└── output_normalizado/ # Diretório de saída (arquivos processados)
```

## ⚙️ Configuração

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `KAFKA_BROKER` | `kafka:29092` | Endereço do broker Kafka |
| `MAPOTECA_SERVICE_URL` | `http://mapoteca_app:3000/internal/processing-complete` | URL do Mapoteca |
| `GESTAO_DADOS_URL` | `http://gestao_dados_app:8000` | URL da Gestão de Dados |
| `STORAGE_SERVICE_URL` | `http://storage_app:3003/storage/upload` | URL do Storage |

### Diretórios Internos
- `/app/temp_ingestao_sip`: Diretório onde os SIPs são recebidos
- `/app/output_normalizado`: Diretório de saída para arquivos processados

#

## 🔍 Funcionalidades Detalhadas

### 1. Sanitização de Nomes de Arquivos
- Remove caracteres especiais e acentos
- Substitui espaços por underscores
- Normaliza para ASCII
- Evita conflitos no sistema de arquivos

### 2. Cálculo de Checksums
- Algoritmo SHA-256
- Verificação de integridade
- Processamento em blocos para eficiência de memória

### 3. Identificação de Formatos
- Baseada em extensões de arquivo
- Suporte para: PDF, DOC, DOCX, ODT, TXT, XML, RTF, JPG, PNG, GIF, DWG

### 4. Normalização de Documentos
- Conversão para PDF usando LibreOffice
- Timeout de 120 segundos por arquivo
- Tratamento de erros robusto
- Preservação do arquivo original

### 5. Organização no Storage
- **Estrutura**: `{RA}/{nome_arquivo}`
- **Buckets separados**: 
  - `originals`: arquivos originais
  - `preservation`: versões normalizadas

## 🔧 Monitoramento e Logs

### Logs Principais
- Conexão com Kafka
- Processamento de cada arquivo
- Cálculo de checksums
- Normalização de documentos
- Envio para storage
- Notificações para outros serviços

### Tratamento de Erros
- Reconexão automática ao Kafka
- Timeout em operações de rede
- Logs detalhados de falhas
- Continuidade do processamento mesmo com falhas individuais

## 🔒 Segurança e Boas Práticas

### Isolamento
- Executa em container Docker isolado
- Não tem acesso direto ao sistema de arquivos do host
- Comunicação apenas através de APIs definidas

### Integridade
- Checksums SHA-256 para todos os arquivos
- Validação de uploads para storage
- Confirmação de operações críticas

### Resiliência
- Reconexão automática ao Kafka
- Processamento idempotente
- Logs para auditoria e debugging

## 📊 Métricas e Performance

### Capacidades
- Processamento assíncrono via Kafka
- Suporte a arquivos grandes (streaming)
- Timeout configurável para conversões
- Processamento em lote por SIP

### Limitações
- Dependente do LibreOffice para conversões
- Identificação de formato básica (por extensão)
- Validação limitada sem ferramentas especializadas (JHOVE)

## 🤝 Integração com Outros Microsserviços

### Dependências Upstream
1. **Microsserviço de Ingestão** → Publica no Kafka
2. **Apache Kafka** → Entrega mensagens

### Dependências Downstream
1. **Microsserviço de Gestão de Dados** → Recebe metadados
2. **Microsserviço Storage** → Recebe arquivos
3. **Microsserviço Mapoteca** → Recebe notificações

### Fluxo Completo na Arquitetura
```
Front-End → Mapoteca → Ingestão → Kafka → PROCESSAMENTO
                                              ↓
                                    ┌─── Gestão de Dados
                                    ├─── Storage (MinIO)  
                                    └─── Mapoteca (notificação)
```

## 📝 Notas de Desenvolvimento

### Próximas Melhorias
- Implementação de ferramentas especializadas (JHOVE)
- Identificação de formato mais robusta (python-magic)
- Validação profunda de estruturas de arquivo
- Métricas de performance
- Health checks

### Considerações Arquiteturais
- Microsserviço stateless
- Processamento idempotente
- Separação clara de responsabilidades
- Comunicação assíncrona para escalabilidade