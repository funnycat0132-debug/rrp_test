from flask import Flask, render_template, request, session, redirect, url_for
import json
from datetime import datetime
import os
import traceback
import requests
import random
import html
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback_secret")

# Файл с вопросами
with open('questions.json', encoding='utf-8') as f:
    questions = json.load(f)

# Файл для отслеживания времени прохождения пользователей
USERS_FILE = 'users.json'

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users(users_data):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users_data, f, indent=2, ensure_ascii=False)

# Функция отправки сообщений в Telegram
def send_telegram(message: str):
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
        if request.method == "POST":
            nickname = request.form.get("nickname", "").strip()
            goal = request.form.get("goal", "").strip()
            time_commit = request.form.get("time_commit", "").strip()
            
            if not nickname or not goal or not time_commit:
                return render_template("nickname.html", error="Заполните все поля")

            # Проверяем повторное прохождение
            users_data = load_users()
            last_time_str = users_data.get(nickname, {}).get('last_time')
            if last_time_str:
                last_time = datetime.fromisoformat(last_time_str)
                delta = datetime.now() - last_time
                if delta.total_seconds() < 48*3600:
                    remaining = 48*3600 - delta.total_seconds()
                    hours = int(remaining // 3600)
                    minutes = int((remaining % 3600) // 60)
                    seconds = int(remaining % 60)
                    return render_template(
                        "nickname.html", 
                        error=f"Повторно пройти тест можно через {hours} ч {minutes} м {seconds} с"
                    )

            # Инициализация сессии
            session['nickname'] = nickname
            session['goal'] = goal
            session['time_commit'] = time_commit
            session['answers'] = []
            session['current'] = 0
            session['start_time'] = datetime.now().isoformat()
            session['questions'] = random.sample(questions, len(questions))
            
            return redirect(url_for('question'))

        return render_template("nickname.html")
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
            answer_text = request.form.get("answer", "").strip()
            start_time = datetime.fromisoformat(session.get('start_time'))
            answer_time = (datetime.now() - start_time).total_seconds()
            session['answers'].append({'answer': answer_text if answer_text else "—", 'time': answer_time})
            session['current'] = current + 1
            session['start_time'] = datetime.now().isoformat()
            return redirect(url_for('question'))

        question_data = questions_list[current]
        question_text = question_data['question'] if isinstance(question_data, dict) else str(question_data)
        return render_template(
            "question.html",
            question=question_text,
            question_number=current + 1,
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
        questions_list = session.get('questions', questions)
        goal = session.get('goal')
        time_commit = session.get('time_commit')

        total_time = sum(a['time'] for a in answers)
        avg_time = total_time / len(answers) if answers else 0

        # Формируем заголовок сообщения
        msg_header = (
            f"<b>🎯 Новый участник прошёл тест 🎯</b>\n\n"
            f"<b>Ник:</b> {html.escape(nickname)}\n"
            f"<b>Цель:</b> {html.escape(goal)}\n"
            f"<b>Время на посту:</b> {html.escape(time_commit)}\n"
            f"<b>Общее время:</b> {total_time:.1f} сек\n"
            f"<b>Среднее время на вопрос:</b> {avg_time:.1f} сек\n\n"
        )

        # Формируем блок с вопросами и ответами
        msg_answers = ""
        for i, ans in enumerate(answers):
            q = questions_list[i]
            q_text = q['question'] if isinstance(q, dict) else str(q)
            a_text = ans['answer']
            a_time = ans['time']
            msg_answers += (
                f"--------------------\n"
                f"<b>{i+1}. {html.escape(q_text)}</b>\n"
                f"Ответ: {html.escape(a_text)} (Время: {a_time:.1f} сек)\n"
            )

        # Разбиваем сообщение на части по 4000 символов
        full_msg = msg_header + msg_answers
        max_len = 4000
        for i in range(0, len(full_msg), max_len):
            send_telegram(full_msg[i:i+max_len])

        # Сохраняем время прохождения пользователя
        users_data = load_users()
        users_data[nickname] = {'last_time': datetime.now().isoformat()}
        save_users(users_data)

        # Очистка сессии
        session.clear()
        return render_template("result.html", nickname=nickname)
    except Exception as e:
        traceback.print_exc()
        return f"<h2>Ошибка: {e}</h2>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
