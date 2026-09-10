const MAX_AMOUNT = 99999999.99;

function brazilDate() {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Sao_Paulo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function displayDate(value) {
  const [year, month, day] = value.split("-");
  return `${day}/${month}/${year}`;
}

function parseDate(value) {
  const parts = value.split("/").map(Number);
  if (parts.length < 2 || parts.length > 3) throw new Error("invalid date");
  const [day, month] = parts;
  let year = parts[2] || Number(brazilDate().slice(0, 4));
  if (year < 100) year += 2000;
  const candidate = new Date(Date.UTC(year, month - 1, day));
  if (
    candidate.getUTCFullYear() !== year ||
    candidate.getUTCMonth() !== month - 1 ||
    candidate.getUTCDate() !== day
  ) throw new Error("invalid date");
  return `${year.toString().padStart(4, "0")}-${month.toString().padStart(2, "0")}-${day.toString().padStart(2, "0")}`;
}

function parseAmount(value) {
  const amount = Number(value.replace(/[ ]/g, "").replace(",", "."));
  if (!Number.isFinite(amount) || Math.abs(amount) > MAX_AMOUNT) throw new Error("invalid amount");
  return amount;
}

function formatMoney(value) {
  return `R$ ${Number(value).toFixed(2).replace(".", ",")}`;
}

function monthRange(date) {
  const [year, month] = date.split("-").map(Number);
  const next = month === 12 ? `${year + 1}-01-01` : `${year}-${String(month + 1).padStart(2, "0")}-01`;
  return [`${year}-${String(month).padStart(2, "0")}-01`, next];
}

function commandName(text) {
  return text.toLocaleLowerCase().split("@")[0];
}

async function telegram(env, method, body) {
  const response = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Telegram HTTP ${response.status}`);
  const result = await response.json();
  if (!result.ok) throw new Error(result.description || "Telegram API error");
  return result;
}

async function reply(env, chatId, text) {
  await telegram(env, "sendMessage", { chat_id: chatId, text });
}

async function addExpense(env, sender, amount, expenseDate) {
  await env.DB.prepare(
    "INSERT INTO expenses (sender, amount, expense_date) VALUES (?, ?, ?)",
  ).bind(sender, amount, expenseDate).run();
}

async function handleMessage(env, update) {
  const message = update.message || {};
  const chat = message.chat || {};
  const configuredChat = env.TELEGRAM_CHAT_ID && String(chat.id) === String(env.TELEGRAM_CHAT_ID);
  const configuredTitle = (env.TELEGRAM_GROUP_NAME || "").trim().toLocaleLowerCase();
  const chatTitle = (chat.title || "").trim().toLocaleLowerCase();
  if (!["group", "supergroup"].includes(chat.type)) return "ignored_chat_type";
  if (chatTitle !== configuredTitle && !configuredChat) return "ignored_chat";
  if (!message.text) return "ignored_message";

  const text = message.text.trim();
  const senderData = message.from || {};
  const sender = [senderData.first_name || "Alguém", senderData.last_name].filter(Boolean).join(" ");
  const messageId = String(update.update_id ?? message.message_id);
  const duplicate = await env.DB.prepare(
    "SELECT message_id FROM processed_messages WHERE message_id = ?",
  ).bind(messageId).first();
  if (duplicate) return "duplicate_ignored";

  const command = commandName(text);

  if (["/ajuda", "/help"].includes(command)) {
    await reply(env, chat.id, "Comandos: /total, /mês, /entradas, /consultar DD/MM/AAAA e /pago.\n\nRegistre: 25,90 ou Almoço R$ 25,90.");
    return "help_sent";
  }

  if (command === "/pago") {
    await env.DB.batch([
      env.DB.prepare("DELETE FROM expenses"),
      env.DB.prepare("DELETE FROM processed_messages"),
    ]);
    await reply(env, chat.id, "Registros apagados. Banco zerado.");
    return "cleared";
  }

  const consult = text.match(/^\/consultar(?:@[^\s]+)?\s+(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)$/i);
  if (consult) {
    let target;
    try { target = parseDate(consult[1]); } catch { await reply(env, chat.id, "Data inválida. Use DD/MM/AAAA."); return "invalid_date"; }
    const entries = await env.DB.prepare("SELECT amount, sender FROM expenses WHERE expense_date = ? ORDER BY id").bind(target).all();
    const total = entries.results.reduce((sum, entry) => sum + entry.amount, 0);
    const details = entries.results.map((entry) => `- R$ ${entry.amount.toFixed(2)} - ${entry.sender}`).join("\n");
    await reply(env, chat.id, entries.results.length ? `${displayDate(target)}\n${details}\nTotal do dia: R$ ${total.toFixed(2)}` : `Nenhum registro em ${displayDate(target)}.`);
    return "consulted";
  }

  if (command === "/entradas") {
    const entries = await env.DB.prepare("SELECT expense_date, amount FROM expenses ORDER BY expense_date, id").all();
    const total = entries.results.reduce((sum, entry) => sum + entry.amount, 0);
    const details = entries.results.map((entry) => `- ${displayDate(entry.expense_date)}: R$ ${entry.amount.toFixed(2)}`).join("\n");
    await reply(env, chat.id, entries.results.length ? `Entradas registradas:\n${details}\n\nTotal: R$ ${total.toFixed(2)}` : "Nenhuma entrada registrada.");
    return "entries_sent";
  }

  if (["/total", "!total", "/mês", "/mes"].includes(command)) {
    const [start, end] = monthRange(brazilDate());
    const entries = await env.DB.prepare("SELECT expense_date, amount FROM expenses WHERE expense_date >= ? AND expense_date < ? ORDER BY expense_date, id").bind(start, end).all();
    const total = entries.results.reduce((sum, entry) => sum + entry.amount, 0);
    const details = entries.results.map((entry) => `- ${entry.expense_date.slice(8)}/${entry.expense_date.slice(5, 7)}: R$ ${entry.amount.toFixed(2)}`).join("\n");
    await reply(env, chat.id, command === "/mês" || command === "/mes" ? `Resumo do mês:\n${details || "Nenhum registro."}\nTotal: R$ ${total.toFixed(2)}` : `Total acumulado: R$ ${total.toFixed(2)}`);
    return "summary_sent";
  }

  const registered = [];
  for (const line of text.split(/\r?\n/)) {
    const matches = [...line.matchAll(/R\$\s*([-+]?\s*\d+(?:[.,]\d{1,2})?)/gi)];
    const natural = matches.length ? matches : [...line.matchAll(/\b(?:deu|total(?:izou)?|gastei|custou|ficou|saiu|valor(?:\s+foi)?)\s*:?\s*(?:R\$\s*)?([-+]?\s*\d+(?:[.,]\d{1,2})?)/gi)];
    if (!natural.length) continue;
    let expenseDate = brazilDate();
    const dateMatch = line.match(/(?<!\d)(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)(?!\d)/);
    if (dateMatch) { try { expenseDate = parseDate(dateMatch[1]); } catch { continue; } }
    for (const match of natural) registered.push([parseAmount(match[1]), expenseDate]);
  }

  if (!registered.length) {
    const onlyValue = text.match(/^[-+]?\s*\d+(?:[.,]\d{1,2})?$/);
    const dateValue = text.match(/^(?:(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)\s+([-+]?\s*\d+(?:[.,]\d{1,2})?)|([-+]?\s*\d+(?:[.,]\d{1,2})?)\s+(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?))$/);
    if (onlyValue) registered.push([parseAmount(text), brazilDate()]);
    else if (dateValue) {
      try { registered.push([parseAmount(dateValue[2] || dateValue[3]), parseDate(dateValue[1] || dateValue[4])]); } catch { await reply(env, chat.id, "Data inválida. Use DD/MM/AAAA."); return "invalid_date"; }
    }
  }

  if (!registered.length) return "no_action";
  for (const [amount, expenseDate] of registered) await addExpense(env, sender, amount, expenseDate);
  await env.DB.prepare("INSERT INTO processed_messages (message_id) VALUES (?)").bind(messageId).run();
  const total = registered.reduce((sum, [amount]) => sum + amount, 0);
  const [monthStart, monthEnd] = monthRange(registered[registered.length - 1][1]);
  const monthResult = await env.DB.prepare(
    "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE expense_date >= ? AND expense_date < ?",
  ).bind(monthStart, monthEnd).first();
  const monthTotal = Number(monthResult.total || 0);
  const values = registered.map(([amount, expenseDate]) => `- ${formatMoney(amount)} (${displayDate(expenseDate)})`).join("\n");
  await reply(
    env,
    chat.id,
    `${registered.length} valor(es) registrado(s):\n${values}\n\nSoma da mensagem: ${formatMoney(total)}\nTotal acumulado no mês: ${formatMoney(monthTotal)}`,
  );
  return "recorded";
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/health") return Response.json({ status: "ok" });
    if (request.method !== "POST" || url.pathname !== "/webhook/telegram") return new Response("Not found", { status: 404 });
    if (!env.TELEGRAM_BOT_TOKEN) return Response.json({ error: "TELEGRAM_BOT_TOKEN ausente" }, { status: 503 });
    if (env.TELEGRAM_WEBHOOK_SECRET && request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.TELEGRAM_WEBHOOK_SECRET) return Response.json({ error: "Webhook não autorizado" }, { status: 403 });
    try {
      const result = await handleMessage(env, await request.json());
      return Response.json({ ok: true, status: result });
    } catch (error) {
      console.error(error);
      return Response.json({ error: "Erro ao processar mensagem" }, { status: 500 });
    }
  },
};