# Bot de despesas

Bot em Python para registrar despesas por mensagens do Telegram e consultar totais mensais e diários.

## Requisitos

- Python 3.11
- MongoDB Atlas
- Bot do Telegram ativo
- Máquina ou servidor para rodar Docker e o Cloudflare Tunnel

## Variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```env
MONGODB_URI=mongodb+srv://usuario:sua_senha@cluster.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=expenses
TELEGRAM_BOT_TOKEN=SEU_TOKEN_DO_BOT
TELEGRAM_GROUP_NAME=Fluxo de Caixa - Marta
TELEGRAM_CHAT_ID=
TELEGRAM_WEBHOOK_SECRET=uma-chave-secreta-com-32-caracteres
CLOUDFLARE_TUNNEL_TOKEN=token-gerado-no-cloudflare
```

## Dependências

```txt
fastapi==0.110.0
uvicorn==0.28.0
pymongo==4.11.3
httpx==0.27.0
```

## Estrutura do projeto

- `main.py` — aplicação FastAPI e lógica do bot
- `models.py` — conexão e repositório do MongoDB Atlas
- `docker-compose.yml` — backend e Cloudflare Tunnel conectados ao MongoDB Atlas
- `dockerfile` — imagem Docker do backend
- `requeriments.txt` — dependências do projeto

## Rodar localmente

### Opção 1: Python + MongoDB Atlas

```bash
pip install -r requeriments.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Opção 2: Docker Compose

```bash
docker compose up --build
```

Isso sobe a aplicação FastAPI na porta `8000`. O banco fica no MongoDB Atlas.

## Publicar com Cloudflare Tunnel

O Cloudflare Tunnel publica o container FastAPI sem abrir a porta `8000` na internet.
Você precisa de:

1. Um cluster MongoDB Atlas
2. Uma máquina ou VPS com Docker instalado
3. O token do bot do Telegram
4. O nome do grupo correto configurado em `TELEGRAM_GROUP_NAME`
5. Uma conta Cloudflare com um domínio adicionado

No painel Cloudflare:

1. Acesse **Zero Trust > Networks > Tunnels** e crie um túnel.
2. Adicione uma rota pública, por exemplo `bot.seudominio.com`, apontando para `http://backend:8000`.
3. Copie o token do túnel para `CLOUDFLARE_TUNNEL_TOKEN` no arquivo `.env`.
4. Configure as outras variáveis do exemplo acima e execute:

```bash
docker compose up -d --build
```

Registre o webhook no Telegram, substituindo o domínio e o token:

```bash
curl -X POST "https://api.telegram.org/botSEU_TOKEN_DO_BOT/setWebhook" \
	-d "url=https://bot.seudominio.com/webhook/telegram" \
	-d "secret_token=uma-chave-secreta-com-32-caracteres"
```

Verifique a aplicação em `https://bot.seudominio.com/health`. O endpoint deve retornar `{"status":"ok"}`.

## Como funciona

O Telegram envia cada mensagem para `/webhook/telegram`. O bot identifica valores e datas, salva os registros no banco e responde com:

- total do mês
- resumo do mês
- consulta por data
- listagem de registros
- registro de despesas em texto livre

## Observações importantes

- O bot usa webhook do Telegram; não execute `getUpdates` ao mesmo tempo.
- Ele só processa mensagens do grupo correto
- `TELEGRAM_WEBHOOK_SECRET` deve ser igual ao `secret_token` usado no `setWebhook`
- As coleções e índices são criados automaticamente ao iniciar o acesso ao banco
- No MongoDB Atlas, adicione o IP do servidor em **Network Access** e crie um usuário de banco

## Exemplo de deploy

```bash
docker build -t bot-despesas .
docker run -p 8000:8000 --env-file .env bot-despesas
```

---

Se quiser, posso também preparar uma versão mais detalhada do README com instruções de deploy em Render, Railway, VPS Linux ou Docker Compose completo.

## Hospedagem gratuita no Cloudflare Workers

O diretório `cloudflare-worker` contém uma versão do bot para Cloudflare Workers + D1. Esta versão não usa FastAPI, Docker, MongoDB ou Cloudflare Tunnel. Depois do deploy, seu computador pode ficar desligado.

### 1. Instalar e autenticar o Wrangler

Instale o Node.js e execute no PowerShell:

```powershell
cd cloudflare-worker
npm install
npx wrangler login
```

O comando abrirá o navegador para autorizar sua conta Cloudflare.

### 2. Criar o banco D1

```powershell
npx wrangler d1 create bot-despesas-db
```

Copie o `database_id` exibido e substitua `SUBSTITUA_PELO_ID_DO_D1` no arquivo `cloudflare-worker/wrangler.toml`.

Depois crie as tabelas remotamente:

```powershell
npx wrangler d1 execute bot-despesas-db --remote --file=schema.sql
```

### 3. Salvar os segredos no Cloudflare

Execute cada comando e cole o valor quando solicitado. Não coloque esses valores no Git ou no `wrangler.toml`.

```powershell
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_WEBHOOK_SECRET
npx wrangler secret put TELEGRAM_CHAT_ID
```

O `TELEGRAM_CHAT_ID` pode ser omitido se o filtro pelo nome do grupo for suficiente. O nome do grupo fica em `[vars]` no `wrangler.toml`.

### 4. Publicar

```powershell
npx wrangler deploy
```

O Wrangler exibirá um endereço parecido com:

```text
https://bot-despesas.seu-usuario.workers.dev
```

Teste a aplicação:

```powershell
curl.exe https://bot-despesas.seu-usuario.workers.dev/health
```

### 5. Registrar o webhook do Telegram

Use o endereço exibido no deploy:

```powershell
curl.exe -X POST "https://api.telegram.org/botSEU_TOKEN/setWebhook" `
	-d "url=https://bot-despesas.seu-usuario.workers.dev/webhook/telegram" `
	-d "secret_token=SEU_WEBHOOK_SECRET"
```

Confira o resultado:

```powershell
curl.exe "https://api.telegram.org/botSEU_TOKEN/getWebhookInfo"
```

### Dados antigos

O D1 começa vazio. As despesas existentes no MongoDB não são copiadas automaticamente. Para este bot pequeno, você pode começar com o D1 vazio ou fazer uma exportação/importação antes de desligar o MongoDB.