import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from docx import Document
import math
import os

# ============ НАСТРОЙКИ ============
TOKEN = os.getenv("TOKEN")  # токен берем из Render
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # id админа тоже из Render
STUDENTS = {
    "user1": "Шоха",
    "user2": "Али",
    # добавь всех студентов (username: ФИО)
}
UNIVERSITY_CENTER = (41.351376, 69.221844)  # центр университета
ALLOWED_RADIUS = 100  # метров
# ===================================

attendance = {}

logging.basicConfig(level=logging.INFO)

def distance(coord1, coord2):
    R = 6371000
    lat1, lon1 = map(math.radians, coord1)
    lat2, lon2 = map(math.radians, coord2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! Отправь '+' если ты на паре, '-' если нет.\n"
        f"Можно отправить геолокацию для подтверждения."
    )

async def mark_attendance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    username = user.username
    text = update.message.text.strip()

    if username not in STUDENTS:
        return await update.message.reply_text("Ты не в списке студентов.")

    today = datetime.now().strftime("%Y-%m-%d")
    if today not in attendance:
        attendance[today] = {}

    if text in ["+", "-"]:
        attendance[today][STUDENTS[username]] = text
        await update.message.reply_text(f"Отметка сохранена: {text}")
    else:
        await update.message.reply_text("Используй только '+' или '-'")

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    username = user.username
    loc = update.message.location

    if username not in STUDENTS:
        return await update.message.reply_text("Ты не в списке студентов.")

    user_coords = (loc.latitude, loc.longitude)
    dist = distance(user_coords, UNIVERSITY_CENTER)

    today = datetime.now().strftime("%Y-%m-%d")
    if today not in attendance:
        attendance[today] = {}

    if dist <= ALLOWED_RADIUS:
        attendance[today][STUDENTS[username]] = "+"
        await update.message.reply_text("Ты в университете ✅")
    else:
        attendance[today][STUDENTS[username]] = "-"
        await update.message.reply_text("Ты не в университете ❌")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return await update.message.reply_text("Только админ может запрашивать отчёт.")

    today = datetime.now().strftime("%Y-%m-%d")
    if today not in attendance:
        return await update.message.reply_text("Сегодня ещё нет данных.")

    doc = Document()
    doc.add_heading(f"Отчёт за {today}", 0)

    for name in STUDENTS.values():
        status = attendance[today].get(name, "-")
        doc.add_paragraph(f"{name}: {status}")

    filename = f"attendance_{today}.docx"
    doc.save(filename)

    await update.message.reply_document(open(filename, "rb"))
    os.remove(filename)

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mark_attendance))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))

    app.run_polling()

if __name__ == "__main__":
    main()
