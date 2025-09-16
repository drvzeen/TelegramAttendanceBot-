import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from docx import Document
import math
import os

# ================== НАСТРОЙКИ ==================
TOKEN = os.getenv("TOKEN")  # Telegram токен
UNIVERSITY_CENTER = (41.351376, 69.221844)  # центр университета
ALLOWED_RADIUS = 100  # метров
# ===============================================

# USERS: username -> {"name": ФИО, "role": "student"/"leader"}
USERS = {
    # Пример: "drvzeen": {"name": "Шухрат Шоха", "role": "student"},
}

attendance = {}  # словарь посещаемости по датам

logging.basicConfig(level=logging.INFO)

# ================== ФУНКЦИИ ==================
def distance(coord1, coord2):
    R = 6371000
    lat1, lon1 = map(math.radians, coord1)
    lat2, lon2 = map(math.radians, coord2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def is_leader(username):
    return username in USERS and USERS[username]["role"] == "leader"

def is_student(username):
    return username in USERS and USERS[username]["role"] == "student"

# ================== КОМАНДЫ ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    await update.message.reply_text(
        f"Привет, {user.first_name}!\n"
        f"Отправь '+' если ты на паре, '-' если нет.\n"
        f"Можно отправить геолокацию для подтверждения.\n"
        f"Используй /help для списка команд."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.from_user.username
    text = "Команды:\n/start\n/help\n+ / -\nГеолокация"
    if is_leader(username):
        text += "\n/report\n/add_student username ФИО role\n/list_students"
    elif is_student(username):
        text += "\n/status"
    await update.message.reply_text(text)

async def mark_attendance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.from_user.username
    text = update.message.text.strip()
    if not is_student(username):
        return await update.message.reply_text("Ты не в списке студентов.")
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in attendance:
        attendance[today] = {}
    if text in ["+", "-"]:
        attendance[today][USERS[username]["name"]] = text
        await update.message.reply_text(f"Отметка сохранена: {text}")
    else:
        await update.message.reply_text("Используй только '+' или '-'")

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.from_user.username
    loc = update.message.location
    if not is_student(username):
        return await update.message.reply_text("Ты не в списке студентов.")
    user_coords = (loc.latitude, loc.longitude)
    dist = distance(user_coords, UNIVERSITY_CENTER)
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in attendance:
        attendance[today] = {}
    if dist <= ALLOWED_RADIUS:
        attendance[today][USERS[username]["name"]] = "+"
        await update.message.reply_text("Ты в университете ✅")
    else:
        attendance[today][USERS[username]["name"]] = "-"
        await update.message.reply_text("Ты не в университете ❌")

# ================== ЛИДЕРСКИЕ КОМАНДЫ ==================
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.from_user.username
    if not is_leader(username):
        return await update.message.reply_text("Только лидер может запрашивать отчёт.")
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in attendance:
        return await update.message.reply_text("Сегодня ещё нет данных.")
    doc = Document()
    doc.add_heading(f"Отчёт за {today}", 0)
    for user in USERS.values():
        if user["role"] == "student":
            status = attendance[today].get(user["name"], "-")
            doc.add_paragraph(f"{user['name']}: {status}")
    filename = f"attendance_{today}.docx"
    doc.save(filename)
    await update.message.reply_document(open(filename, "rb"))
    os.remove(filename)

async def add_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.from_user.username
    if not is_leader(username):
        return await update.message.reply_text("Только лидер может добавлять пользователей.")
    try:
        args = context.args
        if len(args) < 3:
            return await update.message.reply_text("Используй: /add_student username ФИО role")
        new_username = args[0]
        name = args[1]
        role = args[2]
        if role not in ["student", "leader"]:
            return await update.message.reply_text("Роль должна быть student или leader")
        USERS[new_username] = {"name": name, "role": role}
        await update.message.reply_text(f"{name} ({role}) добавлен!")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

async def list_students(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.from_user.username
    if not is_leader(username):
        return await update.message.reply_text("Только лидер может видеть список.")
    text = "Список пользователей:\n"
    for u, data in USERS.items():
        text += f"{data['name']} ({data['role']})\n"
    await update.message.reply_text(text)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.from_user.username
    if not is_student(username):
        return await update.message.reply_text("Ты не в списке студентов.")
    today = datetime.now().strftime("%Y-%m-%d")
    name = USERS[username]["name"]
    status_today = attendance.get(today, {}).get(name, "Не отмечен")
    await update.message.reply_text(f"{name}, твой статус сегодня: {status_today}")

# ================== MAIN ==================
def main():
    app = Application.builder().token(TOKEN).build()

    # команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("add_student", add_student))
    app.add_handler(CommandHandler("list_students", list_students))
    app.add_handler(CommandHandler("status", status))

    # сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, mark_attendance))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))

    app.run_polling()

if __name__ == "__main__":
    main()
