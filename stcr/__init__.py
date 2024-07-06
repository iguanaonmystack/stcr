import os
import sqlite3

from flask import Flask, redirect, url_for
from flask import render_template
from flask_discord import DiscordOAuth2Session, requires_authorization, Unauthorized

app = Flask(__name__)

exec(open(os.path.dirname(__file__) + '/../secrets.py').read())  # provides `config`

app.secret_key = config['flask_secret_key']
# OAuth2 must make use of HTTPS in production environment.
#os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "true"      # !! Only in development environment.

app.config["DISCORD_CLIENT_ID"] = config['client_id']    # Discord client ID.
app.config["DISCORD_CLIENT_SECRET"] = config['client_secret']                # Discord client secret.
app.config["DISCORD_REDIRECT_URI"] = "https://stcr.nevira.net/app/auth/discord-redirect"                 # URL to your callback endpoint.
app.config["DISCORD_BOT_TOKEN"] = ""                    # Required to access BOT resources.


def get_db_connection():
    conn = sqlite3.connect('/var/lib/stcr/src/database.db')
    conn.row_factory = sqlite3.Row
    return conn

discord = DiscordOAuth2Session(app)

@app.route("/auth/discord-login/")
def login():
    return discord.create_session(scope=['identify', 'email'])


@app.route("/auth/discord-redirect")
def callback():
    discord.callback()
    user = discord.fetch_user()
    #welcome_user(user)
    return redirect(url_for(".me"))


@app.errorhandler(Unauthorized)
def redirect_unauthorized(e):
    return redirect(url_for("login"))


@app.route("/")
@requires_authorization
def me():
    discord_user = discord.fetch_user()

    conn = get_db_connection()
    db_user = None
    while db_user is None:
        db_user = conn.execute(
                'SELECT u.* '
                ', pc.page as pc_page'
                ', pc.panel as pc_panel'
                ', p1.page as p1_page'
                ', p1.panel as p1_panel'
                ', p2.page as p2_page'
                ', p2.panel as p2_panel'
                ', p3.page as p3_page'
                ', p3.panel as p3_panel'
                ' FROM users u '
                '  LEFT JOIN panels pc ON pc.id = u.confirmed_choice AND pc.issue = 4 '
                '  LEFT JOIN panels p1 ON p1.id = u.first_choice AND p1.issue = 4 '
                '  LEFT JOIN panels p2 ON p2.id = u.second_choice AND p2.issue = 4 '
                '  LEFT JOIN panels p3 ON p3.id = u.third_choice AND p3.issue = 4 '
                ' WHERE discord_username = (?)'
                , (discord_user.name,)).fetchone()
        if db_user is None:
            db_user = conn.execute(
                'INSERT INTO users (discord_user, is_admin) VALUES (?,?)',
                (discord_user.name, False))
    conn.close()

    return render_template('me.html',
            discord_user=discord_user,
            db_user=db_user)


if __name__ == "__main__":
    app.run()
