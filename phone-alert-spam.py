import os
import pickle
import traceback
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pyicloud_ipd import PyiCloudService

TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

app_bot = Application.builder().token(TOKEN).build()
fastapi_app = FastAPI()

pending_logins = {}

def get_session_path(alias):
    return f"{alias}.session"

def load_icloud_session(alias, email, password):
    session_path = get_session_path(alias)
    if os.path.exists(session_path):
        with open(session_path, "rb") as f:
            api = pickle.load(f)
        return api
    return PyiCloudService(email, password)

def save_icloud_session(alias, api):
    with open(get_session_path(alias), "wb") as f:
        pickle.dump(api, f)

# /alert <alias>
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
        api = load_icloud_session(alias, email, password)
        print(f"[DEBUG] Đang đăng nhập iCloud cho {alias} - email: {email}")

        if api.requires_2fa:
            pending_logins[alias] = api
            print(f"[DEBUG] {alias} yêu cầu 2FA.")
            await update.message.reply_text("🔑 Nhập mã 2FA bằng lệnh: /code <mã>")
            return

        devices = api.devices
        if not devices:
            print(f"[DEBUG] Không tìm thấy thiết bị nào cho {alias}.")
            await update.message.reply_text(f"❌ Không tìm thấy thiết bị cho {alias}.")
            return

        first_device = list(devices.values())[0]
        first_device.play_sound()
        save_icloud_session(alias, api)
        await update.message.reply_text(
            f"✅ Đã gửi lệnh phát âm thanh tới {alias} ({first_device['name']})"
        )
    except Exception as e:
        print(f"[ERROR] Lỗi khi chạy /alert cho {alias}: {repr(e)}")
        traceback.print_exc()
        await update.message.reply_text(f"❌ Lỗi: {str(e)}")

# /code <otp>
async def enter_2fa_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1:
        await update.message.reply_text("❌ Dùng: /code <mã>")
        return

    code = context.args[0]
    for alias, api in pending_logins.items():
        try:
            print(f"[DEBUG] Nhận mã OTP {code} cho {alias}")
            if api.validate_2fa_code(code):
                save_icloud_session(alias, api)
                print(f"[DEBUG] Xác thực 2FA thành công cho {alias}")
                await update.message.reply_text(f"✅ Xác thực 2FA cho {alias} thành công.")
                del pending_logins[alias]
                return
            else:
                print(f"[ERROR] Mã OTP không hợp lệ cho {alias}")
                await update.message.reply_text("❌ Mã OTP không hợp lệ.")
                return
        except Exception as e:
            print(f"[ERROR] Lỗi khi xác thực OTP: {repr(e)}")
            traceback.print_exc()
            await update.message.reply_text(f"❌ Lỗi: {str(e)}")
            return

    await update.message.reply_text("⚠️ Không có phiên đăng nhập nào đang chờ OTP.")

app_bot.add_handler(CommandHandler("alert", alert_device))
app_bot.add_handler(CommandHandler("code", enter_2fa_code))

@fastapi_app.post(f"/webhook/{TOKEN}")
async def webhook_handler(request: Request):
    data = await request.json()
    update = Update.de_json(data, app_bot.bot)
    await app_bot.process_update(update)
    return {"status": "ok"}

@fastapi_app.on_event("startup")
async def startup_event():
    await app_bot.initialize()
    await app_bot.start()
    await app_bot.bot.set_webhook(f"{WEBHOOK_URL}/webhook/{TOKEN}")

@fastapi_app.on_event("shutdown")
async def shutdown_event():
    await app_bot.stop()
    await app_bot.shutdown()
