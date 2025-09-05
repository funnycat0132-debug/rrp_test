from flask import Flask, render_template, request, session, redirect, url_for
import json
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # нужно для сессий

# Загружаем вопросы
with open('questions.json', encoding='utf-8') as f:
    questions = json.load(f)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open("rrp07test").sheet1  # первая вкладка

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if 'nickname' in request.form:
            # Начало теста: ввод ника
            session['nickname'] = request.form['nickname'].strip()
            session['current'] = 0
            session['answers'] = []
            session['start_time'] = datetime.now().isoformat()
            return redirect(url_for('question'))
    return render_template("nickname.html")

@app.route("/question", methods=["GET", "POST"])
def question():
    current = session.get('current', 0)
    if current >= len(questions):
        return redirect(url_for('result'))

    if request.method == "POST":
        answer = request.form.get("answer", "").strip()
        session['answers'].append(answer)
        session['current'] = current + 1
        return redirect(url_for('question'))

    question = questions[current]
    return render_template("question.html", question=question, index=current+1, total=len(questions), nickname=session.get('nickname'))

@app.route("/result")
def result():
    nickname = session.get('nickname')
    answers = session.get('answers', [])
    start_time = datetime.fromisoformat(session.get('start_time'))
    end_time = datetime.now()
    total_time = (end_time - start_time).total_seconds()

    # Сохраняем в Google Sheets
    row = [nickname] + answers + [total_time]
    sheet.append_row(row)

    # Очистка сессии
    session.clear()

    return render_template("result.html", nickname=nickname, answers=answers, total_time=total_time)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
