
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'portfolio.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Distinct Portfolio IDs in holdings:")
for row in cursor.execute("SELECT DISTINCT portfolio_id FROM holdings"):
    print(row[0])

print("\nSample rows from holdings:")
for row in cursor.execute("SELECT * FROM holdings LIMIT 3"):
    print(dict(row))

print("\nSample rows from price_cache:")
for row in cursor.execute("SELECT * FROM price_cache LIMIT 3"):
    print(dict(row))

conn.close()
