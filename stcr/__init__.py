import os
import sqlite3

from flask import Flask, redirect, url_for, request
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

def get_or_create_user(conn, discord_user):
    db_user = None
    while db_user is None:
        db_user = conn.execute(
                'SELECT u.* '
                ', pc.page as pc_page'
                ', pc.panel as pc_panel'
                ', c.status as status'
                ' FROM users u '
                '  LEFT JOIN panels pc ON pc.id = u.confirmed_choice AND pc.issue = 4 '
                '  LEFT JOIN choices c ON c.from_user = u.id AND c.status = "PENDING" '
                ' WHERE discord_username = (?)'
                , (discord_user.name,)).fetchone()
        if db_user is None:
            db_user = conn.execute(
                'INSERT INTO users (discord_user, is_admin) VALUES (?,?)',
                (discord_user.name, False))
    return db_user

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

@app.route("/allocate", methods=('POST',))
@requires_authorization
def allocate():
    """Store the user's panel choices.
    
    The task queue will process whether it's valid or not later."""
    discord_user = discord.fetch_user()

    conn = get_db_connection()
    db_user = get_or_create_user(conn, discord_user)

    first_choice = tuple(map(int, (request.form['first_choice'] or '0-0').split('-')))
    second_choice = tuple(map(int, (request.form['second_choice'] or '0-0').split('-')))
    third_choice = tuple(map(int, (request.form['third_choice'] or '0-0').split('-')))

    conn.execute(
        "INSERT INTO choices (from_user, first_choice, second_choice, third_choice)"
        "VALUES "
        "( ?"
        ", (SELECT id FROM panels p WHERE p.issue == 4 AND p.page = ? AND p.panel = ?)"
        ", (SELECT id FROM panels p WHERE p.issue == 4 AND p.page = ? AND p.panel = ?)"
        ", (SELECT id FROM panels p WHERE p.issue == 4 AND p.page = ? AND p.panel = ?)"
        ")",
        (db_user['id'],) + first_choice + second_choice + third_choice
    )
    conn.commit()
    return redirect(url_for(".me"))

@app.route("/")
@requires_authorization
def me():
    discord_user = discord.fetch_user()

    conn = get_db_connection()
    db_user = get_or_create_user(conn, discord_user)

    available_panels = conn.execute(
        "SELECT * FROM panels p "
        " WHERE issue = 4 "
        " AND NOT EXISTS ("
        "    SELECT * FROM users u WHERE u.confirmed_choice == p.id"
        " )"
    ).fetchall()

    conn.close()
    return render_template('me.html',
            available_panels=list(available_panels),
            discord_user=discord_user,
            db_user=db_user)


if __name__ == "__main__":
    app.run()
