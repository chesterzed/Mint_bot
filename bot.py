import TOKEN
import telebot
from telebot import types
import qrcode
import sqlite3
import re
from pathlib import Path
import cv2

usr_commands = ['Информация', 'Показать QR код', 'Показать бонусы']
adm_commands = ['Информация', 'Зарегистрировать платёж', 'Поменять статус', 'Список администраторов']
db_users_name = 'db.sqlite'
bot = telebot.TeleBot(TOKEN.token)


@bot.message_handler(commands=['start'])
def start_message(message):
    if auth_check(message):
        bot.send_message(message.chat.id, 'Вы уже зарегестрированы')
        main_menu(message)
        return

    text = "Добро пожаловать. " \
           "Я преставляю магазин MintShop. " \
           "У меня ты можешь получить свой qr код с которым поделишься с друзьями, " \
           "получишь бонусы и сможешь потратить их в нашем магазине по адресу: " \
           "Покупки в нашем магазине можно осуществлять только после совершеннолетия. "

    bot.send_message(message.chat.id, text)
    ask_age(message)


def ask_age(message):
    text = "Тебе есть 18 ?"

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    button1 = types.InlineKeyboardButton("Да, мне есть 18")
    button2 = types.InlineKeyboardButton("Нет, мне нет 18")
    markup.add(button1, button2)

    msg = bot.send_message(message.chat.id, text, reply_markup=markup)
    bot.register_next_step_handler(msg, check_age)


def check_age(message):
    if message.text == "Нет, мне нет 18":
        bot.send_message(message.chat.id, "Тогда заходи, когда вырастешь) \nНажми /start если уже повзрослел")
    elif message.text == "Да, мне есть 18":
        ask_consent(message)


def ask_consent(message):
    text = "Окей. Ты согласен на обработку персональных данных?"

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    button1 = types.KeyboardButton("Согласен")
    markup.add(button1)

    msg = bot.send_message(message.chat.id, text, reply_markup=markup)
    bot.register_next_step_handler(msg, get_contact)


def get_contact(message):
    if message.text == "Согласен":
        text = "Хорошо, тогда отправь нам свои данные"

        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        button1 = types.KeyboardButton("Отправить", request_contact=True)
        markup.add(button1)

        bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.message_handler(content_types=['contact'])
def try_add_contact(message):
    # clear_buttons(message)
    username = message.contact.first_name
    pn = message.contact.phone_number
    chat_id = int(message.chat.id)

    text = 'Хорошо, сейчас зарегестрирую тебя'
    bot.send_message(message.chat.id, text)

    con = bd_connect()
    curs = con.cursor()

    if auth_check(message):  # пользователь уже есть
        text = 'Ты уже зарегистрирован)'
    else:  # регистрация (такого пользователя нет)
        curs.execute(
            f"INSERT INTO users (userName, id, phoneNum, bonus, role) VALUES (?, ?, ?, ?, ?)", (username, chat_id, pn, 0, 'user',))
        con.commit()
        text = 'Регистрация прошла успешно'

    bot.send_message(message.chat.id, text)
    main_menu(message)


@bot.message_handler(commands=['menu'])
def main_menu(message):
    # генерация кнопок (а лучше просто месседж кинуть, будет ахуенно)
    # заглушка
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    if check_usr_or_admin(message):
        text = "Меню администратора Mint shop" \
               "\n/info - для информации что нужно делать" \
               "\n/regpay - отправить и считать QR код для снятия и начисления бонусов"
        for i in range(0, len(adm_commands)):
            button = types.InlineKeyboardButton(adm_commands[i])
            markup.add(button)
    else:
        text = "Меню Mint shop" \
               "\n/info - для информации по QR коду" \
               "\n/showqr - показать твой QR код" \
               "\n/showbonus - показать счётчик бонусов"
        for i in range(0, len(usr_commands)):
            button = types.InlineKeyboardButton(usr_commands[i])
            markup.add(button)
    bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.message_handler(commands=['showqr'])
def show_qr(message):
    chat_id = str(message.chat.id)
    img = qrcode.make(chat_id)

    path = 'qrs/' + chat_id + '.png'
    img.save(path)
    photo = open(path, 'rb')
    bot.send_photo(message.chat.id, photo)

    text = "Вот твой qr код, нажми /info чтобы узнать как он работает"
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=['showbonus'])
def show_bonus(message):
    usr_bonus = bd_select_one_str("bonus", "users", "id", message.chat.id)
    bot.send_message(message.chat.id, re.sub("[(),]", "", usr_bonus))


@bot.message_handler(commands=['info'])
def info(message):
    if check_usr_or_admin(message):
        bot.send_message(message.chat.id, 'Ты админ, '
                                          'чтобы начислить или '
                                          'списать бонусы '
                                          'тебе нужно сделать фотку'
                                          ' в QR посетителя, затем '
                                          'загрузить его мне.'
                                          'Я обработаю фото и скажу '
                                          'кто перед тобой, введи сумму '
                                          'его заказа '
                                          'я начислю бынусы.'
                                          '\nНажми /regpay для регистрации платежа')
    else:
        bot.send_message(message.chat.id, 'Всё максимально просто, приглашаешь друзей и получаешь за них бонусы)')
    main_menu(message)


@bot.message_handler(commands=['regpay'])
def reg_pay(message):
    text = "Сфотографируй QR код 1 и отправь мне"
    msg = bot.send_message(message.chat.id, text)
    bot.register_next_step_handler(msg, check_qr)


def check_qr(message):
    if message.content_type == 'photo':
        usr_chat_id = handle_docs_photo(message)
        if usr_chat_id != 0 and usr_chat_id is not None:
            ask_qr_2(message, usr_chat_id)
        else:
            bot.send_message(message.chat.id, "Упс. что-то пошло не так")
            main_menu(message)
    else:
        main_menu(message)


def ask_qr_2(message, usr_chat_id_1):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.InlineKeyboardButton('Нет друга'))

    text = "Сфотографируй QR код 2 и отправь мне"
    msg = bot.send_message(message.chat.id, text, reply_markup=markup)
    bot.register_next_step_handler(msg, check_qr_2, usr_chat_id_1=usr_chat_id_1)


def check_qr_2(message, usr_chat_id_1):
    if message.text == 'Нет друга':
        enter_sum(message, usr_chat_id_1, 0)
        return

    if message.content_type == 'photo':
        usr_chat_id_2 = handle_docs_photo(message)
        if usr_chat_id_2 != 0 and usr_chat_id_2 is not None:
            enter_sum(message, usr_chat_id_1, usr_chat_id_2)
        else:
            bot.send_message(message.chat.id, "Упс. что-то пошло не так")
            main_menu(message)
    else:
        main_menu(message)


def enter_sum(message, usr_chat_id_1, usr_chat_id_2):
    text = "На какую сумму приобрёл товара ?"
    msg = bot.send_message(message.chat.id, text)
    bot.register_next_step_handler(msg, ask_subtract_bonus, usr_chat_id_1=usr_chat_id_1, usr_chat_id_2=usr_chat_id_2)


def ask_subtract_bonus(message, usr_chat_id_1, usr_chat_id_2):
    # Подключение к базе + апдейт бонусов
    try:
        good_price = int(message.text)
        usr_bonus = bd_select_one_str("bonus", "users", "id", usr_chat_id_1)
        usr_bonus = re.sub("[(),]", "", usr_bonus)

        text = "У пользователя на счету: " + usr_bonus + "\nСколько хотите списать?"
        bot.send_message(message.chat.id, text)
        bot.register_next_step_handler(message, get_new_sum, usr_chat_id_1=usr_chat_id_1, usr_chat_id_2=usr_chat_id_2,
                                       good_price=good_price, usr_bonus=int(usr_bonus))
    except Exception:
        bot.send_message(message.chat.id, "Не могу прочитать число 1")
        main_menu(message)


def get_new_sum(message, usr_chat_id_1, usr_chat_id_2, good_price, usr_bonus):
    try:
        lost_bonus = int(message.text)
        if usr_bonus == 0 or lost_bonus == 0:
            text = "Было потрачено: 0 бонусов.\nСтоимость покупки: " + str(good_price) + "руб."
            bot.send_message(message.chat.id, text)
            add_bonus(message, usr_chat_id_1, usr_chat_id_2, good_price, usr_bonus)
            return

        if usr_bonus < lost_bonus:
            lost_bonus = usr_bonus
        if good_price < lost_bonus:
            lost_bonus = good_price

        good_price -= lost_bonus
        usr_bonus -= lost_bonus

        subtract_bonus(message, usr_chat_id_1, good_price, lost_bonus, usr_bonus)
    except Exception:
        # print(type(message.text))
        bot.send_message(message.chat.id, "Не могу прочитать число 2")
        main_menu(message)


def add_bonus(message, usr_chat_id_1, usr_chat_id_2, good_price, usr_bonus):
    if usr_chat_id_2 == 0:
        bonus_division = 20
    else:
        bonus_division = 10
    bonus = good_price // bonus_division
    bonus += usr_bonus

    bd_update("users", "bonus", bonus, "id", usr_chat_id_1)

    text = "Спасибо за покупку, покупателю начислено: " \
           + str(good_price // bonus_division) + " бонусов.\nТеперь у него: " + str(bonus) + " бонусов."
    bot.send_message(message.chat.id, text)  # Админу

    text = "Спасибо за покупку, вам начислено: " \
           + str(good_price // bonus_division) + " бонусов.\nТеперь у вас: " + str(bonus) + " бонусов."
    bot.send_message(usr_chat_id_1, text)

    if usr_chat_id_1 != usr_chat_id_2 and usr_chat_id_2 != 0:
        bonus_1 = good_price // 20
        b = bd_select_one_str("bonus", "users", "id", usr_chat_id_2)
        b = re.sub("[(),]", "", b)
        bonus_1 += int(b)

        bd_update("users", "bonus", bonus_1, "id", usr_chat_id_2)

        text = "Вам начислено: " + str(good_price // 20) + " бонусов.\nТеперь у вас: " + str(bonus_1) + " бонусов."
        bot.send_message(usr_chat_id_2, text)

    main_menu(message)


def subtract_bonus(message, usr_chat_id, good_price, lost_bonus, new_usr_bonus):
    # для Админа
    text = "Было потрачено: " + str(lost_bonus) + " бонусов.\nСтоимость покупки: " + str(good_price) + "руб."
    bot.send_message(message.chat.id, text)

    # Для пользователя
    bd_update("users", "bonus", new_usr_bonus, "id", usr_chat_id)
    text = "У вас было списано: " + str(lost_bonus) + " бонусов.\nТеперь у вас: " + str(new_usr_bonus) + " бонусов."
    bot.send_message(usr_chat_id, text)

    main_menu(message)


@bot.message_handler(commands=["checkadmins"])
def check_admin_status(message):
    if check_usr_or_admin(message):
        con = bd_connect()
        curs = con.cursor()

        curs.execute("SELECT userName, working FROM users WHERE role = ?", ("admin",))
        records = curs.fetchall()
        text = ""
        for row in records:
            # print(re.sub("[(),']", "", str(row)))
            text += re.sub("[(),']", "", str(row)) + "\n"
        bot.send_message(message.chat.id, text)


@bot.message_handler(commands=["switchstatus"])
def ask_status(message):
    if check_usr_or_admin(message):
        text = "Ты сейчас на работе?"
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        but1 = types.InlineKeyboardButton("На рабочем месте")
        but2 = types.InlineKeyboardButton("На перерыве")
        but3 = types.InlineKeyboardButton("Выходной")
        markup.add(but1, but2, but3)

        msg = bot.send_message(message.chat.id, text, reply_markup=markup)
        bot.register_next_step_handler(msg, switch_status)


def switch_status(message):
    # print(message.text)
    bd_update("users", "working", message.text, "id", message.chat.id)
    main_menu(message)


def handle_docs_photo(message):
    Path(f'files/{message.chat.id}/').mkdir(parents=True, exist_ok=True)
    if message.content_type == 'photo':
        file_info = bot.get_file(
            message.photo[len(message.photo) - 1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        src = f'files/{message.chat.id}/' + \
              file_info.file_path.replace('photos/', '')
        with open(src, 'wb') as new_file:
            new_file.write(downloaded_file)
        # read the QRCODE image
        image = cv2.imread(src)
        # initialize the cv2 QRCode detector
        detector = cv2.QRCodeDetector()
        # detect and decode
        data, vertices_array, binary_qrcode = detector.detectAndDecode(
            image)
        # if there is a QR code
        # print the data
        if vertices_array is not None:
            bot.send_message(message.chat.id, "qr code")
            bot.send_message(message.chat.id, data)
            return data
        else:
            bot.send_message(message.chat.id, 'Упс. Я не вижу здесь QR код')
            # print("There was some error")
            return 0


def clear_buttons(message):
    markup = types.ReplyKeyboardRemove()
    bot.send_message(message.chat.id, "очистка", reply_markup=markup)


def check_usr_or_admin(message):
    usr_role = bd_select_one_str("role", "users", "id", message.chat.id)
    usr_role = re.sub('[(),\n]', '', usr_role)
    # print(usr_role)

    if usr_role != '\'admin\'':
        return False
    else:
        return True


def bd_connect():
    return sqlite3.connect(db_users_name)


def bd_select_one_str(s_what, s_list, s_where, s_what_where):
    curs = bd_connect().cursor()
    curs.execute("SELECT " + s_what + " FROM " + s_list + " WHERE " + s_where + " = ?", (s_what_where,))
    selected = str(curs.fetchone())  # возможно вернуть стринг
    return selected


def bd_update(u_list, u_what, u_set, where, u_what_where):
    con = bd_connect()
    curs = con.cursor()
    curs.execute(f"UPDATE {u_list} SET {u_what} = ? WHERE {where} = ?", (u_set, u_what_where,))
    con.commit()


def auth_check(message):
    usr_id = bd_select_one_str("id", "users", "id", message.chat.id)
    if usr_id != 'None':
        # bot.send_message(message.chat.id, 'Вы уже зарегестрированы')
        return True
    else:
        return False


def ref_check(chat_id):
    ref_id = bd_select_one_str("urRefId", "users", "id", chat_id)
    if ref_id is not None and ref_id != 0:
        return True
    else:
        return False


@bot.message_handler(content_types=['text'])
def menu_request(message):
    if not auth_check(message):
        start_message(message)
        return

    # usr_commands = ['Информация', 'Показать QR код', 'Показать бонусы']
    # adm_commands = ['Информация', 'Зарегистрировать платёж', 'Поменять статус', 'Список администраторов']
    if check_usr_or_admin(message):
        if message.text == 'Информация':
            info(message)
        elif message.text == 'Зарегистрировать платёж':
            reg_pay(message)
        elif message.text == 'Поменять статус':
            ask_status(message)
        elif message.text == 'Список администраторов':
            check_admin_status(message)
        else:
            bot.send_message(message.chat.id, 'Ничего не понял, давай по новой')
            main_menu(message)
    else:
        if message.text == 'Информация':
            info(message)
        elif message.text == 'Показать QR код':
            show_qr(message)
        elif message.text == 'Показать бонусы':
            show_bonus(message)
        else:
            bot.send_message(message.chat.id, 'Ничего не понял, давай по новой')
            main_menu(message)


bot.polling(none_stop=True)
