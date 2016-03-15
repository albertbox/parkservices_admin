# -*- coding: utf-8 -*-
import os
import math
import json
from datetime import datetime, timedelta
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import hashlib
import requests
import smtplib

from flask import Flask, request, g, make_response, redirect
import pypyodbc
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


app = Flask(__name__, static_url_path='')   # static file is under "static" directory
app.config.from_object('config.DBConfig')


#============================================================================
# Database connection operation
#============================================================================
def connect_db():
    str_connect = "driver={}; server={}; database={}; uid={}; pwd={}" \
                  .format(app.config["DBTYPE"],
                          app.config["DBSERVER"],
                          app.config["DATABASE"],
                          app.config["USER"],
                          app.config["PASSWORD"],
                          autocommit=True)
    return pypyodbc.connect(str_connect)

@app.before_request
def before_request():
    g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
    if hasattr(g, 'db'):
        g.db.close()


#============================================================================
# Backend Management System
#============================================================================
@app.route('/', methods=['GET', 'POST'])
def index():
    return redirect('index.html')


#============================================================================
# Backend Operations - Parking Lots
#============================================================================
@app.route('/getparklots.cgi', methods=['POST'])
def get_parklots():
    result = {}
    groupid = request.form.get('gid', None)
    sessionid = request.form.get('sessionid', None)
    page = request.form.get('page', None)
    ppage = request.form.get('ppage', None)

    if groupid is None or groupid == '':
        result['result'] = -3       # Lost group id
        return json.dumps(result)

    if sessionid is None or sessionid == '':
        result['result'] = -2       # Lost sessionid
        return json.dumps(result)

    if page is None or page == '':
        result['result'] = -4       # Lost page no.
        return json.dumps(result)
    else:
        try:
            page = int(page)
        except:
            result['result'] = -5    # Invalid page no.
            return json.dumps(result)

    if ppage is None or ppage == '':
        ppage = 10                  # Default 10 entries per page
    else:
        try:
            ppage = int(ppage)
        except:
            result['result'] = -6   # Invalid per-page no.
            return json.dumps(result)

    cursor = g.db.cursor()
    sql = "SELECT COUNT(*) FROM parklots"
    cursor.execute(sql)
    row = cursor.fetchone()
    entries = row[0]

    if entries < ((page-1) * ppage):
        page = math.ceil(entries / ppage)

    sql = ("""SELECT TOP {} * FROM parklots WITH(INDEX(IDX_Disct))
              WHERE name NOT IN
              (SELECT TOP {} name FROM parklots WITH(INDEX(IDX_Disct)))"""
           .format(ppage, ((page-1)*ppage)))
    cursor.execute(sql)
    rows = cursor.fetchall()
    cursor.close()
    if rows is None:
        result['result'] = -1       # No Data
        return json.dumps(result)

    parklots = []
    for row in rows:
        row_parklots = list(row)
        row_parklots[-1] = str(row_parklots[-1])
        parklots.append(row_parklots)
    result['result'] = 0
    result['lots'] = parklots
    result['entries'] = entries
    result['page'] = page
    return json.dumps(result)


def check_lot_name(groupid, lotid, lotname):
    cursor = g.db.cursor()
    sql = ("""SELECT lid FROM parklots
               WHERE gid='{}' AND name='{}'""".format(groupid, lotname))
    cursor.execute(sql)
    row = cursor.fetchone()
    if row is None:
        return True
    else:
        if lotid == 0:
            return False
        elif row[0] != lotid:
            return False
        else:
            return True


@app.route('/saveparklot.cgi', methods=['POST'])
def save_parklot():
    result = {}
    groupid = request.form.get('gid', None)
    sessionid = request.form.get('sessionid', None)
    lotid = int(request.form.get('lotid', 0))

    lot = {}
    lot['name'] = request.form.get('name', None)
    lot['district'] = request.form.get('district', None)
    lot['address'] = request.form.get('address', None)
    lot['tel'] = request.form.get('tel', None)
    lot['xaxis'] = request.form.get('xaxis', None)
    lot['yaxis'] = request.form.get('yaxis', None)
    lot['indoor'] = request.form.get('indoor', None)
    lot['multistoreys'] = request.form.get('multistoreys', None)
    lot['hour24'] = request.form.get('hour24', None)
    lot['suv'] = request.form.get('suv', None)
    lot['attendant'] = request.form.get('attendant', None)
    lot['monthly'] = request.form.get('monthly', None)
    lot['timing'] = request.form.get('timing', None)
    lot['feemonthly'] = request.form.get('feemonthly', None)
    lot['ratehour'] = request.form.get('ratehour', None)
    lot['heightlimit'] = request.form.get('heightlimit', None)
    lot['servicetime'] = request.form.get('servicetime', None)
    lot['description'] = request.form.get('description', None)
    lot['totalcars'] = request.form.get('totalcars', 0)
    lot['totalmotors'] = request.form.get('totalmotors', 0)
    lot['totalbikes'] = request.form.get('totalbikes', 0)
    lot['totalpregnancy'] = request.form.get('totalpregnancy', 0)
    lot['totalhandicap'] = request.form.get('totalhandicap', 0)
    lot['totallargemotors'] = request.form.get('totallargemotors', 0)
    lot['chargestations'] = request.form.get('chargestations', 0)
    lot['delay_minutes'] = request.form.get('delay_minutes', 0)
    lot['apiip'] = request.form.get('apiip', None)
    lot['active'] = request.form.get('active', None)

    if groupid is None or groupid == '':
        result['result'] = -3       # Lost group id
        return json.dumps(result)

    if sessionid is None or sessionid == '':
        result['result'] = -2       # Lost sessionid
        return json.dumps(result)

    if check_lot_name(groupid, lotid, lot['name']) is False:
        result['result'] = -1       # Lot name is existed
        return json.dumps(result)

    cursor = g.db.cursor()
    if lotid == 0:
        cursor.execute("SELECT MAX(lid) FROM parklots WHERE gid='{}'".format(groupid))
        row = cursor.fetchone()
        new_lotid = int(row[0]) + 1
        sql = ("""INSERT INTO parklots values('{}', {}, '{}', '{}', '{}',
                         '{}', '{}', '{}', {}, {}, {}, {}, {}, {}, {}, {}, {},
                         '{}', '{}', '{}', {}, {}, {}, {}, {}, {}, {},
                         {}, '{}', {}, getdate())""".format(
                         groupid, new_lotid, lot['name'], lot['district'], lot['address'],
                         lot['tel'], lot['xaxis'], lot['yaxis'], lot['indoor'],
                         lot['multistoreys'], lot['hour24'], lot['suv'],
                         lot['attendant'], lot['monthly'], lot['timing'], lot['feemonthly'],
                         lot['ratehour'], lot['heightlimit'], lot['servicetime'],
                         lot['description'], lot['totalcars'], lot['totalmotors'],
                         lot['totalbikes'], lot['totalpregnancy'], lot['totalhandicap'],
                         lot['totallargemotors'], lot['chargestations'], lot['delay_minutes'],
                         lot['apiip'], lot['active']))
    else:
        sql = ("""UPDATE parklots SET name='{}', district='{}', address='{}',
                         tel='{}', xaxis='{}', yaxis='{}', indoor={}, 
                         multistoreys={}, hour24={}, suv={}, attendant={},
                         monthly={}, timing={}, feemonthly={}, ratehour={},
                         heightlimit='{}', servicetime='{}', description='{}',
                         totalcars={}, totalmotors={}, totalbikes={},
                         totalpregnancy={}, totalhandicap={}, totallargemotors={},
                         chargestations={}, delay_minutes={}, apiip='{}',
                         active={}, mdate=getdate()
                   WHERE gid='{}' AND lid={}""".format(lot['name'], lot['district'], 
                         lot['address'], lot['tel'], lot['xaxis'], lot['yaxis'],
                         lot['indoor'], lot['multistoreys'], lot['hour24'], lot['suv'],
                         lot['attendant'], lot['monthly'], lot['timing'], lot['feemonthly'],
                         lot['ratehour'], lot['heightlimit'], lot['servicetime'],
                         lot['description'], lot['totalcars'], lot['totalmotors'],
                         lot['totalbikes'], lot['totalpregnancy'], lot['totalhandicap'],
                         lot['totallargemotors'], lot['chargestations'], lot['delay_minutes'],
                         lot['apiip'], lot['active'], groupid, lotid))
    sql = sql.replace("''", "NULL")
    try:
        cursor.execute(sql)
        cursor.commit()
        cursor.close()
        result['result'] = 0
    except Exception as inst:
        print(inst.args)
        print(inst)
        result['result'] = -9           # SQL Failed
    return json.dumps(result)


@app.route('/removeparklot.cgi', methods=['POST'])
def remove_parklot():
    result = {}
    groupid = request.form.get('gid', None)
    sessionid = request.form.get('sessionid', None)
    lotid = int(request.form.get('lotid', 0))

    if groupid is None or groupid == '':
        result['result'] = -3       # Lost group id
        return json.dumps(result)

    if sessionid is None or sessionid == '':
        result['result'] = -2       # Lost sessionid
        return json.dumps(result)

    if lotid == 0:
        result['result'] = -4       # Lost Lot ID.
        return json.dumps(result)

    cursor = g.db.cursor()
    sql = "DELETE parklots WHERE gid='{}' AND lid={}".format(groupid, lotid)
    try:
        cursor.execute(sql)
        cursor.commit()
        result['result'] = 0
    except:
        result['result'] = -1
    return json.dumps(result)


#============================================================================
# Backend Operations - Administrator
#============================================================================
@app.route('/adminsignin.cgi', methods=['POST'])
def admin_signin():
    result = {}
    groupid = request.form.get('gid', None)
    userid = request.form.get('uid', None)
    pwd = request.form.get('pwd', None)

    if groupid is None or groupid == '':
        result['result'] = -3       # Lost group id
        return json.dumps(result)

    if pwd is None or pwd == '':
        result['result'] = -2       # Lost password when using Telephone registeration
        return json.dumps(result)

    cursor = g.db.cursor()
    cursor.execute("""SELECT * FROM admins
                       WHERE userid='{}' AND pwd='{}' AND groupid='{}'"""
                   .format(userid, pwd, groupid))
    rows = cursor.fetchone()
    cursor.close()
    if rows is None:
        result['result'] = -1       # Account is not existed or Password is invalid
        #result['group_id'] = groupid
        #result['userid'] = userid
        #result['pwd'] = pwd
        return json.dumps(result)
    result['result'] = 0
    result['sessionid'] = rows[3]
    return json.dumps(result)


@app.route('/getAdminInfo.cgi', methods=['POST'])
def getAdminInfo():
    result = {}
    groupid = request.form.get('gid', None)
    userid = request.form.get('userid', None)

    if groupid is None or groupid == '':
        result['result'] = -2       # Lost group id
        return json.dumps(result)

    if userid is None or userid == '':
        result['result'] = -3       # Lost user id
        return json.dumps(result)

    cursor = g.db.cursor()
    cursor.execute("""SELECT * FROM admins WHERE groupid='{}' AND userid='{}'"""
                   .format(groupid, userid))
    rows = cursor.fetchone()
    cursor.close()
    if rows is None:
        result['result'] = -1       # data not found
        return json.dumps(result)
    result['result'] = 0
    result['sessionid'] = rows[3]
    result['userid'] = rows[1]
    result['pwd'] = rows[2]
    result['name'] = rows[4]
    result['tel'] = rows[5]
    result['cdate'] = str(rows[6])
    return json.dumps(result)


@app.route('/setAdminInfo.cgi', methods=['POST'])
def setAdminInfo():
    result = {}
    groupid = request.form.get('gid', None)
    userid = request.form.get('userid', None)
    userid_new = request.form.get('userid_new', None)
    pwd = request.form.get('pwd', None)
    name = request.form.get('name', None)
    tel = request.form.get('tel', None)

    if groupid is None or groupid == '':
        result['result'] = -2       # Lost group id
        return json.dumps(result)

    if userid is None or userid == '':
        result['result'] = -3       # Lost user id
        return json.dumps(result)

    sessionid = hashlib.md5((groupid+userid_new).encode(encoding='utf-8')).hexdigest()
    if not pwd:
        sql = ("""UPDATE admins
                     SET userid='{}', sessionid='{}',
                         name='{}', tel='{}'
                   WHERE groupid='{}' AND userid='{}'"""
               .format(userid_new, sessionid, name, tel, groupid, userid))
    else:
        sql = ("""UPDATE admins
                     SET userid='{}', sessionid='{}',
                         name='{}', tel='{}', pwd='{}'
                   WHERE groupid='{}' AND userid='{}'"""
               .format(userid_new, sessionid, name, tel, pwd, groupid, userid))
    cursor = g.db.cursor()
    try:
        cursor.execute(sql)
        cursor.commit()
    except:
        result['result'] = -9       # data not found
        return json.dumps(result)
    
    result['result'] = 0
    result['sessionid'] = sessionid
    return json.dumps(result)


#============================================================================
# Backend Operations - Company, or called Group
#============================================================================
@app.route('/getCompanyInfo.cgi', methods=['POST'])
def getCompanyInfo():
    result = {}
    groupid = request.form.get('gid', None)

    if groupid is None or groupid == '':
        result['result'] = -2       # Lost group id
        return json.dumps(result)

    cursor = g.db.cursor()
    cursor.execute("""SELECT * FROM company WHERE gid='{}'"""
                   .format(groupid))
    rows = cursor.fetchone()
    cursor.close()
    if rows is None:
        result['result'] = -1       # group id not found
        return json.dumps(result)
    result['result'] = 0
    result['name'] = rows[1]
    result['address'] = rows[2]
    result['tel'] = rows[3]
    result['fax'] = rows[4]
    result['website'] = rows[5]
    result['code'] = rows[6]
    return json.dumps(result)


@app.route('/setCompanyInfo.cgi', methods=['POST'])
def setCompanyInfo():
    result = {}
    groupid = request.form.get('gid', None)

    if groupid is None or groupid == '':
        result['result'] = -2       # Lost group id
        return json.dumps(result)

    cursor = g.db.cursor()
    try:
        cursor.execute("""UPDATE company
                             SET name='{}', address='{}', tel='{}',
                                 fax='{}', website='{}', code='{}' WHERE gid='{}'"""
                       .format(request.form.get('name', None),
                               request.form.get('addr', None),
                               request.form.get('tel', None),
                               request.form.get('fax', None),
                               request.form.get('website', None),
                               request.form.get('code', None),
                               groupid))
        cursor.commit()
    except:
        result['result'] = -9       # Update Error
        return json.dumps(result)

    result['result'] = 0
    return json.dumps(result)




if __name__ == '__main__':
    app.run(debug=True)