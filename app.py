from flask import Flask, render_template, request, session, redirect, url_for
import json
from datetime import datetime
import traceback
import requests
import random

app = Flask(__name__)
app.secret_key = "fallback_secret"  # Сессии

# Загружаем вопросы
with open('questions.json', encoding='utf-8') as f:
    questions = json.load(f)

# Функция отправки сообщений в Telegram
def send_telegram(message):
    token = "8476542537:AAGrdS3eIWIRdWW7Iv-TpkQe5455EoEBGUo"
    chat_id = "1932300541"
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
        if session.get("finished"):  # нельзя пройти заново
            return render_template("result.html", nickname=session.get('nickname'))

        if request.method == "POST":
            nickname = request.form.get("nickname", "").strip()
            goal = request.form.get("goal", "").strip()
            time_commit = request.form.get("time_commit", "").strip()
            
            if nickname and goal and time_commit:
                session['nickname'] = nickname
                session['goal'] = goal
                session['time_commit'] = time_commit
                session['answers'] = []
                session['current'] = 0
                session['start_time'] = datetime.now().isoformat()
                session['questions'] = random.sample(questions, len(questions))
                return redirect(url_for('question'))
            else:
                return render_template("nickname.html", error="Заполните все поля")
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
            answer = request.form.get("answer", "").strip()
            session['answers'].append(answer if answer else "—")
            session['current'] = current + 1
            return redirect(url_for('question'))

        question = questions_list[current]
        return render_template(
            "question.html",
            question=question,
            question_number=current,
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
        goal = session.get('goal')
        time_commit = session.get('time_commit')
        start_time = datetime.fromisoformat(session.get('start_time'))
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()

        # Формируем сообщение для Telegram
        msg = f"<b>Новый участник прошёл тест</b>:\n"
        msg += f"<b>Ник:</b> {nickname}\n<b>Цель:</b> {goal}\n<b>Время на посту:</b> {time_commit}\n"
        msg += f"<b>Время прохождения:</b> {total_time:.1f} сек\n<b>Ответы:</b>\n"
        questions_list = session.get('questions', questions)
        for q, a in zip(questions_list, answers):
            msg += f"<b>{q['question']}</b>\nОтвет: {a}\n"

        send_telegram(msg)

        session['finished'] = True  # блокируем повторное прохождение
        return render_template("result.html", nickname=nickname)
    except Exception as e:
        traceback.print_exc()
        return f"<h2>Ошибка: {e}</h2>"

if __name__ == "__main__":
    port = 5000
    app.run(host="0.0.0.0", port=port, debug=True)
