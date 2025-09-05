from flask import Flask, render_template, request, session, redirect, url_for
import json
from datetime import datetime
import traceback
import requests

app = Flask(__name__)
app.secret_key = "super_secret_key_123"  # можно заменить на любое

# Загружаем вопросы
with open('questions.json', encoding='utf-8') as f:
    questions = json.load(f)

# Функция отправки сообщений в Telegram
def send_tg(message):
    chat_id = 1932300541  # твой TG_CHAT_ID
    url = "https://api.telegram.org/bot8476542537:AAGrdS3eIWIRdWW7Iv-TpkQe5455EoEBGUo/sendMessage"
    payload = {'chat_id': chat_id, 'text': message}
    try:
        res = requests.post(url, data=payload)
        print("Telegram API ответ:", res.json())
        return res.json()
    except Exception as e:
        print("Ошибка при отправке в Telegram:", e)
        return None

@app.route("/", methods=["GET", "POST"])
def index():
    try:
        if request.method == "POST":
            nickname = request.form.get("nickname", "").strip()
            if nickname:
                session['nickname'] = nickname
                session['current'] = 0
                session['answers'] = []
                session['start_time'] = datetime.now().isoformat()
                return redirect(url_for('question'))
            else:
                return render_template("nickname.html", error="Введите ник")
        return render_template("nickname.html")
    except Exception as e:
        traceback.print_exc()
        return f"<h2>Ошибка: {e}</h2>"

@app.route("/question", methods=["GET", "POST"])
def question():
    try:
        current = session.get('current', 0)
        if current >= len(questions):
            return redirect(url_for('result'))

        if request.method == "POST":
            answer = request.form.get("answer", "").strip()
            session['answers'].append(answer if answer else "—")
            session['current'] = current + 1
            return redirect(url_for('question'))

        question = questions[current]
        return render_template(
            "question.html",
            question=question,
            question_number=current,
            total=len(questions),
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
        start_time = datetime.fromisoformat(session.get('start_time'))
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()

        # Формируем сообщение для Telegram
        msg = "\n".join([f"{i+1}. {a}" for i, a in enumerate(answers)])
        msg = f"Новый ответ от {nickname}:\n{msg}\nВремя: {total_time:.1f} сек"
        send_tg(msg)

        # Очистка сессии
        session.clear()

        return render_template(
            "result.html",
            nickname=nickname,
            answers=answers,
            total_time=total_time
        )
    except Exception as e:
        traceback.print_exc()
        return f"<h2>Ошибка: {e}</h2>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
