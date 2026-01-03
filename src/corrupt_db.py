
import sqlite3
conn = sqlite3.connect('/home/mark/Development/mixtape-society/collection-data/collection.db')
conn.execute("PRAGMA writable_schema=ON")
conn.execute("UPDATE sqlite_master SET sql='broken' WHERE type='table'")
conn.commit()
conn.close()
