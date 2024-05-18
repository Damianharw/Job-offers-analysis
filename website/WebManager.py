import sqlite3
from flask import Flask, render_template, g, request
from ..JobScrapper import execute


app = Flask(__name__)

def connect_db(db_path):
    return sqlite3.connect(db_path)

@app.before_request
def before_request():
    g.db = connect_db("offers.db")

@app.teardown_request
def teardown_request(exception):
    if hasattr(g, 'db'):
        g.db.close()

@app.route('/')
def index():
    cursor = g.db.cursor()
    fields = cursor.execute("SELECT DISTINCT field FROM jobs").fetchall()
    fields.remove(("data",))
    return render_template('index.html', fields = list(fields))

@app.route('/', methods=['POST'])
def executeT():
    field = request.form['keyword']
    execute(field)
    cursor = g.db.cursor()
    fields = cursor.execute("SELECT DISTINCT field FROM jobs").fetchall()
    fields.remove(("data",))
    return render_template('index.html', fields = list(fields))


@app.route('/statistics/<fieldName>.html')
def get_statistics(fieldName):
    cursor = g.db.cursor()
    min = int(request.args.get('min',-1))
    max = int(request.args.get('max',9999998))
    count = cursor.execute("SELECT COUNT() FROM jobs WHERE CAST(wage AS INTEGER) >= ? AND CAST(wage AS INTEGER) <= ? AND field = ?", (min-1, max+1, fieldName)).fetchone()[0]
    if count == 0:
        print("NULA")
        true_min = cursor.execute("SELECT MIN(wage) FROM jobs WHERE field = ?", (fieldName,)).fetchone()[0]
        true_max = cursor.execute("SELECT MAX(wage) FROM jobs WHERE field = ?", (fieldName,)).fetchone()[0]
        return render_template('statistics.html', count=0, wage = [0,0,0,0,0,0,true_min, true_max], types = [],
                            location = [], skills = [], education = [], experience = [])
    print(count)
    wage = get_wage(min, max, fieldName)
    types = get_types(min, max, fieldName)
    location = get_location(min, max, fieldName)
    skills = get_skills(min, max, fieldName)
    #"Any","High school", "Bachelor","Masters","PHD". 
    education = get_education(min, max, fieldName)
    experience = get_experience(min, max, fieldName)
    return render_template('statistics.html', count=count, wage = wage, types = types,
                            location = location, skills = skills, education = education, experience = experience, fieldName = fieldName)

def get_wage(min, max, fieldName):
    cursor = g.db.cursor()
    wage_info = list(cursor.execute("SELECT MIN(wage),MAX(wage),AVG(wage) FROM jobs WHERE wage >= ? AND wage <= ? AND field = ?", (min-1, max+1, fieldName)).fetchone())
    min_title = cursor.execute("SELECT title FROM jobs WHERE wage = ? AND field = ?", (wage_info[0], fieldName)).fetchone()[0]
    max_title = cursor.execute("SELECT title FROM jobs WHERE wage = ? AND field = ?", (wage_info[1], fieldName)).fetchone()[0]
    std_dev = cursor.execute("SELECT AVG((wage - ?) * (wage - ?)) FROM jobs WHERE wage >= ? AND wage <= ? AND field = ?", (wage_info[2], wage_info[2], min-1, max+1, fieldName)).fetchone()[0]**(1/2)
    true_min = cursor.execute("SELECT MIN(wage) FROM jobs WHERE field = ?", (fieldName,)).fetchone()[0]
    true_max = cursor.execute("SELECT MAX(wage) FROM jobs WHERE field = ?", (fieldName,)).fetchone()[0]
    wage_info[2] = round(wage_info[2], 2)
    std_dev = round(std_dev, 2)
    #print(list(wage_info) + [std_dev, min_title[0], max_title[0]])
    wage_info.extend([std_dev, min_title, max_title, true_min, true_max])
    return wage_info

def get_types(min, max, fieldName):
    cursor = g.db.cursor()
    cursor.execute("SELECT type, COUNT() FROM jobs WHERE wage >= ? AND wage <= ? AND field = ? GROUP BY type", (min-1, max+1, fieldName))
    res = cursor.fetchall()
    res.sort(key=lambda x: x[1], reverse=True)
    #fulltime, internship, ?other, parttime
    #print(res)
    return res
 
def get_skills(min, max, fieldName):
    cursor = g.db.cursor()
    skills = list(cursor.execute("SELECT * FROM skills"))
    res = []
    #print(list(skills))
    for skill in skills:
        count = cursor.execute("SELECT COUNT() FROM job_skills JOIN jobs ON job_skills.job_id = jobs.id WHERE job_skills.skill_id = ? AND jobs.wage >= ? AND jobs.wage <= ? AND jobs.field = ?", (skill[0], min-1, max+1, fieldName)).fetchone()[0]
        res.append((skill[1], count))
        print(count)
    res.sort(key=lambda x: x[1], reverse=True)
    return res[0:20]

def get_location(min, max, fieldName):
    cursor = g.db.cursor()
    cursor.execute("SELECT location, COUNT() FROM jobs WHERE wage >= ? AND wage <= ? AND field = ? GROUP BY location", (min-1, max+1, fieldName))
    res = cursor.fetchall()
    if fieldName == "data":
        minCount = 5
    else:
        minCount = 1
    res = [res[i] for i in range(len(res)) if res[i][1] > minCount]
    #print(res)
    return res

def get_education(min, max, fieldName):
    cursor = g.db.cursor()
    cursor.execute("SELECT education, COUNT() FROM jobs WHERE wage >= ? AND wage <= ? AND field = ? GROUP BY education", (min-1, max+1, fieldName))
    res = cursor.fetchall()
    res.sort(key=lambda x: x[1], reverse=True)
    #print(res)
    return res

def get_experience(min, max, fieldName):
    cursor = g.db.cursor()
    cursor.execute("SELECT experience, COUNT() FROM jobs WHERE wage >= ? AND wage <= ? AND field = ? GROUP BY experience", (min-1, max+1, fieldName))
    res = cursor.fetchall()
    #print(res)
    return res
