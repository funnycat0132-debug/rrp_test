from flask import Flask, render_template, request, session, redirect, url_for
import json
from datetime import datetime, timedelta
import os
import traceback
import requests
import random
from dotenv import load_dotenv
import html

# Загружаем .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback_secret")

# Загружаем вопросы
with open('questions.json', encoding='utf-8') as f:
    questions = json.load(f)

USERS_FILE = "users.json"

# Функции для работы с users.json
def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(data):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Функция отправки сообщений в Telegram
def send_telegram(message):
    token = os.environ.get('TG_TOKEN')
    chat_id = os.environ.get('TG_CHAT_ID')
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML'
    }
    try:
        res = requests.get(url, params=params)
        response = res.json()
        print("Telegram API ответ:", response)
        if not response.get("ok"):
            print("Ошибка Telegram:", response)
        return response
    except Exception as e:
        print("Ошибка при отправке в Telegram:", e)
        return None

@app.route("/", methods=["GET", "POST"])
def index():
    try:
        error_msg = None
        if request.method == "POST":
            nickname = request.form.get("nickname", "").strip()
            goal = request.form.get("goal", "").strip()
            time_commit = request.form.get("time_commit", "").strip()

            if not (nickname and goal and time_commit):
                error_msg = "Заполните все поля"
                return render_template("nickname.html", error=error_msg)

            users_data = load_users()
            last_time_str = users_data.get(nickname, {}).get('last_time')
            if last_time_str:
                last_time = datetime.fromisoformat(last_time_str)
                next_allowed = last_time + timedelta(days=2)
                now = datetime.now()
                if now < next_allowed:
                    remaining = next_allowed - now
                    hours, remainder = divmod(remaining.total_seconds(), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    error_msg = (f"Повторно пройти тест можно через "
                                 f"{int(hours)} ч {int(minutes)} мин {int(seconds)} сек")
                    return render_template("nickname.html", error=error_msg)

            # Сохраняем в сессию
            session['nickname'] = nickname
            session['goal'] = goal
            session['time_commit'] = time_commit
            session['answers'] = []
            session['times'] = []  # время на каждый вопрос
            session['current'] = 0
            session['start_time'] = datetime.now().isoformat()
            session['questions'] = random.sample(questions, len(questions))

            return redirect(url_for('question'))

        return render_template("nickname.html", error=error_msg)
    except Exception as e:
        traceback.print_exc()
        return f"<h2>Ошибка: {e}</h2>"

@app.route("/question", methods=["GET", "POST"])
def question():
    try:
        current = session.get('current', 0)
        questions_list = session.get('questions', questions)
        
        if current >= len(questions_list):
            return redirect(url_for('result'))

        if request.method == "POST":
            answer = request.form.get("answer", "").strip()
            session['answers'].append(answer if answer else "—")
            end_time = datetime.now()
            start_time = datetime.fromisoformat(session.get('question_start', session['start_time']))
            session['times'].append((end_time - start_time).total_seconds())
            session['current'] = current + 1
            return redirect(url_for('question'))

        # Запоминаем время начала вопроса
        session['question_start'] = datetime.now().isoformat()
        question = questions_list[current]
        return render_template(
            "question.html",
            question=question,
            question_number=current + 1,  # визуально с 1
            total=len(questions_list),
            nickname=session.get('nickname')
        )
    except Exception as e:
        traceback.print_exc()
        return f"<h2>Ошибка: {e}</h2>"

@app.route("/result")
def result():
    try:
        nickname = session.get('nickname')
        answers = session.get('answers', [])
        times = session.get('times', [])
        goal = session.get('goal')
        time_commit = session.get('time_commit')
        start_time = datetime.fromisoformat(session.get('start_time'))
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        avg_time = sum(times)/len(times) if times else 0

        # Сохраняем время прохождения
        users_data = load_users()
        users_data[nickname] = {'last_time': datetime.now().isoformat()}
        save_users(users_data)

        # Формируем сообщения для Telegram (разбиваем на блоки по ~4000 символов)
        msg_base = f"<b>Новый участник прошёл тест</b>:\n<b>Ник:</b> {nickname}\n<b>Цель:</b> {goal}\n<b>Время на посту:</b> {time_commit}\n<b>Общее время:</b> {total_time:.1f} сек\n<b>Среднее время на вопрос:</b> {avg_time:.1f} сек\n\n"
        msg = msg_base
        block = ""
        for i, (q, a, t) in enumerate(zip(session.get('questions'), answers, times)):
            block += f"<b>{i+1}. {html.escape(q if isinstance(q, str) else str(q))}</b>\nОтвет: {html.escape(a)}\nВремя: {t:.1f} сек\n\n"
            if len(msg + block) > 3500:  # ограничение на длину
                send_telegram(msg + block)
                block = ""
        if block:
            send_telegram(msg + block)

        # Очистка сессии
        session.clear()
        return render_template("result.html", nickname=nickname)
    except Exception as e:
        traceback.print_exc()
        return f"<h2>Ошибка: {e}</h2>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
