import sys
import re
import socket
from datetime import datetime
from waitress import serve
import mysql.connector as mysql
import pandas as pd
from flask import Flask, render_template, request
from mysql.connector import errorcode


def connect_to_database():
    try:
        mydb = mysql.connect(
            host="localhost",
            user="root",
            password="Teams1234",
            database="MinecraftServers",
            charset="utf8mb4",
            collation="utf8mb4_unicode_ci"
        )

    except mysql.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Something is wrong with your user name or password")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Database does not exist")
        else:
            print(err)
    else:
        return mydb

    sys.exit(1)


app = Flask(__name__)


def strip_color_codes(text):
    return re.sub(r'§[0-9a-fk-or]', '', text)


def get_dns_name(ip):
    try:
        dns_name = socket.gethostbyaddr(ip)[0]
        dns_name.count("-")
        if dns_name.count("-") >= 2:
            return "N/A"
        else:
            return dns_name
    except socket.herror:
        return "N/A"


def get_server_info(filename, mydb):
    with open(filename, 'r') as file:
        lines = file.readlines()[1:]

    data = [line.strip().split(",") for line in lines if line.strip()]
    df = pd.DataFrame(data, columns=["IP", "Port", "Country", "Version", "Online", "Max", "Ping", "MOTD"])

    df["Port"] = df["Port"].astype(int)
    df["Online"] = df["Online"].astype(int)
    df["Max"] = df["Max"].astype(int)
    df["Ping"] = df["Ping"].astype(int)

    server_info_list = []
    for index, row in df.iterrows():
        dns_name = get_dns_name(row['IP'])

        server_info = {
            "ip": row['IP'],
            "dns_name": dns_name,
            "version": row['Version'],
            "online": row['Online'],
            "ping": row['Ping'],
            "port": row['Port'],
            "motd": strip_color_codes(row['MOTD'])
        }

        update_server_data(server_info, mydb)

        server_info_list.append(server_info)

    return server_info_list


def update_server_data(server_info, mydb):
    q = "SELECT COUNT(*) FROM ServerInformation WHERE ip = %(ip)s"

    cursor = mydb.cursor()

    cursor.execute(q, {'ip': server_info["ip"]})
    count = cursor.fetchone()[0]
    if count == 0:
        q = "INSERT INTO ServerInformation VALUES (%s, %s, %s)"
        cursor.execute(q, (server_info["ip"], server_info["dns_name"], server_info["port"]))

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    q = "INSERT INTO ServerStatus VALUES (%s, %s, %s, %s, %s)"
    cursor.execute(q, (server_info["ip"], server_info["version"], server_info["online"], server_info["motd"], timestamp))

    mydb.commit()
    cursor.close()


def get_data_from_database(ips, mydb):
    data = dict()
    cursor = mydb.cursor()
    all_dates = set()

    for ip in ips:
        q = """SELECT online, timestamp 
            FROM ServerStatus 
            WHERE ip = %(ip)s
            ORDER BY timestamp DESC
            LIMIT 10"""

        cursor.execute(q, {"ip": ip})


        selected_data = cursor.fetchall()

        server_data = dict()
        for online_count, time in selected_data:
            date_str = time.strftime('%Y-%m-%d_%H:%M')
            all_dates.add(date_str)
            server_data[date_str] = online_count

        data[ip] = server_data

    sorted_dates = sorted(all_dates)

    return data, sorted_dates


@app.route('/')
def index():
    mydb = connect_to_database()
    server_info = get_server_info(sys.argv[1], mydb)
    return render_template('index.html', server_info=server_info)


@app.route('/selected_ips', methods=['POST'])
def selected_ips():
    selected_ips = request.form.getlist('selected_ips')
    mydb = connect_to_database()
    data, sorted_dates = get_data_from_database(selected_ips, mydb)
    return render_template('selected_ips.html', data=data, dates=sorted_dates)


if __name__ == '__main__':
    serve(app, host="0.0.0.0", port=8080)
