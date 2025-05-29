import json
import logging
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

import asyncpg
import aioredis
import os
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
REDIS_URL = os.getenv('REDIS_URL')
DASHBOARD_URL = 'https://yourbot.onrender.com'

async def init_db():
    return await asyncpg.create_pool(DATABASE_URL)

async def load_faqs(pool, business_id):
    async with pool.acquire() as conn:
        return await conn.fetch('SELECT question, answer FROM FAQs WHERE business_id = $1', business_id)

async def load_branding(pool, business_id):
    async with pool.acquire() as conn:
        branding = await conn.fetchrow('SELECT bot_name, logo_url, response_template FROM Businesses WHERE business_id = $1', business_id)
        return branding or {'bot_name': 'Bot', 'logo_url': None, 'response_template': '[Answer]'}

async def save_message(pool, business_id, message_text, is_answered):
    async with pool.acquire() as conn:
        await conn.execute(
            'INSERT INTO Messages (business_id, message_text, is_answered, created_at) VALUES ($1, $2, $3, $4)',
            business_id, message_text, is_answered, datetime.utcnow()
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    business_id = str(update.effective_chat.id)
    pool = context.bot_data['db_pool']
    
    branding = await load_branding(pool, business_id)
    welcome_message = f'Добро пожаловать в {branding["bot_name"]}! 😊 Задайте вопрос, например, "Сколько стоит стрижка?"'
    if branding['logo_url']:
        await update.message.reply_photo(photo=branding['logo_url'], caption=welcome_message)
    else:
        await update.message.reply_text(welcome_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    business_id = str(update.effective_chat.id)
    pool = context.bot_data['db_pool']
    user_message = update.message.text.lower()
    
    faqs = await load_faqs(pool, business_id)
    branding = await load_branding(pool, business_id)
    
    for faq in faqs:
        if re.search(faq['question'].lower(), user_message):
            response = branding['response_template'].replace('[Answer]', faq['answer'])
            await update.message.reply_text(response)
            await save_message(pool, business_id, user_message, True)
            return
    
    async with pool.acquire() as conn:
        owner_chat_id = await conn.fetchval('SELECT owner_chat_id FROM Businesses WHERE business_id = $1', business_id)
    if owner_chat_id:
        keyboard = [[InlineKeyboardButton("Ответить", callback_data=f'reply_{business_id}_{update.message.from_user.id}_{update.message.message_id}')]]
        await context.bot.send_message(
            chat_id=owner_chat_id,
            text=f'Новый вопрос от {update.message.from_user.username or update.message.from_user.first_name}: {user_message}',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    await update.message.reply_text('Ваш вопрос передан владельцу. Мы скоро ответим!')
    await save_message(pool, business_id, user_message, False)

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split('_')
    if data[0] == 'reply':
        business_id, user_id, message_id = data[1], data[2], data[3]
        await query.message.reply_text('Введите ответ для клиента:')
        context.user_data['reply_to'] = {'business_id': business_id, 'user_id': user_id, 'message_id': message_id}
    await query.answer()

async def process_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'reply_to' not in context.user_data:
        return
    reply_data = context.user_data['reply_to']
    await context.bot.send_message(
        chat_id=reply_data['user_id'],
        text=update.message.text,
        reply_to_message_id=reply_data['message_id']
    )
    await update.message.reply_text('Ответ отправлен клиенту!')
    del context.user_data['reply_to']

async def add_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    business_id = str(update.effective_chat.id)
    pool = context.bot_data['db_pool']
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text('Использование: /addfaq <вопрос> | <ответ>')
        return
    
    args = ' '.join(context.args).split('|')
    if len(args) != 2:
        await update.message.reply_text('Формат: /addfaq <вопрос> | <ответ>')
        return
    
    question, answer = args[0].strip(), args[1].strip()
    async with pool.acquire() as conn:
        await conn.execute(
            'INSERT INTO FAQs (business_id, question, answer) VALUES ($1, $2, $3)',
            business_id, question, answer
        )
    await update.message.reply_text(f'Добавлен FAQ: {question} -> {answer}')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f'Update {update} caused error {context.error}')
    if update and update.message:
        await update.message.reply_text('Произошла ошибка. Попробуйте снова.')

async def main():
    db_pool = await init_db()
    redis = await aioredis.from_url(REDIS_URL)
    
    application = Application.builder().token('YOUR_BOT_TOKEN').build()
    application.bot_data['db_pool'] = db_pool
    application.bot_data['redis'] = redis
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('addfaq', add_faq))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, process_reply))
    application.add_handler(CallbackQueryHandler(handle_reply, pattern='^reply_'))
    
    await application.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())