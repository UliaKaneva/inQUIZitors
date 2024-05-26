from flask import Flask
import copy
from flask_socketio import SocketIO, emit
from flask import render_template, request, session, redirect, url_for, g, make_response
from flask_login import LoginManager, login_user, login_required, logout_user, current_user

from werkzeug.security import generate_password_hash, check_password_hash
from DataBase import DataBase
from UserLogin import UserLogin
from random import shuffle
import sqlite3
import json

import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "your_secret_key"
socketio = SocketIO(app)

# configuration
DATABASE = "/templates/flsite.db"
SECRET_KEY = "1488"
MAX_CONTENT_LENGTH = 1024 * 1024
quiz_rooms = {}
app.config.from_object(__name__)
app.config.update(dict(DATABASE=os.path.join(app.root_path, "flsite.db")))

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Авторизуйтесь для доступа к закрытым страницам"
login_manager.login_message_category = "success"

quiz_is_started = True
test_n = 0
quiz_dir = "static/quizes"
quizzes = {}
all_user_answers = {}
for quiz in os.listdir(quiz_dir):
    quizzes[quiz] = json.loads(open(os.path.join(quiz_dir, quiz), encoding="utf-8-sig").read())


def make_quiz_list():
    template_quiz = []
    for el in quizzes:
        if el != "quiz_template":
            template_quiz.append([el, quizzes[el]["name"], quizzes[el]["description"]])
    return template_quiz


def check_answer(quest_id, answer, last_question):
    quiz = copy.deepcopy(quizzes[quest_id])["questions"][last_question - 1]
    for el in quiz["options"]:
        if el[0] == answer and el[1]:
            return True
    return False


def end_quiz():
    session["last_question"] = 0
    session["quiz"] = 0
    session["total"] = 0
    session["answers"] = 0


def save_answers():
    answer = request.form.get("ans_text")
    quest_id = request.form.get("q_id")
    session["last_question"] += 1
    session["total"] += 1
    if check_answer(quest_id, answer, session["last_question"]):
        session["answers"] += 1


def question_form(question):
    answers_list = [question[0], question[1], question[2], question[3]]
    if ".json" in session["quiz"]:
        image_url = f"""{session["quiz"][:-5]}_{str(session["last_question"])}.png"""
    else:
        image_url = f"""{session["quiz"]}_{str(session["last_question"])}.png"""
    full_path = os.path.join("static\images", image_url)
    if not os.path.exists(full_path):
        image_url = "планета.jpg"
    return render_template("quiz.html", answers_list=answers_list, question=question[4], quest_id=question[5],
                           image_url=image_url)


def start_create_quiz(quiz_id):
    session["quiz_start"] = 0
    session["quiz_dict"] = {}
    session["last_quiz_id"] = 0


def test(n):
    global test_n
    test_n = n


def start_quiz(quiz_id):
    session["last_question"] = 0
    session["quiz"] = quiz_id
    session["total"] = 0
    session["answers"] = 0


def change_session():
    session["quiz_is_started"] = 1


def get_question_after(last_id, quiz_id):
    quiz = copy.deepcopy(quizzes[quiz_id])["questions"]
    if last_id < len(quiz):
        quiz = quiz[last_id]
        questions = []
        for el in quiz["options"]:
            questions.append(el[0])
        shuffle(questions)
        questions += [quiz["text"], quiz_id]
        return questions
    return False


@login_manager.user_loader
def load_user(user_id):
    return UserLogin().fromDB(user_id, dbase)


def connect_db():
    conn = sqlite3.connect(app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def create_db():
    db = connect_db()
    with app.open_resource("sq_db.sql", mode="r") as f:
        db.cursor().executescript(f.read())
    db.commit()
    db.close()


def get_db():
    if not hasattr(g, "link_db"):
        g.link_db = connect_db()
    return g.link_db


dbase = None


@app.before_request
def before_request():
    global dbase
    db = get_db()
    dbase = DataBase(db)


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("profile"))
    return render_template("Front_Page.html")


@app.route("/register", methods=["GET", "POST"])
def registration():
    if current_user.is_authenticated:
        return redirect(url_for("profile"))
    if request.method == "POST":
        session.pop("_flashes", None)
        if len(request.form["name"]) > 2 and len(request.form["email"]) > 4 \
                and len(request.form["password"]) > 4 and request.form["password"] == request.form["repassword"]:
            hash = generate_password_hash(request.form["password"])
            res = dbase.addUser(request.form["name"], request.form["email"], hash)
            if res:
                return redirect(url_for("login"))
    return render_template("registration.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("profile"))
    if request.method == "POST":
        user = dbase.getUserByEmail(request.form["email"])
        if user and check_password_hash(user["password"], request.form["password"]):
            userlogin = UserLogin().create(user)
            login_user(userlogin, remember=True)
            return redirect(url_for("profile"))
    return render_template("login.html")


@app.route("/prom")
def prom():
    return render_template("prom.html")


@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html")


@app.route("/quiz_list", methods=["GET", "POST"])
@login_required
def quiz_list():
    return render_template("quiz_list.html", quiz_list=make_quiz_list())


@app.route("/quiz/<id>/", methods=["GET", "POST"])
@login_required
def quiz(id):
    if not ("quiz" in session) or session["quiz"] == 0 or id != session["quiz"]:
        start_quiz(id)
    if request.method == "POST":
        save_answers()
    next_question = get_question_after(session["last_question"], session["quiz"])
    if next_question == False:
        session["total_quiz"] = id
        return redirect(url_for("quiz_check"))
    else:
        return question_form(next_question)


@app.route("/check_quiz", methods=["POST", "GET"])
def quiz_check():
    answers = session["answers"]
    total = session["total"]
    end_quiz()
    for el in quiz_rooms:
        if quiz_rooms[el]["quiz_name"] == session["total_quiz"] and session["nickname"] in quiz_rooms[el]["members"]:
            all_user_answers[session["nickname"]] = answers
            return render_template("multiplayer_quiz_check.html", total=total, right=answers)
    return render_template("quiz_check.html", total=total, right=answers)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/create_quiz", methods=["GET", "POST"])
def create_quiz():
    if request.method == "POST":
        if "quiz_start" not in session:
            start_create_quiz(1)
        array = []
        if "image" in request.files:
            file = request.files["image"]
            if file.filename != "":
                file.save(
                    os.path.join("static/images", f"""{request.form.get("input-1")}_{session["last_quiz_id"]}.png"""))
        for i in range(1, 9):
            array.append(request.form.get("input-" + str(i)))
        create_quiz_json(array)
        if request.form.get("save-quiz") is not None:
            save_quiz()
    return render_template("create_quiz.html")


def save_quiz():
    template = session["quiz_dict"]
    with open(f"""static/quizes/{template["name"]}.json""", "w") as outfile:
        json.dump(template, outfile)
    quizzes[template["name"]] = template
    session["quiz_start"] = 0
    session["quiz_dict"] = {}
    session["last_quiz_id"] = 0


def create_quiz_json(array):
    with open("static/quizes/quiz_template", "r") as f:
        if session["quiz_dict"] == {}:
            template = json.load(f)
        else:
            template = session["quiz_dict"]
        question_id = session["last_quiz_id"]
        temp = {"text": "", "options": []}
        template["name"] = array[0]
        template["description"] = array[1]
        template["questions"].append(temp)

        template["questions"][question_id]["text"] = array[2]
        for i in range(4):
            if i == int(array[-1]) - 1:
                correct_answer = True
            else:
                correct_answer = False
            template["questions"][question_id]["options"].append([array[i + 3], correct_answer])
        session["last_quiz_id"] += 1
        session["quiz_dict"] = template


@app.route("/profile")
@login_required
def profile():
    session["quiz_is_started"] = 0
    return render_template("profile.html")


@app.route("/userava")
@login_required
def userava():
    img = current_user.getAvatar(app)
    if not img:
        return ""
    h = make_response(img)
    h.headers["Content-Type"] = "image/png"
    return h


@app.route("/quiz_img_upload", methods=["GET", "POST"])
@login_required
def quiz_img_upload():
    if request.method == "POST":
        file = request.files["file"]
        file.save(os.path.join("/static/images", f""""{session["quiz_name"]}{session["last_quiz_id"]}"""))


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        file = request.files["file"]
        if file and current_user.verifyExt(file.filename):
            try:
                img = file.read()
                res = dbase.updateUserAvatar(img, current_user.get_id())
                if not res:
                    return redirect(url_for("profile"))
            except FileNotFoundError as e:
                pass
    return redirect(url_for("profile"))


@app.route("/quiz_multiplayer", methods=["POST", "GET"])
def quiz_multiplayer():
    session["nickname"] = current_user.getName()
    global quiz_rooms
    if request.method == "POST":
        room_name = request.form.get("name")
        quiz_rooms[room_name] = {"admin": session["nickname"], "members": [session["nickname"]], "answered_players": []}
    return render_template("quiz_multiplayer.html", quiz_rooms=quiz_rooms)


@app.route("/quiz_multiplayer/<name>/", methods=["POST", "GET"])
def quiz_lobby(name):
    global quiz_rooms
    if session["nickname"] not in quiz_rooms[name]["members"]:
        quiz_rooms[name]["members"].append(session["nickname"])
    session["room_name"] = name
    if request.method == "POST":
        room_name = request.form.get("name")
    return render_template("quiz_lobby.html", lobby_name=name, quiz_list=make_quiz_list())


def is_room_creator():
    return quiz_rooms[session["room_name"]]["admin"] == session["nickname"]


@socketio.on("connect")
def handle_connect():
    if not session["quiz_is_started"]:
        emit("check_players", {}, broadcast=True)
        emit("user_role", {"role": is_room_creator()})


@socketio.on("start_quiz")
def start_quiz_multiplayer(data):
    global quiz_is_started
    global quiz_rooms
    quiz_is_started = True
    for el in quizzes:
        if quizzes[el]["name"] == data:
            new_data = el
    quiz_rooms[session["room_name"]]["quiz_name"] = new_data
    emit("start_quiz", [session["room_name"], f"/quiz/{new_data}"], broadcast=True)


@socketio.on("count_all_users_answers")
def count_all_users_answers():
    global quiz_rooms
    global quiz_is_started
    flag = True
    quiz_rooms[session["room_name"]]["answered_players"].append(session["nickname"])
    for user in quiz_rooms[session["room_name"]]["members"]:
        if user not in quiz_rooms[session["room_name"]]["answered_players"]:
            flag = False
    if flag:
        max_n = 0
        nick = ""
        for el in quiz_rooms[session["room_name"]]["answered_players"]:
            if all_user_answers[el] > max_n:
                max_n = all_user_answers[el]
                nick = el
        emit("show_result", [nick, max_n], broadcast=True)
        del quiz_rooms[session["room_name"]]
        quiz_is_started = False


@socketio.on("check_players")
def check_players():
    socketio.emit("players_list", data=[quiz_rooms[session["room_name"]]["members"], session["room_name"]])


@socketio.on("disconnect")
def handle_disconnect():
    test(2)
    if not quiz_is_started:
        emit("check_players", {}, broadcast=True)
        qr = copy.deepcopy(quiz_rooms)
        quiz_rooms[session["room_name"]]["members"].remove(session["nickname"])
        if quiz_rooms[session["room_name"]]["admin"] == session["nickname"]:
            del quiz_rooms[session["room_name"]]
        socketio.emit("user_disconnected", {"username": session["nickname"]})


if __name__ == "__main__":
    socketio.run(app, allow_unsafe_werkzeug=True)
