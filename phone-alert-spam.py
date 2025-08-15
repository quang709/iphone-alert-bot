import os
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pyicloud import PyiCloudService

TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Tự load tất cả iCloud accounts từ env
ICLOUD_ACCOUNTS = {}
for key, value in os.environ.items():
    if key.startswith("ICLOUD_") and key.endswith("_EMAIL"):
        alias = key[len("ICLOUD_"):-len("_EMAIL")].lower()
        email = value
        password_key = f"ICLOUD_{alias.upper()}_PASS"
        password = os.getenv(password_key)
        if password:
            ICLOUD_ACCOUNTS[alias] = (email, password)

app_bot = Application.builder().token(TOKEN).build()

async def alert_device(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("❌ Dùng: /alert <alias>")
        return
    
    alias = context.args[0].lower()
    if alias not in ICLOUD_ACCOUNTS:
        await update.message.reply_text(f"❌ Alias '{alias}' không tồn tại.")
        return

    email, pwd = ICLOUD_ACCOUNTS[alias]
    try:
        icloud = PyiCloudService(email, pwd)
        device = icloud.find_my_iphone.devices[0]  # chọn thiết bị đầu tiên
        device.play_sound()
        await update.message.reply_text(f"✅ Đã phát âm thanh trên thiết bị '{alias}'.")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")

app_bot.add_handler(CommandHandler("alert", alert_device))

fastapi_app = FastAPI()

@fastapi_app.post(f"/webhook/{TOKEN}")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, app_bot.bot)
    await app_bot.process_update(update)
    return {"status": "ok"}

@fastapi_app.on_event("startup")
async def startup_event():
    await app_bot.bot.set_webhook(f"{WEBHOOK_URL}/webhook/{TOKEN}")
