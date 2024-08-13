import psycopg2
import os

connection = psycopg2.connect('dbname=stcr user=stcr password=%s' % os.getenv('STCRDBPW'))

cur = connection.cursor()
with open('schema_psql.sql') as f:
    cur.execute(f.read())

for page in range(1, 8):
    for panel in range(1, 6):
        cur.execute("INSERT INTO panels (issue, page, panel) VALUES (%s, %s, %s)",
                    (4, page, panel)
                    )

cur.execute("INSERT INTO users (discord_username, is_admin) VALUES (%s, %s)",
            ('kapellosaur', True)
            )

connection.commit()
connection.close()
