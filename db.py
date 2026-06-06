import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Sanjay@10",
        database="sales_management_system"
    )