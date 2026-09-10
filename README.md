# Bot de Despesas

Bot de Telegram para registrar despesas em segundos e consultar os totais do grupo.

> **Produção:** [bot-despesas.bot-despesas.workers.dev](https://bot-despesas.bot-despesas.workers.dev)<br>
> **Hospedagem:** Cloudflare Workers<br>
> **Banco:** Cloudflare D1<br>
> **Custo:** plano gratuito para este volume de uso

## Visão geral

```text
Telegram
	 ↓ webhook HTTPS
Cloudflare Worker
	 ↓ binding DB
Cloudflare D1
```

O bot roda na nuvem, portanto o computador local não precisa ficar ligado. A aplicação foi dimensionada para um grupo pequeno com uso diário.

## O que ele faz

| Comando | Função |
| --- | --- |
| `/ajuda` | Exibe as instruções do bot |
| `/total` | Mostra o total acumulado no mês |
| `/mês` ou `/mes` | Mostra o resumo mensal detalhado |
| `/entradas` | Lista os registros salvos |
| `/consultar DD/MM/AAAA` | Consulta as despesas de um dia |
| `/pago` | Apaga todos os registros |

Também aceita mensagens como:

```text
25,90
25,90 10/09/2026
10/09/2026 25,90
Almoço R$ 25,90
Mercado R$ 80,00
```

Ao registrar uma despesa, o bot informa cada valor, a soma da mensagem e o total acumulado no mês.

## Estrutura

```text
cloudflare-worker/
├── src/index.js       # lógica do Worker e webhook Telegram
├── schema.sql          # tabelas do D1
├── wrangler.toml       # configuração do Cloudflare
├── package.json        # scripts e dependência do Wrangler
└── package-lock.json   # versões fixadas
```

## Pré-requisitos

- Conta gratuita no [Cloudflare](https://dash.cloudflare.com/)
- Bot criado pelo [@BotFather](https://t.me/BotFather)
- Node.js instalado
- Bot adicionado ao grupo do Telegram

Não é necessário Python, Docker, MongoDB, VPS ou Cloudflare Tunnel.

## Configuração inicial

Abra o PowerShell na raiz do projeto:

```powershell
cd cloudflare-worker
npm install
npx wrangler login
```

O `wrangler login` abrirá o navegador para autorizar sua conta Cloudflare.

### Criar o banco D1

Crie o banco uma única vez:

```powershell
npx wrangler d1 create bot-despesas-db
```

Copie o `database_id` exibido e coloque-o em `wrangler.toml`:

```toml
[[d1_databases]]
binding = "DB"
database_name = "bot-despesas-db"
database_id = "SEU_DATABASE_ID"
```

Crie as tabelas no banco de produção:

```powershell
npx wrangler d1 execute bot-despesas-db --remote --file=schema.sql
```

Esse comando deve ser executado apenas quando o banco ainda não tiver sido inicializado.

### Cadastrar os segredos

Os valores secretos ficam no Cloudflare e não devem ser colocados no Git:

```powershell
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_WEBHOOK_SECRET
```

O nome do grupo fica configurado em `wrangler.toml`:

```toml
[vars]
TELEGRAM_GROUP_NAME = "Fluxo de Caixa - Marta"
```

Se preferir filtrar pelo ID do grupo, cadastre também:

```powershell
npx wrangler secret put TELEGRAM_CHAT_ID
```

## Publicar

Dentro de `cloudflare-worker`, execute:

```powershell
npx wrangler deploy
```

O endereço atual é:

```text
https://bot-despesas.bot-despesas.workers.dev
```

Teste o Worker:

```powershell
Invoke-WebRequest -UseBasicParsing https://bot-despesas.bot-despesas.workers.dev/health
```

Resposta esperada:

```json
{"status":"ok"}
```

## Configurar o webhook do Telegram

Substitua `SEU_TOKEN` e `SEU_WEBHOOK_SECRET` pelos valores reais:

```powershell
curl.exe -X POST "https://api.telegram.org/botSEU_TOKEN/setWebhook" `
	-d "url=https://bot-despesas.bot-despesas.workers.dev/webhook/telegram" `
	-d "secret_token=SEU_WEBHOOK_SECRET"
```

Confirme a configuração:

```powershell
curl.exe "https://api.telegram.org/botSEU_TOKEN/getWebhookInfo"
```

O resultado correto deve conter:

```json
{
	"ok": true,
	"result": {
		"url": "https://bot-despesas.bot-despesas.workers.dev/webhook/telegram",
		"pending_update_count": 0
	}
}
```

## Teste rápido

No grupo configurado, envie:

```text
25,90
```

Depois teste:

```text
/total
/mês
/entradas
/consultar 10/09/2026
```

## Segurança

- Nunca envie tokens para o GitHub ou para o README.
- O arquivo `.env` é ignorado pelo Git.
- Os segredos de produção ficam no Cloudflare via `wrangler secret put`.
- Se um token for exposto, revogue-o e gere outro imediatamente.
- O webhook valida `X-Telegram-Bot-Api-Secret-Token`.
- O Worker aceita apenas mensagens do grupo configurado.

## Manutenção

Ver os segredos cadastrados, sem revelar os valores:

```powershell
npx wrangler secret list
```

Consultar registros do D1:

```powershell
npx wrangler d1 execute bot-despesas-db --remote --command "SELECT * FROM expenses ORDER BY expense_date, id"
```

Publicar uma nova versão após alterar o código:

```powershell
npx wrangler deploy
```

## Dados antigos

O banco D1 é independente do MongoDB antigo. Registros que estavam no MongoDB não são migrados automaticamente. O Worker atual usa exclusivamente o D1.