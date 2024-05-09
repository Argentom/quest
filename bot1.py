from telebot import *
from config import *
from database import *
from gpt import *

bot = telebot.TeleBot(token)
# функция для кнопок
def menu_keyboard(options):
    buttons = (types.KeyboardButton(text=option) for option in options)
    keyboard =types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True,
                                         one_time_keyboard=True)
    keyboard.add(*buttons)
    return keyboard


# команда для начала
@bot.message_handler(commands=['start'])
def start(message):
    create_table_answer()
    create_db()
    create_table()
    user_id = message.from_user.id
    reg(user_id)
    bot.send_message(user_id, hello_text, reply_markup=menu_keyboard(['/tts', '/help','/stt','/chatGPT']))


# для тех, кто ничего не понял, постарался объяснить
@bot.message_handler(commands=['help'])
def help_func(message):
    user_id = message.from_user.id
    bot.send_message(user_id, text=help_text, reply_markup=menu_keyboard(['/tts','/stt','/chatGPT']))


# вот и text-to-speech
@bot.message_handler(commands=['tts'])
def tts_handler(message):
    user_id = message.from_user.id
    bot.send_message(user_id, 'Отправь текст, который я буду озвучивать')
    bot.register_next_step_handler(message, tts)


def tts(message):

    user_id = message.from_user.id
    i=count_all_tokens(user_id)
    print(i)
    text = message.text

    # Проверка, что сообщение действительно текстовое
    if message.content_type != 'text':
        bot.send_message(user_id, 'Отправь текстовое сообщение')
        bot.register_next_step_handler(message, tts)
        return

    text_symbol = is_tts_symbol_limit(message, text)
    if text_symbol is None:
        bot.send_message(user_id, 'что-то пошло не так')
        bot.register_next_step_handler(message, tts)
        return
    blocks=0
    tokens=0
    # Записываем сообщение и кол-во символов в БД
    insert_row(user_id, text, text_symbol,blocks,tokens)

    # Получаем статус и содержимое ответа от SpeechKit
    status, content = text_to_speech(text)

    # Если статус True - отправляем голосовое сообщение, иначе - сообщение об ошибке
    if status:
        bot.send_voice(user_id, content, reply_markup=menu_keyboard(['/help', '/tts','/stt','/chatGPT']))
    else:
        bot.send_message(user_id, content)


@bot.message_handler(commands=['debug'])
def debug_file(message):
    try:
        with open('errors.txt', 'rb') as f:
            file = f.read()
        bot.send_document(message.chat.id, file)
    except FileNotFoundError:
        bot.send_message(message.chat.id, text='ошибок нет')

@bot.message_handler(commands=['chatGPT'])
def gpt(message):
    bot.send_message(message.chat.id,'Отправь голосовое или текстовое сообщение.',reply_markup=menu_keyboard(['Выйти']))
    bot.register_next_step_handler(message,stt_or_tts)


def stt_or_tts(message):
    user_id=message.from_user.id
    if not message.text and not message.voice:
        bot.send_message(message.chat.id, 'Отправь текстовое сообщение или голосовое')
        bot.register_next_step_handler(message, stt_or_tts)
        return




    elif message.voice:
        file_id = message.voice.file_id  # получаем id голосового сообщения
        file_info = bot.get_file(file_id)  # получаем информацию о голосовом сообщении
        file = bot.download_file(file_info.file_path)  # скачиваем голосовое сообщение


        # Получаем статус и содержимое ответа от SpeechKit
        status, text = speech_to_text(file)
        if status:
            gpt_answer(' ',user_id)

            result=ask_gpt(text,user_id)
            dialogue = [{'role': 'system', 'text': result}]
            tokens=is_token_limit(message,dialogue)
            if tokens is None:
                bot.send_message(user_id, 'что-то пошло не так')
                bot.register_next_step_handler(message, stt_or_tts)
                return
            tts_symbol = 0
            blocks = 0
            gpt_answer(result,user_id)
            insert_row(user_id, text, tts_symbol, blocks, tokens)
            status, content = text_to_speech(result)
            bot.send_voice(message.chat.id, content)
            bot.send_message(message.chat.id, 'Можно задать следующий вопрос,продолжить решение или выйти',
                             reply_markup=menu_keyboard(['Выйти', 'Продолжи']))
            bot.register_next_step_handler(message, stt_or_tts)
        else:
            bot.send_message(message.chat.id, text)
            bot.send_message(message.chat.id, 'Можно задать следующий вопрос или выйти',
                             reply_markup=menu_keyboard(['Выйти']))
            bot.register_next_step_handler(message, stt_or_tts)
    elif message.text:
        if message.text.lower()=='продолжи':
            if gpt_answer_content(user_id)==' ':
                bot.send_message(message.chat.id, 'Вы еще не делали запрос')
                bot.register_next_step_handler(message,stt_or_tts)
                return
            text=message.text+' '+gpt_answer_content(user_id)
            result=ask_gpt(text,user_id)
            dialogue = [{'role': 'system', 'text': result}]
            tokens = is_token_limit(message, dialogue)
            if tokens is None:
                bot.send_message(user_id, 'что-то пошло не так')
                bot.register_next_step_handler(message, stt_or_tts)
                return
            tts_symbol = 0
            blocks = 0
            gpt_answer(gpt_answer_content(user_id)+result, user_id)
            insert_row(user_id, text, tts_symbol, blocks, tokens)
            bot.send_message(message.chat.id, result)
            bot.send_message(message.chat.id, 'Можно задать следующий вопрос,продолжить решение или выйти',
                             reply_markup=menu_keyboard(['Выйти', 'Продолжи']))
            bot.register_next_step_handler(message, stt_or_tts)
            return

        if message.text.lower() == 'выйти':
            clear_base(user_id)
            bot.send_message(message.chat.id, 'Вы вышли из чата с GPT',
                             reply_markup=menu_keyboard(['/help', '/tts', '/stt','/chatGPT']))
            return
        gpt_answer(' ',user_id)
        text=message.text
        result=ask_gpt(text,user_id)
        dialogue = [{'role': 'system', 'text': result}]
        tokens=is_token_limit(message,dialogue)
        if tokens is None:
            bot.send_message(user_id, 'что-то пошло не так')
            bot.register_next_step_handler(message, stt_or_tts)
            return
        tts_symbol = 0
        blocks = 0
        gpt_answer(result,user_id)
        insert_row(user_id, text, tts_symbol, blocks, tokens)
        bot.send_message(message.chat.id,result)
        bot.send_message(message.chat.id, 'Можно задать следующий вопрос,продолжить решение или выйти',
                         reply_markup=menu_keyboard(['Выйти', 'Продолжи']))
        bot.register_next_step_handler(message,stt_or_tts)
        return






@bot.message_handler(commands=['stt'])
def stt_handler(message):
    user_id = message.from_user.id
    bot.send_message(user_id, 'Отправь голосовое сообщение, чтобы я его распознал!')
    bot.register_next_step_handler(message, stt)


# Переводим голосовое сообщение в текст после команды stt
def stt(message):
    user_id = message.from_user.id

    # Проверка, что сообщение действительно голосовое
    if not message.voice:
        return

    # Считаем аудиоблоки и проверяем сумму потраченных аудиоблоков
    blocks = is_stt_block_limit(message, message.voice.duration)
    if not blocks:
        return

    file_id = message.voice.file_id  # получаем id голосового сообщения
    file_info = bot.get_file(file_id)  # получаем информацию о голосовом сообщении
    file = bot.download_file(file_info.file_path)  # скачиваем голосовое сообщение

    # Получаем статус и содержимое ответа от SpeechKit
    status, text = speech_to_text(file)  # преобразовываем голосовое сообщение в текст
    tts_symbol = 0
    tokens = 0
    # Если статус True - отправляем текст сообщения и сохраняем в БД, иначе - сообщение об ошибке
    if status:
        # Записываем сообщение и кол-во аудиоблоков в БД
        insert_row(user_id, text, tts_symbol, blocks,tokens)
        bot.send_message(user_id, text, reply_to_message_id=message.id,reply_markup=menu_keyboard(['/help', '/tts','/stt','/chatGPT']))
    else:
        bot.send_message(user_id, text, reply_markup=menu_keyboard(['/help', '/tts','/stt','/chatGPT']))




@bot.message_handler(content_types=['text','voice','audio','video','sticker'])
def text_handler(message):
    user_id = message.from_user.id
    bot.send_message(user_id, 'к сожалению, я реагирую только на команды, '
                              'вот кнопки с доступными командами: ',
                     reply_markup=menu_keyboard(['/tts', '/help', '/stt','/chatGPT']))


bot.infinity_polling(timeout=60, long_polling_timeout=6)
