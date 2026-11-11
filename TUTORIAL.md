# 📘 Tutorial de Operação e Instalação: Colibri Studio — Estação de Trabalho Local para Modelos MoE

Guia passo a passo para configuração, inicialização, execução de testes e resolução de problemas no projeto **Colibri Studio — Estação de Trabalho Local para Modelos MoE** (`colibri-studio`).

---

## 🛠️ 1. Visão Geral e Arquitetura

O **Colibri Studio** é uma estação de trabalho local de inteligência artificial de classe corporativa construída em torno do motor de inferência **Colibrì** (`JustVugg/colibri`). O sistema transforma o Colibrì em uma alternativa local completa para plataformas de IA na nuvem, preservando a filosofia central: o modelo pertence ao usuário, a inferênc...

- **Tecnologias Principais:** Python 3.11+
- **Diretório do Módulo:** `colibri-studio`

---

## 📋 2. Pré-requisitos do Sistema

Antes de iniciar a configuração local, certifique-se de ter os seguintes componentes instalados em seu ambiente de desenvolvimento:

- **Git:** Para clonagem e versionamento.
- **Ambiente de Runtime:** Ferramentas correspondentes à stack do projeto (Python 3.11+):
  - Node.js 18+ / Python 3.11+ / Go 1.24+ / Java 21 LTS / Flutter SDK / CMake.
- **Docker Engine & Docker Compose:** Recomendado para execução de containers e dependências.

---

## 🚀 3. Passo a Passo de Setup e Instalação

### Passo 1: Acessar a Pasta do Projeto
```bash
cd colibri-studio
```

### Passo 2: Instalação de Dependências
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

---

## ⚙️ 4. Configuração do Ambiente

Configure o arquivo de variáveis de ambiente (`.env` ou configurações de projeto) localizado no diretório raiz de `colibri-studio`:

```ini
# Configurações Gerais
ENVIRONMENT=development
LOG_LEVEL=info

# URLs de Conexão e Serviços
DATABASE_URL=sqlite:///./app.db
REDIS_URL=redis://localhost:6379/0
```

---

## 💻 5. Guia de Execução

### Inicializando a Aplicação
Inicie a aplicação ou serviço utilizando o comando correspondente:

```bash
python3 main.py # ou uvicorn/streamlit/fastapi app
```

---

## 🧪 6. Testes e Validação

Para validar o funcionamento do módulo e garantir que não há regressões, execute a suíte de testes:

```bash
python3 -m pytest tests/ -v
```

---

## 🔍 7. Troubleshooting e Resolução de Problemas

1. **Porta em uso ou Conflito de Rede:**
   - Cancele processos pendentes na porta utilizada ou utilize `docker compose down` e suba novamente.
2. **Erros de Dependências Ausentes:**
   - Certifique-se de estar executando os comandos dentro do diretório `colibri-studio` e com as versões corretas das linguagens.
3. **Falhas na Suíte de Testes:**
   - Verifique se as variáveis de ambiente necessárias foram inicializadas corretamente.
