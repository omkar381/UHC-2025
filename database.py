import sqlite3

def create_table():
    con = sqlite3.connect("users.db")
    cur = con.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    email TEXT,
                    qr_code TEXT)''')
    con.commit()
    con.close()
