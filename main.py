from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date
from zoneinfo import ZoneInfo
import asyncio
import logging
import httpx
import re
import os

from models import SessionLocal, Expense, ProcessedMessage

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
TELEGRAM_GROUP_NAME = os.getenv("TELEGRAM_GROUP_NAME", "Fluxo de Caixa - Marta")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
MAX_AMOUNT = 99999999.99
LOCAL_TIMEZONE = ZoneInfo("America/Sao_Paulo")

PATTERN_ONLY_VALUE = re.compile(r"^[-+]?\s*(\d+(?:[.,]\d{1,2})?)$")
PATTERN_DATE_VALUE = re.compile(
    r"^(?:(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+([-+]?\s*\d+(?:[.,]\d{1,2})?)|([-+]?\s*\d+(?:[.,]\d{1,2})?)\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?))$"
)
PATTERN_CURRENCY_VALUE = re.compile(
    r"R\$\s*([-+]?\s*\d+(?:[.,]\d{1,2})?)", re.IGNORECASE
)
PATTERN_NATURAL_VALUE = re.compile(
    r"\b(?:deu|total(?:izou)?|gastei|custou|ficou|saiu|valor(?:\s+foi)?)"
    r"\s*:?\s*(?:R\$\s*)?([-+]?\s*\d+(?:[.,]\d{1,2})?)",
    re.IGNORECASE,
)
PATTERN_ANY_DATE = re.compile(
    r"(?<!\d)(\d{1,2}/\d{1,2}(?:/\d{2,4})?)(?!\d)"
)
PATTERN_CONSULT_DATE = re.compile(
    r"^/consultar\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)$",
    re.IGNORECASE,
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def parse_date(date_str: str) -> date:
    parts = date_str.split("/")
    day, month = int(parts[0]), int(parts[1])
    current_year = datetime.now(LOCAL_TIMEZONE).year
    year = int(parts[2]) if len(parts) == 3 else current_year
    if year < 100:
        year += 2000
    return date(year, month, day)

async def send_telegram_reply(chat_id: int, text: str):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            raise RuntimeError(result.get("description", "Telegram API error"))

async def handle_telegram_message(
    chat_id: int, message_id: str, sender: str, text: str, db: Session
):
    if message_id and db.query(ProcessedMessage).filter(
        ProcessedMessage.message_id == message_id
    ).first():
        return {"status": "duplicate_ignored"}

    text = text.strip()

    if text.lower() in {"/ajuda", "/help"}:
        reply = (
            "📚 *Comandos do bot:*\n"
            "• `/total` - total do mês atual\n"
            "• `/mês` - resumo detalhado do mês atual\n"
            "• `/entradas` - lista todos os registros\n"
            "• `/consultar DD/MM/AAAA` - consulta um dia específico\n"
            "• `/pago` - apaga todos os registros\n\n"
            "💰 *Registrar despesa:*\n"
            "• `25,90`\n"
            "• `25,90 15/03/2026`\n"
            "• `15/03/2026 25,90`\n"
            "• Também aceito mensagens como `Almoço R$ 25,90`."
        )
        await send_telegram_reply(chat_id, reply)
        return {"status": "help_sent"}

    if text.lower() == "/pago":
        db.query(Expense).delete(synchronize_session=False)
        db.query(ProcessedMessage).delete(synchronize_session=False)
        db.commit()
        await send_telegram_reply(chat_id, "✅ Registros apagados. Banco zerado.")
        return {"status": "cleared"}

    consult_match = PATTERN_CONSULT_DATE.match(text)
    if consult_match:
        try:
            consult_date = parse_date(consult_match.group(1))
        except ValueError:
            await send_telegram_reply(chat_id, "❌ Data inválida. Use DD/MM/AAAA.")
            return {"status": "invalid_date"}

        entries = db.query(Expense).filter(
            Expense.expense_date == consult_date
        ).order_by(Expense.id).all()
        day_total = sum((entry.amount for entry in entries), 0)
        if entries:
            details = "\n".join(
                f"• R$ {entry.amount:.2f} - {entry.sender}" for entry in entries
            )
            reply = (
                f"📅 *{consult_date.strftime('%d/%m/%Y')}*\n"
                f"{details}\n"
                f"📊 *Total do dia:* R$ {day_total:.2f}"
            )
        else:
            reply = f"📅 Nenhum registro em {consult_date.strftime('%d/%m/%Y')}."
        await send_telegram_reply(chat_id, reply)
        return {"status": "consulted"}

    if text.lower() == "/entradas":
        entries = db.query(Expense).order_by(
            Expense.expense_date, Expense.id
        ).all()
        if entries:
            details = "\n".join(
                f"• {entry.expense_date.strftime('%d/%m/%Y')}: R$ {entry.amount:.2f}"
                for entry in entries
            )
            total = sum((entry.amount for entry in entries), 0)
            reply = f"📋 *Entradas registradas:*\n{details}\n\n📊 *Total:* R$ {total:.2f}"
        else:
            reply = "📋 Nenhuma entrada registrada."
        await send_telegram_reply(chat_id, reply)
        return {"status": "entries_sent", "count": len(entries)}

    if text.lower() in {"/total", "!total", "/mês", "/mes"}:
        today = datetime.now(LOCAL_TIMEZONE).date()
        month_entries = db.query(Expense).filter(
            func.extract('year', Expense.expense_date) == today.year,
            func.extract('month', Expense.expense_date) == today.month
        ).order_by(Expense.expense_date, Expense.id).all()
        month_total = sum((entry.amount for entry in month_entries), 0)
        if text.lower() in {"/mês", "/mes"}:
            details = "\n".join(
                f"• {entry.expense_date.strftime('%d/%m')}: R$ {entry.amount:.2f}"
                for entry in month_entries
            ) or "Nenhum registro."
            reply = (
                f"🗓️ *Resumo de {today.strftime('%m/%Y')}:*\n{details}\n"
                f"📊 *Total do mês:* R$ {month_total:.2f}"
            )
        else:
            reply = f"📊 *Total acumulado em {today.strftime('%m/%Y')}:* R$ {month_total:.2f}"
        await send_telegram_reply(chat_id, reply)
        return {"status": "summary_sent"}

    listed_expenses = []
    for line in text.splitlines():
        currency_matches = list(PATTERN_CURRENCY_VALUE.finditer(line))
        natural_matches = [] if currency_matches else list(
            PATTERN_NATURAL_VALUE.finditer(line)
        )
        value_matches = currency_matches or natural_matches
        if not value_matches:
            continue

        line_date = datetime.now(LOCAL_TIMEZONE).date()
        for date_text in reversed(PATTERN_ANY_DATE.findall(line)):
            try:
                line_date = parse_date(date_text)
                break
            except ValueError:
                continue

        for value_match in value_matches:
            line_amount = float(
                value_match.group(1).replace(",", ".").replace(" ", "")
            )
            if abs(line_amount) > MAX_AMOUNT:
                return {"status": "invalid_amount"}
            listed_expenses.append((line_amount, line_date))

    if listed_expenses:
        if message_id:
            db.add(ProcessedMessage(message_id=message_id))
        for line_amount, line_date in listed_expenses:
            db.add(
                Expense(
                    sender=sender,
                    amount=line_amount,
                    expense_date=line_date,
                )
            )
        try:
            db.commit()
        except Exception:
            db.rollback()
            return {"status": "database_error"}

        message_total = sum(line_amount for line_amount, _ in listed_expenses)
        reply = (
            f"✅ *{len(listed_expenses)} valores registrados*\n"
            f"📊 *Soma da mensagem:* R$ {message_total:.2f}"
        )
        await send_telegram_reply(chat_id, reply)
        return {"status": "recorded", "count": len(listed_expenses)}

    target_date = None
    amount = None

    m_val = PATTERN_ONLY_VALUE.match(text)
    if m_val:
        amount = float(text.replace(",", ".").replace(" ", ""))
        target_date = datetime.now(LOCAL_TIMEZONE).date()

    if amount is None:
        m_date = PATTERN_DATE_VALUE.match(text)
        if m_date:
            d1, v1, v2, d2 = m_date.groups()
            date_part = d1 or d2
            val_part = v1 or v2
            amount = float(val_part.replace(",", ".").replace(" ", ""))
            try:
                target_date = parse_date(date_part)
            except ValueError:
                return {"status": "invalid_date"}

    if amount is not None and abs(amount) > MAX_AMOUNT:
        return {"status": "invalid_amount"}

    if amount is not None and target_date is not None:
        if message_id:
            db.add(ProcessedMessage(message_id=message_id))
        expense = Expense(sender=sender, amount=amount, expense_date=target_date)
        db.add(expense)
        try:
            db.commit()
        except Exception:
            db.rollback()
            return {"status": "database_error"}

        month_total = db.query(func.sum(Expense.amount)).filter(
            func.extract('year', Expense.expense_date) == target_date.year,
            func.extract('month', Expense.expense_date) == target_date.month
        ).scalar() or 0.0

        formatted_date = target_date.strftime("%d/%m")
        reply = (
            f"✅ *R$ {amount:.2f}* registrado ({formatted_date}) por {sender}\n"
            f"📊 *Total do mês ({target_date.strftime('%m/%Y')}):* R$ {month_total:.2f}"
        )
        await send_telegram_reply(chat_id, reply)
        return {"status": "recorded"}

    return {"status": "no_action"}


async def telegram_polling():
    if not TELEGRAM_BOT_TOKEN:
        return

    offset = 0
    async with httpx.AsyncClient(timeout=35) as client:
        while True:
            try:
                response = await client.get(
                    f"{TELEGRAM_API_URL}/getUpdates",
                    params={"offset": offset, "timeout": 25, "allowed_updates": '["message"]'},
                )
                response.raise_for_status()
                updates = response.json().get("result", [])
                for update in updates:
                    offset = update["update_id"] + 1
                    message = update.get("message", {})
                    chat = message.get("chat", {})
                    chat_id = chat.get("id")
                    chat_title = chat.get("title", "")
                    configured_chat = str(chat_id) == TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else False
                    if chat.get("type") not in {"group", "supergroup"}:
                        continue
                    normalized_title = " ".join(chat_title.casefold().split())
                    configured_title = " ".join(TELEGRAM_GROUP_NAME.casefold().split())
                    if normalized_title != configured_title and not configured_chat:
                        continue
                    text = message.get("text", "")
                    if not text:
                        continue
                    sender_data = message.get("from", {})
                    sender = (
                        sender_data.get("first_name", "Alguém")
                        + (f" {sender_data['last_name']}" if sender_data.get("last_name") else "")
                    )
                    db = SessionLocal()
                    try:
                        await handle_telegram_message(
                            chat_id,
                            str(update["update_id"]),
                            sender,
                            text,
                            db,
                        )
                    finally:
                        db.close()
            except Exception:
                logger.exception("Erro no polling do Telegram")
                await asyncio.sleep(5)


@app.on_event("startup")
async def start_telegram_polling():
    if TELEGRAM_BOT_TOKEN:
        app.state.telegram_task = asyncio.create_task(telegram_polling())


@app.on_event("shutdown")
async def stop_telegram_polling():
    task = getattr(app.state, "telegram_task", None)
    if task:
        task.cancel()