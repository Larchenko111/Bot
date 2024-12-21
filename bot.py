import os
import httpx
import sqlite3
from telegram import Update, ReplyKeyboardMarkup, PhotoSize
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ConversationHandler


# Константы состояний разговора
MAIN_MENU, CUSTOM_DESIGN, DESIGN_IDEA, DESIGN_SIZE, DESIGN_SOURCE, RETURN_QUESTIONS, MARKETPLACE, ORDER_NUMBER, PROBLEM, OTHER_PROBLEM, DESIGN_CONNECTION,  GET_VIDEO,  OTHER_QUESTION, OTHER_QUESTION_MESSAGE, GET_PHONE, GET_PHOTO_DESIGN, GET_PHOTO_RETURN = range(1, 18)


# Создание базы данных и таблиц, а также папок для хранения фото и видео
def setup():
    db_path = 'telegram_bot.db'
    os.makedirs('photos', exist_ok=True)
    os.makedirs('videos', exist_ok=True)
    os.makedirs('custom_orders', exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS returns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        order_number TEXT NOT NULL,
        marketplace TEXT NOT NULL,
        problem TEXT NOT NULL,
        photo_path TEXT,
        video_path TEXT,
        phone_number TEXT,
        status TEXT NOT NULL
    )
    ''')

    cursor.execute("PRAGMA table_info(returns)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    if 'photo_path' not in column_names:
        cursor.execute("ALTER TABLE returns ADD COLUMN photo_path TEXT")
    if 'video_path' not in column_names:
        cursor.execute("ALTER TABLE returns ADD COLUMN video_path TEXT")
    if 'phone_number' not in column_names:
        cursor.execute("ALTER TABLE returns ADD COLUMN phone_number TEXT")

    conn.commit()
    conn.close()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS custom_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        look TEXT NOT NULL,
        size TEXT NOT NULL,
        connection TEXT NOT NULL,
        source TEXT NOT NULL,
        status TEXT NOT NULL,
        photo_path TEXT,           
        phone_number TEXT
    )
    ''')

    cursor.execute("PRAGMA table_info(custom_orders)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    if 'photo_path' not in column_names:
        cursor.execute("ALTER TABLE custom_orders ADD COLUMN photo_path TEXT")
    if 'phone_number' not in column_names:
        cursor.execute("ALTER TABLE custom_orders ADD COLUMN phone_number TEXT")

    conn.commit()
    conn.close()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS other_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            phone_number TEXT
        )
        ''')
    conn.commit()
    conn.close()


# Функция для старта
async def start(update: Update, context: CallbackContext) -> int:
    reply_keyboard = [['Создание светильника по своему дизайну', 'Возврат товара', 'Другой вопрос']]
    await update.message.reply_text(
        'Привет! Это чат-бот магазина DiodeNeon. Чем могу помочь?',
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return MAIN_MENU

# Функции для обработки дизайна
async def custom_design(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Есть ли у вас идеи насчёт того, как должен выглядеть светильник?')
    return DESIGN_IDEA

async def design_idea(update: Update, context: CallbackContext) -> int:
    context.user_data['idea'] = update.message.text
    await update.message.reply_text('Если у вас есть фотографии или примеры того, как должен выглядеть светильник. Пожалуйста, пришлите их в чат.')
    return GET_PHOTO_DESIGN

async def get_photo_design(update: Update, context: CallbackContext) -> int:
    if update.message.photo:
        photo: PhotoSize = update.message.photo[-1]  # Берем последнюю (самую большую) фотографию из отправленных
        photo_file_id = photo.file_id

        # Получаем user_id пользователя
        user_id = update.message.from_user.id

        # Сохраняем фотографию на диск
        photo_file = await context.bot.get_file(photo_file_id)
        photo_path = os.path.join('photos', f"{user_id}_{context.user_data.get('order_number', 'custom')}.jpg")
        await photo_file.download_to_drive(photo_path)

        # Сохраняем путь к фотографии в user_data
        context.user_data['photo_path'] = photo_path

        await update.message.reply_text('Фотография принята. Есть ли у вас комментарии по поводу фотографии?')
        return DESIGN_SIZE
    else:
        await update.message.reply_text('Пожалуйста, отправьте фотографию или напишите "нет", если у вас нет фотографии.')
        return GET_PHOTO_DESIGN


async def design_size(update: Update, context: CallbackContext) -> int:
    context.user_data['size'] = update.message.text
    await update.message.reply_text('Светильник должен подключаться в розетку или напрямую к проводу 220 В?')
    return DESIGN_CONNECTION

async def design_connection(update: Update, context: CallbackContext) -> int:
    context.user_data['connection'] = update.message.text
    await update.message.reply_text('Откуда Вы о нас узнали?')
    return DESIGN_SOURCE

async def design_source(update: Update, context: CallbackContext) -> int:
    context.user_data['source'] = update.message.text

    # Получение данных из user_data или установка пустой строки, если значение отсутствует
    idea = context.user_data.get('idea', '')
    size = context.user_data.get('size', '')
    connection = context.user_data.get('connection', '')
    source = context.user_data.get('source', '')

    # Проверка, что поле look не пустое
    if not idea.strip():
        await update.message.reply_text('Пожалуйста, предоставьте идею насчёт светильника.')
        return DESIGN_IDEA

    # Сохранение данных в базу данных
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO custom_orders (user_id, look, size, connection, source, status) VALUES (?, ?, ?, ?, ?, ?)
    ''', (update.message.from_user.id, idea, size, connection, source, 'active'))

    conn.commit()

    # Запрашиваем номер телефона
    await update.message.reply_text('Спасибо! Ваш заказ принят. Пожалуйста, укажите номер телефона, привязанный к Telegram.')
    return GET_PHONE


# Функции для обработки возвратов и вопросов по маркетплейсам
async def return_questions(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('На каком маркетплейсе Вы приобрели вывеску?')
    return MARKETPLACE

async def marketplace(update: Update, context: CallbackContext) -> int:
    context.user_data['marketplace'] = update.message.text
    await update.message.reply_text('Подскажите, пожалуйста, номер Вашего заказа.')
    return ORDER_NUMBER

async def order_number(update: Update, context: CallbackContext) -> int:
    context.user_data['order_number'] = update.message.text
    reply_keyboard = [['Неполный комплект', 'Брак светильника', 'Брак регулятора яркости'], ['Другое']]
    await update.message.reply_text(
        'В чем заключается проблема светильника?',
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return PROBLEM

async def problem(update: Update, context: CallbackContext) -> int:
    if update.message.text == 'Другое':
        await update.message.reply_text('Пожалуйста, введите ваш текст проблемы.')
        return OTHER_PROBLEM
    else:
        context.user_data['problem'] = update.message.text

        # Сохранение данных в базу данных
        conn = sqlite3.connect('telegram_bot.db')
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO returns (user_id, order_number, marketplace, problem, status) VALUES (?, ?, ?, ?, ?)
        ''', (update.message.from_user.id, context.user_data.get('order_number'), context.user_data.get('marketplace'), context.user_data['problem'], 'pending'))  # Используйте context.user_data.get() для безопасного доступа
        conn.commit()  # Коммит изменений в базе данных
        conn.close()

        await update.message.reply_text('Пожалуйста, отправьте фотографию проблемы.')
        return GET_PHOTO_RETURN

async def other_problem(update: Update, context: CallbackContext) -> int:
    context.user_data['problem'] = update.message.text

    # Сохранение данных в базу данных
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO returns (user_id, order_number, marketplace, problem, status) VALUES (?, ?, ?, ?, ?)
    ''', (update.message.from_user.id, context.user_data.get('order_number'), context.user_data.get('marketplace'), context.user_data.get('problem'), 'pending'))
    conn.commit()
    conn.close()

    await update.message.reply_text('Пожалуйста, отправьте фотографию проблемы.')
    return GET_PHOTO_RETURN

async def get_photo_return(update: Update, context: CallbackContext) -> int:
    if update.message.photo:
        photo: PhotoSize = update.message.photo[-1]  # Берем последнюю (самую большую) фотографию из отправленных
        photo_file_id = photo.file_id

        # Получаем user_id пользователя
        user_id = update.message.from_user.id

        # Сохраняем фотографию на диск
        photo_file = await context.bot.get_file(photo_file_id)
        photo_path = os.path.join('photos', f"{user_id}_{context.user_data.get('order_number', 'return')}.jpg")
        await photo_file.download_to_drive(photo_path)

        # Сохраняем путь к фотографии в user_data
        context.user_data['photo_path'] = photo_path

        await update.message.reply_text('Фотография принята. Пожалуйста, отправьте видео проблемы(если его нет, напишите"Нет").')
        return GET_VIDEO
    else:
        await update.message.reply_text('Пожалуйста, отправьте фотографию или напишите "нет", если у вас нет фотографии.')
        return GET_PHOTO_RETURN

async def get_video(update: Update, context: CallbackContext) -> int:
    if update.message.text and update.message.text.lower() == 'нет':
        video_path = None
        context.user_data['video_path'] = None
    else:
        video = update.message.video
        video_file_id = video.file_id

        # Получаем user_id пользователя
        user_id = update.message.from_user.id

        # Сохраняем видео на диск
        video_file = await context.bot.get_file(video_file_id)
        video_path = os.path.join('videos', f"{user_id}_{context.user_data['order_number']}.mp4")
        await video_file.download_to_drive(video_path)

        # Сохраняем file_id видео в user_data для дальнейшей обработки
        context.user_data['video_path'] = video_path

    # Сохранение данных в базу данных
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO returns (user_id, order_number, marketplace, problem, photo_path, video_path, status) 
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (update.message.from_user.id, context.user_data.get('order_number'), context.user_data.get('marketplace'),
          context.user_data['problem'], context.user_data['photo_path'], context.user_data['video_path'], 'pending'))
    conn.commit()
    conn.close()

    await update.message.reply_text('Ваш запрос на возврат зарегистрирован.')
    await update.message.reply_text('Пожалуйста, укажите номер телефона, привязанный к Telegram.')
    return GET_PHONE

async def other_question(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Пожалуйста, напишите ваш вопрос.')
    return OTHER_QUESTION_MESSAGE

async def other_question_message(update: Update, context: CallbackContext) -> int:
    context.user_data['other_question'] = update.message.text
    await update.message.reply_text('Ваш вопрос принят. Пожалуйста, укажите ваш номер телефона, привязанный к Telegram.')
    return GET_PHONE

async def get_phone(update: Update, context: CallbackContext) -> int:
    context.user_data['phone_number'] = update.message.text

    # Обновление записи в базе данных для возврата
    conn = sqlite3.connect('telegram_bot.db')
    cursor = conn.cursor()
    if 'problem' in context.user_data:  # Если это возврат
        cursor.execute('''
        UPDATE returns SET phone_number = ?, photo_path = ?, video_path = ? WHERE user_id = ? AND order_number = ? AND marketplace = ?
        ''', (context.user_data['phone_number'], context.user_data.get('photo_path'), context.user_data.get('video_path'), update.message.from_user.id, context.user_data.get('order_number'), context.user_data.get('marketplace')))
    elif 'other_question' in context.user_data:  # Если это другой вопрос
        cursor.execute('''
        INSERT INTO other_questions (user_id, question, phone_number) VALUES (?, ?, ?)
        ''', (update.message.from_user.id, context.user_data['other_question'], context.user_data['phone_number']))
    else:  # Если это индивидуальный заказ
        cursor.execute('''
        UPDATE custom_orders SET phone_number = ?, photo_path = ? WHERE user_id = ? AND look = ? AND size = ? AND connection = ? AND source = ?
        ''', (context.user_data['phone_number'], context.user_data.get('photo_path'), update.message.from_user.id, context.user_data.get('idea'), context.user_data.get('size'), context.user_data.get('connection'), context.user_data.get('source')))

    conn.commit()
    conn.close()

    await update.message.reply_text('Спасибо! Мы свяжемся с вами в ближайшее время.')
    return ConversationHandler.END



async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Операция отменена.')
    return ConversationHandler.END

async def main_menu(update: Update, context: CallbackContext) -> int:
    user_choice = update.message.text
    if user_choice == 'Создание светильника по своему дизайну':
        return await custom_design(update, context)
    elif user_choice == 'Возврат товара':
        return await return_questions(update, context)
    elif user_choice == 'Другой вопрос':
        return await other_question(update, context)
    else:
        await update.message.reply_text('Пожалуйста, выберите один из вариантов.')
        return MAIN_MENU

async def send_message(chat_id, message):
    async with httpx.AsyncClient() as client:
        url = f'https://api.telegram.org/bot<7359805961:AAGcvR8XSoOXxZ4VT-J59EKjewDPQtEGIx4>/sendMessage'
        payload = {'chat_id': chat_id, 'text': message}
        await client.post(url, json=payload)

def main():
    # Настройка базы данных и папок
    setup()

    # Инициализация Application с вашим токеном
    application = Application.builder().token("7359805961:AAGcvR8XSoOXxZ4VT-J59EKjewDPQtEGIx4").build()

    # Настройка ConversationHandler для различных состояний
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [
                MessageHandler(filters.Regex('^Создание светильника по своему дизайну$'), custom_design),
                MessageHandler(filters.Regex('^Возврат товара$'), return_questions),
                MessageHandler(filters.Regex('^Другой вопрос$'), other_question)
            ],
            CUSTOM_DESIGN: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_design)],
            DESIGN_IDEA: [MessageHandler(filters.TEXT & ~filters.COMMAND, design_idea)],
            DESIGN_SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, design_size)],
            DESIGN_CONNECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, design_connection)],
            DESIGN_SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, design_source)],
            RETURN_QUESTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, return_questions)],
            OTHER_QUESTION: [MessageHandler(filters.TEXT, other_question)],
            OTHER_QUESTION_MESSAGE: [MessageHandler(filters.TEXT, other_question_message)],

            MARKETPLACE: [MessageHandler(filters.TEXT & ~filters.COMMAND, marketplace)],
            ORDER_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_number)],
            PROBLEM: [
                MessageHandler(filters.Regex('^(Неполный комплект|Брак светильника|Брак регулятора яркости|Другое)$'),
                               problem)],
            GET_PHOTO_DESIGN: [MessageHandler(filters.PHOTO, get_photo_design)],
            GET_PHOTO_RETURN: [MessageHandler(filters.PHOTO, get_photo_return)],
            OTHER_PROBLEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, other_problem)],
            GET_VIDEO: [MessageHandler(filters.VIDEO | filters.TEXT & ~filters.COMMAND, get_video)],

            GET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
        },
        fallbacks=[CommandHandler('cancel', cancel),
                   CommandHandler('menu', main_menu)]
    )

    # Добавление ConversationHandler в диспетчер
    application.add_handler(conv_handler)

    # Запуск бота, чтобы он начал прослушивать сообщения
    application.run_polling()

if __name__ == '__main__':
    main()