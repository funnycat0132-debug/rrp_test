from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_session import Session
import json
from datetime import datetime
import os
import traceback
import requests
import random
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback_secret")

# Настройка серверной сессии
app.config["SESSION_TYPE"] = "filesystem"
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
                if delta.total_seconds() < 48 * 3600:
                    remaining = 48 * 3600 - delta.total_seconds()
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

        # Сохраняем время прохождения
        users_data = load_users()
        users_data[nickname] = {'last_time': datetime.now().isoformat()}
        save_users(users_data)

        # 🔥 Отправляем уведомление боту
        try:
            requests.post(
                "https://rrp07-bot-1.onrender.com/notify",
                json={
                    "nickname": nickname,
                    "goal": goal,
                    "time": time_commit,
                    "total_time": total_time,
                    "answers": answers,
                    "tab_events": session.get("tab_events", [])
                }
            )
        except Exception as e:
            print("Notify error:", e)

        session.clear()
        return render_template("result.html", nickname=nickname)
    except Exception as e:
        traceback.print_exc()
        return f"<h2>Ошибка: {e}</h2>"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
