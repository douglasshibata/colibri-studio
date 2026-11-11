# 🐦 Colibri Studio — Estação de Trabalho Local para Modelos MoE

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](#)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-brightgreen.svg)](#)
[![Colibrì Engine](https://img.shields.io/badge/Engine-Colibr%C3%AC%20Pure--C-cyan.svg)](#)
[![License](https://img.shields.io/badge/License-Apache%202.0-purple.svg)](#)

O **Colibri Studio** é uma estação de trabalho local de inteligência artificial de classe corporativa construída em torno do motor de inferência **Colibrì** (`JustVugg/colibri`). O sistema transforma o Colibrì em uma alternativa local completa para plataformas de IA na nuvem, preservando a filosofia central: o modelo pertence ao usuário, a inferência roda localmente e a hierarquia de memória unificada engloba **VRAM, RAM e NVMe**.

---

## 📋 Sumário
- [Arquitetura Geral](#-arquitetura-geral)
- [Instalação & Requisitos](#-instalação--requisitos)
- [Configuração](#-configuração)
- [Execução & Uso](#-execução--uso)
- [Documentação das APIs](#-documentação-das-apis)
- [Testes Automatizados](#-testes-automatizados)
- [Segurança & Boas Práticas](#-segurança--boas-práticas)
- [Troubleshooting & Limitações](#-troubleshooting--limitações)

---

## 🏗️ Arquitetura Geral

O Colibri Studio é estruturado de forma estritamente modular e desacoplada:

```
colibri-studio/
├── api/
│   └── routes.py           # Gateway API compatível com OpenAI (/v1) e endpoints do Studio (/api/v1)
├── backend/
│   ├── config.py           # Gerenciador de configurações e persistência JSON
│   └── main.py             # Servidor principal FastAPI & roteamento de ativos estáticos
├── colibri/
│   ├── client.py           # ColibriClient (cliente HTTP REST/SSE para `coli serve`)
│   └── process.py          # ColibriProcessManager (subconjunto seguro de controle subprocesso)
├── frontend/
│   ├── app.js              # Lógica de interface workstation em Vanilla JS
│   ├── index.html          # Layout HTML5 de alta densidade técnica (Dark Aesthetic)
│   └── styles.css          # Estilização CSS3 inspirada em monitoramento de sistemas
├── hardware/
│   └── monitor.py          # Monitoramento de hardware (CPU, RAM, VRAM, throughput NVMe)
├── models/
│   ├── manager.py          # ModelManager (descoberta de 8 famílias MoE e metadados)
│   └── planner.py          # ResourcePlanner (estimador de viabilidade de máquina)
├── storage/
│   └── db.py               # Persistência SQLite de conversas e histórico de mensagens
└── tests/
    └── test_studio.py      # Suíte de testes automatizados com pytest
```

---

## 💻 Instalação & Requisitos

### Pré-requisitos
- **Python:** 3.12 ou superior
- **Colibrì Engine:** Executável `coli` (ou repositório `JustVugg/colibri` compilado via `./setup.sh` em `c/`)
- **Dependências de Sistema:** `gcc`/`clang` com suporte OpenMP (para compilar o motor C se executado a partir do código-fonte).

### Passos de Instalação
```bash
# 1. Instalar dependências Python do Studio
pip install fastapi uvicorn psutil httpx pytest pydantic

# 2. Navegar para o diretório da aplicação
cd colibri-studio
```

---

## ⚙️ Configuração

As configurações são lidas do arquivo `colibri-studio/config.json` e podem ser sobrescritas por variáveis de ambiente:

| Variável / Parâmetro | Padrão | Descrição |
|----------------------|--------|-----------|
| `COLIBRI_EXEC_PATH` | `coli` | Caminho para o executável ou script de inicialização do Colibrì |
| `COLIBRI_MODEL_DIR` | `./models` | Diretório contendo os modelos convertidos do Colibrì |
| `COLIBRI_STUDIO_HOST`| `127.0.0.1` | IP de ligação do servidor Colibri Studio |
| `COLIBRI_STUDIO_PORT`| `8000` | Porta local da interface web do Studio |
| `COLIBRI_SERVE_PORT` | `8080` | Porta onde o servidor `coli serve` é executado |
| `COLIBRI_API_KEY` | `None` | Chave de autenticação opcional para chamadas de API |

---

## 🚀 Execução & Uso

### Iniciar o Colibri Studio
```bash
PYTHONPATH=colibri-studio python3 colibri-studio/backend/main.py
```
Acesse a interface no navegador em **http://127.0.0.1:8000**.

### Interface da Estação de Trabalho
1. **Chat:** Interface estilo ChatGPT com respostas em streaming, markdown, blocos de código com destaque de sintaxe, botão de cópia, edição e regeneração de mensagens, além de configuração de Prompt de Sistema.
2. **Models:** Catálogo dos modelos MoE instalados (`GLM-5.2`, `GLM-5.3-Flash`, `Inkling`, `Kimi K3`, `DeepSeek V4`, `Qwen3.6`, `Qwen3.8`, `OLMoE`).
3. **Hardware:** Painel com atualização em tempo real do uso de CPU, RAM, VRAM e taxas de leitura/escrita de disco NVMe.
4. **Brain:** Visualizador Canvas 2D mostrando o mapa de rotação dos 19.456 especialistas do modelo MoE.
5. **Planner:** Avaliador de recursos para validar se o seu hardware é "Comfortable", "Possible but slow", "Marginal" ou "Not practical".

---

## 📡 Documentação das APIs

### Endpoints Compatíveis com OpenAI (`/v1/*`)
- **`GET /v1/health`**: Status de saúde do motor Colibrì.
- **`GET /v1/models`**: Lista os modelos detectados localmente no formato de API OpenAI.
- **`POST /v1/chat/completions`**: Executa chamadas de inferência de chat completas ou em streaming (SSE).

### Endpoints do Colibri Studio (`/api/v1/*`)
- **`GET /api/v1/config`** & **`POST /api/v1/config`**: Leitura e atualização de preferências.
- **`GET /api/v1/models`**: Lista detalhada de modelos com parâmetros ativos e tamanho em disco.
- **`POST /api/v1/models/select`**: Seleção do modelo ativo.
- **`GET /api/v1/hardware`**: Telemetria do sistema (CPU, RAM, VRAM, NVMe I/O).
- **`POST /api/v1/planner`**: Avaliação de capacidade de máquina para modelos específicos.
- **`GET /api/v1/conversations`** & **`POST /api/v1/conversations`**: Gerenciamento de conversas.

---

## 🧪 Testes Automatizados

A suíte de testes cobre todas as camadas do sistema (persistência, gerenciamento de modelos, planejador, cliente de API e endpoints FastAPI):

```bash
python3 -m pytest colibri-studio/tests/test_studio.py -v
```

---

## 🔒 Segurança & Boas Práticas

- **Binding Local por Padrão:** O servidor conecta-se exclusivamente em `127.0.0.1`.
- **Prevenção de Shell Injection:** Chamadas de subprocesso do motor utilizam listas explícitas de argumentos sem invocação de shell intermediário (`shell=False`).
- **Sanitização de Logs:** Chaves de API e prompts confidenciais nunca são gravados nos logs do servidor.

---

## 🛠️ Troubleshooting & Limitações

- **Servidor Colibrì Offline:** Se o `coli serve` não estiver em execução na porta configurada (ex: `8080`), a interface entra no modo degradado apresentando uma simulação offline clara e orientando a inicialização do motor.
- **Falta de Memória RAM/VRAM:** Verifique a aba **Planner** antes de carregar modelos de grande escala como o Kimi K3 (2.8T) ou Inkling (975B).
