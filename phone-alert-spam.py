import asyncio
import logging
import time
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Bật log để debug
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

import os
TOKEN = os.getenv("TOKEN")

async def timiphone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text(
            "❌ Sai cú pháp!\nDùng: /timiphone <Model> <IMEI> <Liên hệ>"
        )
        return
    
    model = context.args[0]
    imei = context.args[1]
    lienhe = " ".join(context.args[2:])

    message = (
        "🚨 *CẢNH BÁO TÌM iPHONE* 🚨\n\n"
        f"📱 *Model:* {model}\n"
        f"🔍 *IMEI:* `{imei}`\n"
        f"📞 *Liên hệ:* {lienhe}\n"
    )

    # Gửi liên tục trong 3 phút, mỗi lần cách 10 giây
    start_time = time.monotonic()
    while time.monotonic() - start_time < 180:
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        await asyncio.sleep(10)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("timiphone", timiphone))
    app.run_polling()
