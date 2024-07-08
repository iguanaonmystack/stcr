import sqlite3

connection = sqlite3.connect('database.db')


with open('schema.sql') as f:
    connection.executescript(f.read())

cur = connection.cursor()

for page in range(1, 8):
    for panel in range(1, 6):
        cur.execute("INSERT INTO panels (issue, page, panel) VALUES (?, ?, ?)",
                    (4, page, panel)
                    )

cur.execute("INSERT INTO users (discord_username, is_admin) VALUES (?, ?)",
            ('kapellosaur', True)
            )

connection.commit()
connection.close()
