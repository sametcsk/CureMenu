import sqlite3
conn = sqlite3.connect('healmenu.db')
cursor = conn.cursor()
cursor.execute("DELETE FROM interaction_logs WHERE cevap LIKE '%biomarkers%'")
print(f"Deleted {cursor.rowcount} bad logs.")
conn.commit()
