import pymysql

def get_db_connection():
    return pymysql.connect(
        host="localhost",
        port=5001,
        user="root",
        password="822048",
        database="chatapp",
        cursorclass=pymysql.cursors.DictCursor
    )
