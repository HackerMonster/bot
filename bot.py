from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

TOKEN = "7948105899:AAHsPWxKPd7X9g4oEgzzkxwDQV_I47rTh00"

async def reply_sss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("SSS")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.ALL, reply_sss))
    app.run_polling()

if __name__ == "__main__":
    main()
