import asyncio                     # Thư viện chuẩn để chạy tác vụ bất đồng bộ (async/await, create_task, cancel)
import os                          # Đọc biến môi trường (.env) qua os.getenv
import logging                     # Ghi log (debug/info/error) giúp theo dõi trạng thái bot
from dotenv import load_dotenv     # Đọc file .env và nạp biến môi trường
from pyicloud import PyiCloudService                               # SDK không chính thức để gọi iCloud
from pyicloud.exceptions import PyiCloudFailedLoginException       # Exception login iCloud lỗi (sai mk/lock)
from telegram import Update                                        # Kiểu dữ liệu message update của Telegram
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes  # Build app & đăng ký lệnh

# ==== ENV & LOGGER ============================================================
load_dotenv()                      # Đọc .env trong thư mục hiện tại -> nạp vào os.environ
logging.basicConfig(level=logging.INFO)     # Cấu hình log mức INFO (in ra console)
logger = logging.getLogger("tg-icloud-bot") # Tạo logger riêng tên 'tg-icloud-bot'

TG_TOKEN = os.getenv("TG_TOKEN")

ICLOUD_ACCOUNTS = [
    {"email": os.getenv("ICLOUD_EMAIL_1"), "password": os.getenv("ICLOUD_PASSWORD_1")},
    {"email": os.getenv("ICLOUD_EMAIL_2"), "password": os.getenv("ICLOUD_PASSWORD_2")},
    {"email": os.getenv("ICLOUD_EMAIL_3"), "password": os.getenv("ICLOUD_PASSWORD_3")},
]

apis = {}
awaiting_2fa = {}
ring_tasks = {}  # (account_index, device_index) -> asyncio.Task

# ---------- LOGIN ----------
def icloud_login(account_index, force=False):
    if account_index in apis and not force:
        return apis[account_index], "✅ Dùng session cũ."

    try:
        email = ICLOUD_ACCOUNTS[account_index]["email"]
        password = ICLOUD_ACCOUNTS[account_index]["password"]
        api = PyiCloudService(email, password)
        apis[account_index] = api

        if api.requires_2fa:
            awaiting_2fa[account_index] = True
            return api, f"🔐 Tài khoản {account_index+1} yêu cầu 2FA. /2fa {account_index+1} <mã>"

        awaiting_2fa[account_index] = False
        return api, f"✅ Đăng nhập thành công tài khoản {account_index+1}."
    except PyiCloudFailedLoginException as e:
        apis.pop(account_index, None)
        return None, f"❌ Đăng nhập thất bại: {e}"
    except Exception as e:
        apis.pop(account_index, None)
        return None, f"❌ Lỗi đăng nhập: {e}"

# ---------- COMMANDS ----------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Xin chào! Mình là bot phát âm thanh iPhone qua iCloud.\n\n"
        "Các lệnh:\n"
        "/login <số> – đăng nhập iCloud\n"
        "/devices <số> – liệt kê thiết bị\n"
        "/ring <số_tài_khoản> <số_thiết_bị> – phát âm thanh\n"
        "/stop <số_tài_khoản> <số_thiết_bị> – dừng phát âm thanh\n"
        "/2fa <số_tài_khoản> <mã> – nhập mã 2FA\n\n"
        "Ví dụ:\n/login 1\n/devices 1\n/ring 1 2\n/stop 1 2\n/2fa 1 123456"
    )

async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Cú pháp: /login <số_tài_khoản>")
        return
    try:
        account_index = int(context.args[0]) - 1
        if account_index < 0 or account_index >= len(ICLOUD_ACCOUNTS):
            await update.message.reply_text("❗ Số tài khoản không hợp lệ.")
            return
        _, msg = icloud_login(account_index, force=True)
        await update.message.reply_text(msg)
    except ValueError:
        await update.message.reply_text("❗ Tham số phải là số.")

async def cmd_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Cú pháp: /2fa <số_tài_khoản> <mã_6_số>")
        return
    try:
        account_index = int(context.args[0]) - 1
        code = context.args[1].strip()
    except ValueError:
        await update.message.reply_text("❗ Tham số không hợp lệ.")
        return

    acc = apis.get(account_index)
    if not acc:
        await update.message.reply_text("❗ Chưa login. Dùng /login <số> trước.")
        return
    if not awaiting_2fa.get(account_index, False):
        await update.message.reply_text("ℹ️ Account này hiện không yêu cầu 2FA.")
        return

    try:
        acc.validate_2fa_code(code)
        if not acc.is_trusted_session:
            await update.message.reply_text("⚠️ Session chưa trust. Hãy xác nhận trên thiết bị/email rồi /login lại.")
        else:
            awaiting_2fa[account_index] = False
            await update.message.reply_text("✅ Xác thực 2FA thành công. Dùng /devices <số> để xem thiết bị.")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi xác thực 2FA: {e}")

def devget(dev, key, default=None):
    try:
        return dev[key]
    except Exception:
        return default

async def cmd_devices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Cú pháp: /devices <số_tài_khoản>")
        return
    try:
        account_index = int(context.args[0]) - 1
    except ValueError:
        await update.message.reply_text("❗ Tham số không hợp lệ.")
        return

    acc, msg = icloud_login(account_index, force=False)
    if acc is None:
        await update.message.reply_text(msg)
        return
    if awaiting_2fa.get(account_index, False):
        await update.message.reply_text("🔐 Đang chờ 2FA. Gõ: /2fa <số_tài_khoản> <mã>")
        return

    try:
        devices = list(acc.devices.values())
        if not devices:
            await update.message.reply_text("❌ Không tìm thấy thiết bị nào.")
            return

        lines = [f"📱 Danh sách thiết bị cho tài khoản {account_index+1}:"]
        for idx, d in enumerate(devices, 1):
            name = devget(d, "name", "UNKNOWN")
            model = devget(d, "deviceModel", "")
            batt = devget(d, "batteryLevel", None)
            batt_txt = f" – pin {int(batt*100)}%" if isinstance(batt, (int, float)) else ""
            lines.append(f"{idx}. {name} ({model}){batt_txt}")
        lines.append("\nDùng: /ring <số_tài_khoản> <số_thiết_bị> hoặc /stop <số_tài_khoản> <số_thiết_bị>")
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        logger.exception("devices error")
        await update.message.reply_text(f"❌ Lỗi lấy danh sách thiết bị: {e}")

# ---------- RING ----------
async def ring_device(account_index, device_index, target, name):
    """Phát âm thanh liên tục (mỗi 5s) cho đến khi bị hủy"""
    try:
        while True:
            target.play_sound()
            await asyncio.sleep(0.1)  # gửi mỗi 0.1s
    except asyncio.CancelledError:
        logger.info(f"Stopped ringing {name} (account {account_index+1}, device {device_index+1})")

async def cmd_ring(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Cú pháp: /ring <số_tài_khoản> <số_thiết_bị>")
        return

    try:
        account_index = int(context.args[0]) - 1
        idx = int(context.args[1]) - 1
    except ValueError:
        await update.message.reply_text("❗ Tham số không hợp lệ.")
        return

    acc, msg = icloud_login(account_index, force=False)
    if acc is None:
        await update.message.reply_text(msg)
        return
    if awaiting_2fa.get(account_index, False):
        await update.message.reply_text("🔐 Đang chờ 2FA.")
        return

    try:
        devices = list(acc.devices.values())
        if idx < 0 or idx >= len(devices):
            await update.message.reply_text(f"❗ Số ngoài phạm vi (1…{len(devices)}).")
            return

        target = devices[idx]
        name = devget(target, "name", "UNKNOWN")

        # nếu đã có task trước đó thì cancel
        key = (account_index, idx)
        if key in ring_tasks:
            ring_tasks[key].cancel()

        task = asyncio.create_task(ring_device(account_index, idx, target, name))
        ring_tasks[key] = task

        await update.message.reply_text(f"🔔 Bắt đầu phát âm thanh: {name} (account {account_index+1})")
    except Exception as e:
        logger.exception("ring error")
        await update.message.reply_text(f"❌ Lỗi phát âm thanh: {e}")

# ---------- STOP ----------
async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Cú pháp: /stop <số_tài_khoản> <số_thiết_bị>")
        return

    try:
        account_index = int(context.args[0]) - 1
        idx = int(context.args[1]) - 1
    except ValueError:
        await update.message.reply_text("❗ Tham số không hợp lệ.")
        return

    key = (account_index, idx)
    if key in ring_tasks:
        ring_tasks[key].cancel()
        del ring_tasks[key]
        await update.message.reply_text(f"🛑 Đã dừng phát âm thanh cho thiết bị {idx+1} (account {account_index+1})")
    else:
        await update.message.reply_text("❗ Không có tác vụ nào đang chạy cho thiết bị này.")

# ---------- MAIN ----------
def main():
    app = ApplicationBuilder().token(TG_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("login", cmd_login))
    app.add_handler(CommandHandler("2fa", cmd_2fa))
    app.add_handler(CommandHandler("devices", cmd_devices))
    app.add_handler(CommandHandler("ring", cmd_ring))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()



