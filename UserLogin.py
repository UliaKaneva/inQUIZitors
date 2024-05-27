from flask import url_for
import sqlite3


class UserLogin:
    def fromDB(self, user_id, db):
        self.__user = db.getUser(user_id)
        return self

    def create(self, user):
        self.__user = user
        return self

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.__user["id"])

    def getName(self):
        return self.__user["name"] if self.__user else "Без имени"

    def getEmail(self):
        return self.__user["email"] if self.__user else "Без email"

    def getAvatar(self, app):
        img = None
        if not self.__user["avatar"]:
            try:
                with app.open_resource(app.root_path + url_for("static", filename="images/default.png"), "rb") as f:
                    img = f.read()
            except FileNotFoundError as e:
                pass
        else:
            img = self.__user["avatar"]

        return img

    def verifyExt(self, filename):
        ext = filename.rsplit(".", 1)[1]
        if ext == "png" or ext == "PNG":
            return True
        return False

    def updateUserAvatar(self, avatar, user_id):
        if not avatar:
            return False

        try:
            binary = sqlite3.Binary(avatar)
            self.__cur.execute(f"UPDATE users SET avatar = ? WHERE id = ?", (binary, user_id))
            self.__db.commit()
        except sqlite3.Error as e:
            return False
        return True
