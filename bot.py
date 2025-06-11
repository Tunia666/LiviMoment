import logging
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from current_lesson_task import LessonManager

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация менеджера уроков
lesson_manager = LessonManager("ktp.json")

# Словарь для хранения решений пользователей
user_solutions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    keyboard = [
        [InlineKeyboardButton("📚 Текущее занятие", callback_data='current_lesson')],
        [InlineKeyboardButton("📝 Получить задание", callback_data='get_task')],
        [InlineKeyboardButton("📋 Отправить решение", callback_data='submit_solution')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 Привет! Я бот-помощник для обучения Python.\n\n"
        "Я могу:\n"
        "• Показать информацию о текущем занятии\n"
        "• Сгенерировать задание\n"
        "• Принять ваше решение на проверку\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'current_lesson':
        await show_current_lesson(update, context)
    elif query.data == 'get_task':
        await send_task(update, context)
    elif query.data == 'submit_solution':
        await request_solution(update, context)

async def show_current_lesson(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать информацию о текущем занятии"""
    query = update.callback_query
    current_lesson = lesson_manager.get_current_lesson()
    
    if current_lesson:
        message = (
            f"📚 Текущее занятие:\n\n"
            f"📅 Дата: {current_lesson['date']}\n"
            f"⏰ Время: {current_lesson['start_time']} - {current_lesson['end_time']}\n"
            f"📝 Тема: {current_lesson['topic']}\n"
            f"📋 Задание: {current_lesson['assignment']}"
        )
    else:
        message = "На данный момент нет активных занятий"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=message, reply_markup=reply_markup)

async def send_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправить задание пользователю"""
    query = update.callback_query
    current_lesson = lesson_manager.get_current_lesson()
    
    if current_lesson:
        task = lesson_manager.generate_task_with_llm(current_lesson)
        
        message = (
            f"📝 Задание: {task['title']}\n\n"
            f"📋 Описание:\n{task['description']}\n\n"
            f"📌 Требования:\n" + "\n".join(f"• {req}" for req in task['requirements']) + "\n\n"
            f"📚 Примеры:\n"
        )
        
        for example in task['examples']:
            message += f"Входные данные: {example['input']}\n"
            message += f"Выходные данные: {example['output']}\n\n"
        
        message += "📝 Шаги выполнения:\n" + "\n".join(f"{i+1}. {step}" for i, step in enumerate(task['steps']))
        
        # Сохраняем задание для пользователя
        user_id = query.from_user.id
        user_solutions[user_id] = {
            'task': task,
            'solution': None,
            'status': 'pending'
        }
    else:
        message = "На данный момент нет активных занятий"
    
    keyboard = [
        [InlineKeyboardButton("📤 Отправить решение", callback_data='submit_solution')],
        [InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=message, reply_markup=reply_markup)

async def request_solution(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запросить решение у пользователя"""
    query = update.callback_query
    user_id = query.from_user.id
    
    if user_id not in user_solutions:
        message = "Сначала получите задание!"
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')]]
    else:
        message = (
            "Отправьте ваше решение в виде текста или файла Python.\n\n"
            "Формат решения:\n"
            "1. Код должен быть рабочим\n"
            "2. Добавьте комментарии к коду\n"
            "3. Укажите, как запустить программу"
        )
        keyboard = [[InlineKeyboardButton("◀️ Отмена", callback_data='back_to_menu')]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=message, reply_markup=reply_markup)

async def handle_solution(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик отправленных решений"""
    user_id = update.effective_user.id
    
    if user_id not in user_solutions:
        await update.message.reply_text(
            "Сначала получите задание!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')]])
        )
        return
    
    # Сохраняем решение
    if update.message.document:
        file = await context.bot.get_file(update.message.document.file_id)
        solution = await file.download_as_bytearray()
        user_solutions[user_id]['solution'] = solution.decode('utf-8')
    else:
        user_solutions[user_id]['solution'] = update.message.text
    
    user_solutions[user_id]['status'] = 'submitted'
    
    # Отправляем подтверждение
    keyboard = [
        [InlineKeyboardButton("📝 Получить новое задание", callback_data='get_task')],
        [InlineKeyboardButton("◀️ В главное меню", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "✅ Ваше решение принято!\n\n"
        "Преподаватель проверит его и даст обратную связь.",
        reply_markup=reply_markup
    )

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Вернуться в главное меню"""
    query = update.callback_query
    keyboard = [
        [InlineKeyboardButton("📚 Текущее занятие", callback_data='current_lesson')],
        [InlineKeyboardButton("📝 Получить задание", callback_data='get_task')],
        [InlineKeyboardButton("📋 Отправить решение", callback_data='submit_solution')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Выберите действие:",
        reply_markup=reply_markup
    )

def main() -> None:
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token("YOUR_BOT_TOKEN").build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL, handle_solution))
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 