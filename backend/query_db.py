import psycopg2
import os

db_url = "postgresql://branin_user:jycxu1-Sejcyx-tocdyd@pgm-7xvr64yzlj6hkl70go.pg.rds.aliyuncs.com:5432/branin_db"
conn = psycopg2.connect(db_url)
cur = conn.cursor()
cur.execute("SELECT id, email FROM users WHERE id IN ('8f0ee69a-dfe4-4988-9202-6660f3245f7f', '7c8e9bb4-7403-4826-8ead-9eb5e47523f5');")
rows = cur.fetchall()
for r in rows:
    print(r)
