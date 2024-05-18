import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import sqlite3
import time

client = OpenAI()

class ChatGPT:
    def __init__(self, api_key, initial_prompt = ""):
        client.api_key = api_key
        self.assistant = client.beta.assistants.create(
            name="Info extractor",
            instructions=initial_prompt,
            model="gpt-3.5-turbo-0125",
            temperature=0.5)
        
    def create_new_thread(self):
        self.thread = client.beta.threads.create()
        
    
    def add_message(self, message):
        client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content= message)

    def run(self):
        return client.beta.threads.runs.create_and_poll(
            thread_id=self.thread.id,
            assistant_id=self.assistant.id,
            timeout=20)
    
    def getResponse(self):
        return client.beta.threads.messages.list(thread_id=self.thread.id).data[0].content[0].text.value



class JobScrapper:

    DOMAINS = {
    "profesia": "praca/?search_anywhere="
    }
    
    def __init__(self, domain):
        self.domain = domain
        try:
            self.response = requests.get(self.domain)   
        except:
            print("Error: Invalid domain")
            return None
        
    def create_chat(self, api_key, initial_prompt):
        self.chat = ChatGPT(api_key, initial_prompt)
        self.chat.create_new_thread()


class JobScrapperProfesia(JobScrapper):
    def __init__(self):
        super().__init__("https://www.profesia.sk")
    
    def scrape_job_offers(self, field, page_count = 3):
        job_hub_url = requests.get(self.response.url + JobScrapper.DOMAINS["profesia"] + field)
        if page_count is None:
            page_count = self.__get_number_of_pages(job_hub_url.text)
        #print(page_count)
        jobs_htmls = []
        for i in range(1, page_count+1):
            print(i)
            if(i == 1):
                jobs = job_hub_url
            else:
                jobs = requests.get(self.response.url + JobScrapper.DOMAINS["profesia"] + field + "&page_num=" + str(i))
            jobs_htmls.extend(self.__scrape_page(jobs.text))
        return jobs_htmls
    
    def extract_job_information(self, job_htmls):
        if type(job_htmls) is not list:
            raise AttributeError("Error: job_htmls must be a list")
        if self.chat is None:
            raise NotImplementedError("Error: Must initalise chatGPT before extracting job information")
        job_info = []
        for job in job_htmls:
            self.chat.add_message(job.prettify())
            run = self.chat.run()
            if run.status != "completed":
                print(run.status)
            job_info.append(self.chat.getResponse())
            print("JOB DONE")
            time.sleep(0.3)
        return job_info

    
    def __get_number_of_pages(self, job_hub):
        soup = BeautifulSoup(job_hub, "html.parser")
        try:
            pagination = soup.find("ul", class_="pagination")
            li_list = pagination.find_all("li")
            last_page_li = li_list[-2]
            last_page = last_page_li.get_text()
            return int(last_page)
        except AttributeError: # if there is no pagination - only one page
            return 1
    
    def __scrape_page(self, page):
        soup = BeautifulSoup(page, "html.parser")
        jobs = []
        job_hyperlinks = soup.select("ul.list li h2 a")
        for job in job_hyperlinks:
            job_url = requests.get(self.domain + job.attrs["href"])
            job_soup = BeautifulSoup(job_url.text, "html.parser")
            job_description = job_soup.find("div", class_=["card", "card-content"])
            jobs.append(job_description)
        return jobs
    
class JobDatabase:

    def __init__(self, db_name = "offers.db"):
        self.con = sqlite3.connect(db_name)
        self.cursor = self.con.cursor()

    def add_data(self, field_name, field_data, sep = '|'):
        if type(field_data) is not list:
            raise AttributeError("Error: field_data must be a list")
        incorrect = []
        for data in field_data:
            #title, company, type, wage, city, education,langs,  experience, skills
            data_list = data.split('\n')[0].strip("|").split(sep)
            data_list = [x.strip() for x in data_list]
            data_list = [x.strip('"') for x in data_list]
            try:
                self.cursor.execute("INSERT INTO jobs (field, title, company, type, wage, location, education, languages, experience, skills)"
                                "VALUES (?,?,?,?,?,?,?,?,?,?)", (field_name, *data_list))
            except sqlite3.OperationalError:
                print("Error: Invalid data format")
                incorrect.append(data)
            job_id = self.cursor.lastrowid
            skills = data_list[-1].split(';')
            skills = [skill.strip().lower() for skill in skills]
            for skill in skills:
                if not self.cursor.execute("SELECT * FROM skills WHERE description = ?", (skill,)).fetchone():
                    skill_id = self.add_skill(skill)
                else:
                    skill_id = self.cursor.execute("SELECT id FROM skills WHERE description = ?", (skill,)).fetchone()[0]
                self.cursor.execute("INSERT INTO job_skills (skill_id, job_id) VALUES (?,?)", (skill_id, job_id))
        return incorrect

    def delete_data(self, id):
        if type(id) is not int:
            raise TypeError("Error: id must be of type int")
        self.cursor.execute("DELETE FROM jobs WHERE id = ?", (id,))
        if self.cursor.rowcount == 0:
            return False
        return True

    def delete_field(self, field_name):
        self.cursor.execute("DELETE FROM jobs WHERE field = ?", (field_name,))
        if self.cursor.rowcount == 0:
            return False
        return True

    def add_skill(self, skill):
        self.cursor.execute("INSERT INTO skills (description) VALUES (?)", (skill,))
        return self.cursor.lastrowid

    def remove_skill(self, id):
        if type(id) is str:
            self.cursor.execute("DELETE FROM skills WHERE description = ?", (id,))
        elif type(id) is int:
            self.cursor.execute("DELETE FROM skills WHERE id = ?", (id,))
        else:
            raise TypeError("Error: id must be of type str or int")
        if self.cursor.rowcount == 0:
            return False
        return True
    
    def get_skills(self, formatted = False):
        res = set()
        self.cursor.execute("SELECT * FROM skills ORDER BY description ASC")
        for skill in self.cursor.fetchall():
            res.add(skill)
        if formatted:
            return ",".join(sorted([skill[1] for skill in res]))
        return res

    def clear_jobs(self):
        self.cursor.execute("DELETE FROM jobs")
        if self.cursor.rowcount == 0:
            return False
        return True
    
    def clear_skills(self):
        self.cursor.execute("DELETE FROM skills")
        if self.cursor.rowcount == 0:
            return False
        return True
    
    def print_jobs_table(self):
        self.cursor.execute("SELECT * FROM jobs")
        for row in self.cursor.fetchall():
            print(row)

    def clean_data(self):
        self.cursor.execute("UPDATE jobs SET wage = wage*160 WHERE wage < 100")
        self.cursor.execute("DELETE FROM jobs WHERE wage > 20000 OR wage < 300")
        self.cursor.execute("UPDATE jobs SET type = 'Full time' WHERE type = 'Full-time'")
        self.cursor.execute("UPDATE jobs SET type = 'Other' WHERE type = 'Temporary jobs'")
        self.cursor.execute('UPDATE jobs SET education = "Bachelor" WHERE education = "Bachelor\'s"')
        self.cursor.execute('UPDATE jobs SET education = "Master" WHERE education = "Master\'s" OR education = "Masters"')
        self.cursor.execute('UPDATE jobs SET education = "High school" WHERE education LIKE "%High school%"')
        self.cursor.execute('UPDATE jobs SET education = "Bachelor" WHERE education LIKE "%Bachelor%"')
        self.cursor.execute('UPDATE jobs SET education = "Master" WHERE education LIKE "%Master%"')
        self.cursor.execute('UPDATE jobs SET education = "Other" WHERE education NOT IN ("Bachelor", "Master", "High school", "Any")')

    def save(self):
        self.con.commit()
    
    def close(self):
        self.con.close()


        
    

def execute(field, domain = "profesia"):
    field = field.strip().lower().replace(" ", "-")
    JS = JobScrapperProfesia()
    db = JobDatabase()
    fields = db.cursor.execute("SELECT DISTINCT field FROM jobs").fetchall()
    if (field,) in fields:
        print("Field already exists")
        return
    job_htmls = JS.scrape_job_offers(field)
    with open("initial_prompt.txt", "r") as f:
        init_prompt = f.read()
    JS.create_chat("sk-proj-d4vZozwVwLAplgX5ixSoT3BlbkFJV12ZImViE0vBzSm8Uyy9", init_prompt)
    incorrect = 0
    for i in range(len(job_htmls)):
        try:
            extracted_info = JS.extract_job_information(job_htmls[i:i+1])
            db.add_data(field, extracted_info)
        except:
            incorrect += 1
        print(i, "/", len(job_htmls))
    print("Incorrect:", incorrect)
    db.clean_data()
    db.save()
    db.close()


    
