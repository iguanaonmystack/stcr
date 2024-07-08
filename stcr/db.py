import sqlite3

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

