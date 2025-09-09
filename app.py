from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_session import Session
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

# Настройка серверной сессии
app.config["SESSION_TYPE"] = "filesystem"  # хранение на сервере
app.config["SESSION_FILE_DIR"] = "./.flask_session"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True
Session(app)

# Загружаем вопросы
with open('questions.json', encoding='utf-8') as f:
    questions = json.load(f)

USERS_FILE = 'users.json'

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_users(users_data):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users_data, f, indent=2, ensure_ascii=False)

def send_telegram(message: str):
    token = os.environ.get('TG_TOKEN')
    chat_id = os.environ.get('TG_CHAT_ID')
    if not token or not chat_id:
        print("Ошибка: токен или chat_id не указан")
        return None

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    # Разбиваем сообщение на части до 4000 символов
    max_len = 4000
    responses = []
    for i in range(0, len(message), max_len):
        part = message[i:i+max_len]
        try:
            res = requests.get(url, params={'chat_id': chat_id, 'text': part})  # без parse_mode
            response = res.json()
            responses.append(response)
            print("Telegram API ответ:", response)
        except Exception as e:
            print("Ошибка при отправке в Telegram:", e)
            responses.append({"ok": False, "error": str(e)})
    return responses

@app.route("/", methods=["GET", "POST"])
def index():
    try:
        if request.method == "POST":
            nickname = request.form.get("nickname", "").strip()
            goal = request.form.get("goal", "").strip()
            time_commit = request.form.get("time_commit", "").strip()

            if not nickname or not goal or not time_commit:
                return render_template("nickname.html", error="Заполните все поля")

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

            session['nickname'] = nickname
            session['goal'] = goal
            session['time_commit'] = time_commit
            session['answers'] = []
            session['current'] = 0
            session['start_time'] = datetime.now().isoformat()
            session['questions'] = random.sample(questions, len(questions))
            session['tab_events'] = []

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
            q_data = questions_list[current]
            q_text = q_data['question'] if isinstance(q_data, dict) else str(q_data)
            session['answers'].append({
                'question': q_text,
                'answer': answer_text if answer_text else "—",
                'time': answer_time
            })
            session['current'] = current + 1
            session['start_time'] = datetime.now().isoformat()
            return redirect(url_for('question'))

        q_data = questions_list[current]
        question_text = q_data['question'] if isinstance(q_data, dict) else str(q_data)
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

@app.route("/log_tab_event", methods=["POST"])
def log_tab_event():
    try:
        data = request.get_json(force=True)
        event_type = data.get("event")
        timestamp = datetime.now().isoformat()
        if 'tab_events' not in session:
            session['tab_events'] = []
        session['tab_events'].append({'event': event_type, 'time': timestamp})
        session.modified = True
        return jsonify({"status": "ok"})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/result")
def result():
    try:
        nickname = session.get('nickname')
        answers = session.get('answers', [])
        goal = session.get('goal')
        time_commit = session.get('time_commit')

        total_time = sum(a['time'] for a in answers)
        avg_time = total_time / len(answers) if answers else 0

        msg_header = (
            f"🎯 Новый участник прошёл тест 🎯\n\n"
            f"Ник: {nickname}\n"
            f"Цель: {goal}\n"
            f"Время на посту: {time_commit}\n"
            f"Общее время: {total_time:.1f} сек\n"
            f"Среднее время на вопрос: {avg_time:.1f} сек\n\n"
        )

        msg_answers = ""
        for i, ans in enumerate(answers):
            q_text = ans['question']
            a_text = ans['answer']
            a_time = ans['time']
            msg_answers += (
                f"--------------------\n"
                f"{i+1}. {q_text}\n"
                f"Ответ: {a_text} (Время: {a_time:.1f} сек)\n"
            )

        # Добавляем события вкладки
        tab_events = session.get('tab_events', [])
        if tab_events:
            blur_times = [e['time'] for e in tab_events if e['event'] == 'blur']
            focus_times = [e['time'] for e in tab_events if e['event'] == 'focus']

            def format_times(times):
                return "\n".join([f"- {datetime.fromisoformat(t).strftime('%d.%m.%Y %H:%M:%S')}" for t in times])

            msg_answers += "\n📌 События вкладки:\n"
            if blur_times:
                msg_answers += "⚠️ Свернуты:\n" + format_times(blur_times) + "\n"
            if focus_times:
                msg_answers += "✅ Вернулся:\n" + format_times(focus_times) + "\n"

        # Отправляем в Telegram
        full_msg = msg_header + msg_answers
        max_len = 4000
        token = os.environ.get('TG_TOKEN')
        chat_id = os.environ.get('TG_CHAT_ID')
        if token and chat_id:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            for i in range(0, len(full_msg), max_len):
                part = full_msg[i:i+max_len]
                requests.get(url, params={'chat_id': chat_id, 'text': part})

        # Сохраняем время прохождения
        users_data = load_users()
        users_data[nickname] = {'last_time': datetime.now().isoformat()}
        save_users(users_data)

        session.clear()
        return render_template("result.html", nickname=nickname)
    except Exception as e:
        traceback.print_exc()
        return f"<h2>Ошибка: {e}</h2>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
