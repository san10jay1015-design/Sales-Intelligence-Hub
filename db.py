import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="PASSWORD",
        database="sales_management_system"
    )
