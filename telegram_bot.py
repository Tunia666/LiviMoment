import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from current_lesson_task import LessonManager
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from langchain_gigachat import GigaChat
from langchain_core.messages import SystemMessage, HumanMessage
import subprocess
import tempfile
from telegram.error import NetworkError, TelegramError

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация менеджера уроков
lesson_manager = LessonManager("ktp.json")

# Словари для хранения данных
user_solutions = {}
student_registrations = {}  # {user_id: {lesson_date: registration_data}}
user_stats = {}  # user_id: {'total': 0, 'success': 0}

# Пример теста (можно заменить на генерацию или загрузку из файла)
test_questions = [
    {"q": "Что такое список в Python?", "a": ["Изменяемая коллекция", "Неизменяемая коллекция", "Функция", "Модуль"], "correct": 0},
    {"q": "Как создать кортеж?", "a": ["[]", "{}", "()", "<>"], "correct": 2},
    {"q": "Как получить длину списка my_list?", "a": ["my_list.len()", "len(my_list)", "length(my_list)", "my_list.length()"], "correct": 1},
    {"q": "Как добавить элемент в список?", "a": ["add()", "append()", "insert()", "push()"], "correct": 1},
    {"q": "Как получить срез списка с 2 по 4 элемент?", "a": ["my_list[2:5]", "my_list[1:4]", "my_list[2:4]", "my_list[1:5]"], "correct": 0}
]

user_tests = {}  # user_id: {"current": int, "answers": list}

def save_registrations():
    """Сохранить регистрации в файл"""
    with open('registrations.json', 'w', encoding='utf-8') as f:
        json.dump(student_registrations, f, ensure_ascii=False, indent=2)

def load_registrations():
    """Загрузить регистрации из файла"""
    global student_registrations
    try:
        with open('registrations.json', 'r', encoding='utf-8') as f:
            student_registrations = json.load(f)
    except FileNotFoundError:
        student_registrations = {}

# Загружаем существующие регистрации при запуске
load_registrations()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    keyboard = [
        [InlineKeyboardButton("✅ Отметка на занятии", callback_data='register_attendance')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👋 Привет! Я бот-помощник для обучения Python.\n\n"
        "Для начала работы отметьтесь на занятии, нажав кнопку ниже.\n"
        "После отметки вы получите доступ к заданию и сможете отправить решение.",
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
    elif query.data == 'register_attendance':
        await register_attendance(update, context)
    elif query.data == 'start_test':
        await start_test(update, context)
    elif query.data == 'back_to_menu':
        await back_to_menu(update, context)

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

    # AI-проверка решения
    task = user_solutions[user_id]['task']
    solution_code = user_solutions[user_id]['solution']
    check_results = []
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as tmp:
        tmp.write(solution_code)
        tmp_path = tmp.name
    for example in task.get('examples', []):
        input_data = example['input']
        expected_output = example['output']
        try:
            proc = subprocess.run(
                ['python3', tmp_path],
                input=input_data.encode('utf-8'),
                capture_output=True,
                timeout=5
            )
            actual_output = proc.stdout.decode('utf-8').strip()
            error_output = proc.stderr.decode('utf-8').strip()
            success = (actual_output == expected_output)
        except Exception as e:
            actual_output = str(e)
            error_output = ''
            success = False
        check_results.append({
            'input': input_data,
            'expected': expected_output,
            'actual': actual_output,
            'error': error_output,
            'success': success
        })
    os.unlink(tmp_path)

    # === СТАТИСТИКА ===
    if user_id not in user_stats:
        user_stats[user_id] = {'total': 0, 'success': 0}
    user_stats[user_id]['total'] += 1
    if all(res['success'] for res in check_results):
        user_stats[user_id]['success'] += 1

    # === ОЦЕНКА ===
    total = user_stats[user_id]['total']
    success = user_stats[user_id]['success']
    percent = round(success / total * 100) if total else 0
    if percent >= 90:
        grade = 5
    elif percent >= 75:
        grade = 4
    elif percent >= 50:
        grade = 3
    elif percent >= 30:
        grade = 2
    else:
        grade = 1

    # Формируем отчет
    report = "\n\nРезультаты автоматической проверки:\n"
    for i, res in enumerate(check_results, 1):
        report += f"\nТест {i}:\n"
        report += f"Входные данные: {res['input']}\n"
        report += f"Ожидалось: {res['expected']}\n"
        report += f"Получено: {res['actual']}\n"
        if res['error']:
            report += f"Ошибка выполнения: {res['error']}\n"
        report += f"Результат: {'✅ Успех' if res['success'] else '❌ Ошибка'}\n"
    report += f"\n📊 Ваша текущая оценка: {grade}/5 (успехов: {success} из {total}, {percent}%)"
    
    # Отправляем отчет пользователю
    keyboard = [
        [InlineKeyboardButton("📝 Получить новое задание", callback_data='get_task')],
        [InlineKeyboardButton("◀️ В главное меню", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "✅ Ваше решение принято!" + report,
        reply_markup=reply_markup
    )

async def register_attendance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Регистрация присутствия на занятии с учетом опоздания и выдачей доп. задания через TaskGenerator"""
    query = update.callback_query
    user_id = str(query.from_user.id)
    current_lesson = lesson_manager.get_current_lesson()
    
    if not current_lesson:
        message = "На данный момент нет активных занятий"
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='back_to_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=message, reply_markup=reply_markup)
        return
    
    # Время начала занятия
    lesson_start = datetime.strptime(f"{current_lesson['date']} {current_lesson['start_time']}", "%Y-%m-%d %H:%M")
    now = datetime.now()
    late_minutes = (now - lesson_start).total_seconds() / 60
    late_threshold = 10  # минут
    is_late = late_minutes > late_threshold
    
    # Проверяем, не зарегистрирован ли уже студент на это занятие
    if user_id in student_registrations and current_lesson['date'] in student_registrations[user_id]:
        reg = student_registrations[user_id][current_lesson['date']]
        message = (
            "Вы уже зарегистрированы на это занятие!\n\n"
            f"Дата регистрации: {reg['registration_time']}\n"
            f"Тема: {reg['topic']}\n"
            f"Задание: {reg['assignment']}"
        )
        if reg.get('extra_assignment'):
            message += f"\n\n⚠️ Дополнительное задание за опоздание:\n{reg['extra_assignment']}"
        # Показываем кнопки для работы с заданием
        keyboard = [
            [InlineKeyboardButton("📚 Текущее занятие", callback_data='current_lesson')],
            [InlineKeyboardButton("📝 Получить задание", callback_data='get_task')],
            [InlineKeyboardButton("📋 Отправить решение", callback_data='submit_solution')],
            [InlineKeyboardButton("◀️ В главное меню", callback_data='back_to_menu')]
        ]
    else:
        # Создаем запись о регистрации
        registration_time = now.strftime("%Y-%m-%d %H:%M:%S")
        extra_assignment = None
        if is_late:
            # Генерируем доп. задание через TaskGenerator
            extra_lesson = dict(current_lesson)  # копия
            extra_lesson['topic'] = f"Дополнительное/усложнённое задание по теме: {current_lesson['topic']}"
            extra_assignment_obj = lesson_manager.task_generator.generate_task_for_lesson(extra_lesson)
            extra_assignment = (
                f"{extra_assignment_obj['title']}\n"
                f"{extra_assignment_obj['description']}\n"
                f"Требования:\n" + "\n".join(f"- {req}" for req in extra_assignment_obj['requirements']) + "\n"
                f"Примеры:\n" + "\n".join(
                    f"Входные данные: {ex['input']}\nВыходные данные: {ex['output']}" for ex in extra_assignment_obj['examples']
                ) + "\n"
                f"Шаги выполнения:\n" + "\n".join(f"{i+1}. {step}" for i, step in enumerate(extra_assignment_obj['steps']))
            )
        if user_id not in student_registrations:
            student_registrations[user_id] = {}
        
        student_registrations[user_id][current_lesson['date']] = {
            'registration_time': registration_time,
            'topic': current_lesson['topic'],
            'assignment': current_lesson['assignment'],
            'student_name': f"{query.from_user.first_name} {query.from_user.last_name or ''}",
            'extra_assignment': extra_assignment
        }
        
        # Сохраняем регистрации
        save_registrations()
        
        message = (
            "✅ Вы успешно зарегистрированы на занятие!\n\n"
            f"📅 Дата занятия: {current_lesson['date']}\n"
            f"⏰ Время регистрации: {registration_time}\n"
            f"📚 Тема: {current_lesson['topic']}\n"
            f"📝 Задание: {current_lesson['assignment']}"
        )
        if extra_assignment:
            message += f"\n\n⚠️ Вы опоздали на занятие!\nДополнительное задание:\n{extra_assignment}"
        else:
            message += "\n\nТеперь вы можете получить задание и отправить решение."
        # Показываем кнопки для работы с заданием
        keyboard = [
            [InlineKeyboardButton("📚 Текущее занятие", callback_data='current_lesson')],
            [InlineKeyboardButton("📝 Получить задание", callback_data='get_task')],
            [InlineKeyboardButton("📋 Отправить решение", callback_data='submit_solution')],
            [InlineKeyboardButton("◀️ В главное меню", callback_data='back_to_menu')]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=message, reply_markup=reply_markup)

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Вернуться в главное меню"""
    query = update.callback_query
    user_id = str(query.from_user.id)
    current_lesson = lesson_manager.get_current_lesson()
    is_registered = (current_lesson and user_id in student_registrations and current_lesson['date'] in student_registrations[user_id])
    # Проверяем, пора ли тестировать
    show_test = False
    if is_registered and current_lesson:
        lesson_end = datetime.strptime(f"{current_lesson['date']} {current_lesson['end_time']}", "%Y-%m-%d %H:%M")
        now = datetime.now()
        if (lesson_end - now).total_seconds() <= 600:  # 10 минут
            show_test = True
    if is_registered:
        keyboard = [
            [InlineKeyboardButton("📚 Текущее занятие", callback_data='current_lesson')],
            [InlineKeyboardButton("📝 Получить задание", callback_data='get_task')],
            [InlineKeyboardButton("📋 Отправить решение", callback_data='submit_solution')],
        ]
        if show_test:
            keyboard.append([InlineKeyboardButton("🧪 Пройти тест", callback_data='start_test')])
        keyboard.append([InlineKeyboardButton("✅ Отметка на занятии", callback_data='register_attendance')])
        message = "Выберите действие:"
    else:
        keyboard = [[InlineKeyboardButton("✅ Отметка на занятии", callback_data='register_attendance')]]
        message = "Для начала работы отметьтесь на занятии."
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=message, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    help_text = (
        "🤖 *Доступные команды:*\n\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n\n"
        "Порядок работы с ботом:\n"
        "1. Отметьтесь на занятии\n"
        "2. Получите информацию о текущем занятии\n"
        "3. Получите задание\n"
        "4. Отправьте решение"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def start_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = str(query.from_user.id)
    current_lesson = lesson_manager.get_current_lesson()
    if not current_lesson:
        await query.edit_message_text("Нет активного занятия для теста.")
        return
    # Генерируем тест через TaskGenerator
    test_obj = lesson_manager.task_generator.generate_test_for_lesson(current_lesson, num_questions=5)
    print('GigaChat response:', test_obj.get("questions", []))
    questions = test_obj.get("questions", [])
    if not questions or len(questions) < 1:
        await query.edit_message_text("Не удалось сгенерировать тест по теме занятия. Попробуйте позже или обратитесь к преподавателю.")
        return
    user_tests[user_id] = {"current": 0, "answers": [], "questions": questions}
    await send_test_question(query, user_id)

def get_test_keyboard(q):
    return InlineKeyboardMarkup([[InlineKeyboardButton(a, callback_data=f"test_answer_{i}")] for i, a in enumerate(q['a'])])

async def send_test_question(query, user_id):
    idx = user_tests[user_id]["current"]
    q = user_tests[user_id]["questions"][idx]
    await query.edit_message_text(
        text=f"Вопрос {idx+1}/5:\n{q['q']}",
        reply_markup=get_test_keyboard(q)
    )

async def test_answer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = str(query.from_user.id)
    data = query.data
    if not data.startswith("test_answer_"):
        return
    answer_idx = int(data.split("_")[-1])
    test_state = user_tests.get(user_id)
    if not test_state:
        await query.answer("Тест не начат!", show_alert=True)
        return
    test_state["answers"].append(answer_idx)
    test_state["current"] += 1
    if test_state["current"] < len(test_state["questions"]):
        await send_test_question(query, user_id)
    else:
        # Завершение теста
        correct = sum(1 for i, q in enumerate(test_state["questions"]) if test_state["answers"][i] == q["correct"])
        await query.edit_message_text(
            text=f"Тест завершён!\nВаш результат: {correct}/{len(test_state['questions'])} правильных ответов.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В главное меню", callback_data='back_to_menu')]])
        )
        del user_tests[user_id]

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    stats = user_stats.get(user_id, {'total': 0, 'success': 0})
    total = stats['total']
    success = stats['success']
    percent = round(success / total * 100) if total else 0
    if percent >= 90:
        grade = 5
    elif percent >= 75:
        grade = 4
    elif percent >= 50:
        grade = 3
    elif percent >= 30:
        grade = 2
    else:
        grade = 1
    await update.message.reply_text(
        f'📊 Ваша статистика:\n'
        f'Всего попыток: {total}\n'
        f'Успешных решений: {success}\n'
        f'Процент успеха: {percent}%\n'
        f'Ваша оценка: {grade}/5'
    )

async def error_handler(update, context):
    try:
        raise context.error
    except NetworkError as e:
        logger.error(f"Network error: {e}")
    except TelegramError as e:
        logger.error(f"Telegram error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

def main() -> None:
    """Запуск бота"""
    # Используем токен напрямую, так как он уже известен
    token = "7526612637:AAFjBbtgpxvgjBDdOMFT8h492Tf_BgDQdj8"
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(test_answer_handler, pattern=r'^test_answer_'))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT | filters.Document.ALL, handle_solution))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 