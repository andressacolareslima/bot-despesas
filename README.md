# Bot de despesas

Bot em Python para registrar despesas por mensagens do Telegram e consultar totais mensais e diários.

## Requisitos

- Python 3.11
- PostgreSQL
- Bot do Telegram ativo
- Serviço de hospedagem/VPS para rodar online

## Variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```env
POSTGRES_USER=user
POSTGRES_PASSWORD=sua_senha
POSTGRES_DB=expenses
TELEGRAM_BOT_TOKEN=SEU_TOKEN_DO_BOT
TELEGRAM_GROUP_NAME=Fluxo de Caixa - Marta
DATABASE_URL=postgresql://user:sua_senha@db:5432/expenses
```

## Dependências

```txt
fastapi==0.110.0
uvicorn==0.28.0
sqlalchemy==2.0.28
psycopg2-binary==2.9.9
httpx==0.27.0
```

## Estrutura do projeto

- `main.py` — aplicação FastAPI e lógica do bot
- `models.py` — modelos do banco e conexão com PostgreSQL
- `docker-compose.yml` — banco e backend
- `dockerfile` — imagem Docker do backend
- `requeriments.txt` — dependências do projeto

## Rodar localmente

### Opção 1: Python + PostgreSQL

```bash
pip install -r requeriments.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Opção 2: Docker Compose

```bash
docker compose up --build
```

Isso sobe:
- PostgreSQL na porta `5432`
- aplicação FastAPI na porta `8000`

## Rodar online

Para publicar o projeto, você precisa de:

1. Um banco PostgreSQL em produção ou gerenciado
2. Um servidor/VPS ou plataforma com suporte a containers
3. O token do bot do Telegram
4. O nome do grupo correto configurado em `TELEGRAM_GROUP_NAME`
5. Variáveis de ambiente configuradas no ambiente de produção

## Como funciona

O bot escuta mensagens do Telegram, identifica valores e datas, salva os registros no banco e responde com:

- total do mês
- resumo do mês
- consulta por data
- listagem de registros
- registro de despesas em texto livre

## Observações importantes

- O bot usa polling do Telegram com `getUpdates`
- Ele só processa mensagens do grupo correto
- O banco é criado automaticamente ao iniciar a aplicação

## Exemplo de deploy

```bash
docker build -t bot-despesas .
docker run -p 8000:8000 --env-file .env bot-despesas
```

---

Se quiser, posso também preparar uma versão mais detalhada do README com instruções de deploy em Render, Railway, VPS Linux ou Docker Compose completo.