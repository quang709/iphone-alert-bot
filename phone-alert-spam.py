import os
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pyicloud_ipd import PyiCloudService

TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app_bot = Application.builder().token(TOKEN).build()
fastapi_app = FastAPI()

# Lệnh /alert <alias>
async def alert_device(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Dùng: /alert <alias>")
        return

    alias = context.args[0].lower()
    email_key = f"ICLOUD_{alias.upper()}_EMAIL"
    pass_key = f"ICLOUD_{alias.upper()}_PASS"

    email = os.getenv(email_key)
    password = os.getenv(pass_key)

    if not email or not password:
        await update.message.reply_text(f"⚠️ Alias '{alias}' chưa được cấu hình.")
        return

    try:
        api = PyiCloudService(email, password)
        devices = api.devices
        if not devices:
            await update.message.reply_text(f"❌ Không tìm thấy thiết bị cho {alias}.")
            return

        first_device = list(devices.values())[0]
        first_device.play_sound()
        await update.message.reply_text(
            f"✅ Đã gửi lệnh phát âm thanh tới {alias} ({first_device['name']})"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {str(e)}")

app_bot.add_handler(CommandHandler("alert", alert_device))

# Webhook handler
@fastapi_app.post(f"/webhook/{TOKEN}")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, app_bot.bot)
    await app_bot.process_update(update)
    return {"status": "ok"}

# Khởi tạo bot khi Render start
@fastapi_app.on_event("startup")
async def startup_event():
    await app_bot.initialize()
    await app_bot.start()
    await app_bot.bot.set_webhook(f"{WEBHOOK_URL}/webhook/{TOKEN}")

@fastapi_app.on_event("shutdown")
async def shutdown_event():
    await app_bot.stop()
    await app_bot.shutdown()
