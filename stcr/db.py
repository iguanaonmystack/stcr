import sqlite3

def get_db_connection():
    conn = sqlite3.connect('/var/lib/stcr/src/database.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_or_create_user(conn, discord_username):
    db_user = None
    while db_user is None:
        db_user = conn.execute(
                'SELECT u.* '
                ', al.id as aid'
                ', al.created as acreated'
                ', pa.issue as a_issue'
                ', pa.page as a_page'
                ', pa.panel as a_panel'
                ' FROM users u '
                '  LEFT JOIN allocations al ON al.user = u.id'
                '  LEFT JOIN panels pa ON pa.id = al.panel AND pa.issue = 4 '
                ' WHERE discord_username = (?)'
                ' ORDER BY acreated DESC'
                , (discord_username,)).fetchone()
        if db_user is None:
            db_user = conn.execute(
                'INSERT INTO users (discord_user, is_admin) VALUES (?,?)',
                (discord_username, False))
    return db_user

