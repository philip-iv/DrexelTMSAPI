from requests.adapters import HTTPAdapter
from requests.packages.urllib3.poolmanager import PoolManager
import ssl
from bs4 import BeautifulSoup
import requests
import sys
import sqlite3
import threading

url = "https://duapp2.drexel.edu/webtms_du/app"


#hack TLSv1 adapter
class TLSv1Adapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(num_pools=connections,
                                       maxsize=maxsize,
                                       block=block,
                                       ssl_version=ssl.PROTOCOL_TLSv1)


session = None


def create_session():
    global session
    #create session using tlsv1 because Drexel is in the past
    session = requests.Session()
    session.mount('https://', TLSv1Adapter())


def get_term_number(term):
    tms_main = BeautifulSoup(session.get(url).text, "lxml")
    term_list = tms_main.find("select", id="term", class_="formField")
    for option in term_list.find_all("option"):
        if option.getText() == term:
            return option['value']


def get_search_data(term, name='', number='', crn=''):
    return {
        'formids': 'term,courseName,crseNumb,crn',
        'component': 'searchForm',
        'page': 'Home',
        'service': 'direct',
        'session': 'T',
        'submitmode': 'submit',
        'submitname': '',
        'term': get_term_number(term),
        'courseName': name,
        'crseNumb': number,
        'crn': crn
    }


def parse_row(tablerow):
    data = tablerow.findAll("td")
    listing = {
        'subj': data[0].getText(),
        'number': data[1].getText(),
        'type': data[2].getText(),
        'sec': data[3].getText(),
        'CRN': data[4].getText(),
        'title': data[5].getText(),

        'instructor': data[7].getText(),
    }
    return listing


def search(term, name="", crn="", number=""):
    #gotta have some search term
    if name == "" and crn == "" and number == "":
        return []

    #connect and get the results page
    data = get_search_data(term, name=name, crn=crn, number=number)
    r = session.post(url, data, cookies={'JSESSIONID': '85954D362E769EF49690130F3E55DABD'})
    result = BeautifulSoup(r.text, "lxml")

    #check to make sure session is still good
    if result.title.get_text() == "Stale Session":
        print "Session is stale. Please provide new session ID"
        sys.exit(-1)

    #parse the results
    table = result.find("table", bgcolor="cccccc")
    rows = table.find_all("tr", recursive=False)
    results = []
    for tr in rows:
        if tr.find("td").get_text() == "Subject Code":
            continue
        try:
            row = parse_row(tr)
            results.append(row)
        except: #last row causes an issue, because it's just filler
            continue
    return results

class scrapeThread(threading.Thread):
    def __init__(self, classnum, db):
        threading.Thread.__init__(self)
        self.classnum = classnum
        self.cursor = db.cursor()
    def run(self):
        for i in range(self.classnum * 100, self.classnum * 100 + 100):
            results = search("Fall Quarter 16-17", number=i)
            for c in results:
                print c
                #tuple = (c['CRN'], c['subj'], c['number'], c['type'])
                #self.cursor.execute("INSERT OR REPLACE INTO D201615 VALUES (?, ?, ?, ?)", tuple)
            print i

if __name__ == "__main__":
    db = sqlite3.connect('classes.db', check_same_thread=False)
    cursor = db.cursor()
    #cursor.execute("CREATE TABLE D201615(CRN int PRIMARY KEY, subj string, number int, type string);")
    create_session()
    for i in xrange(0, 10):
        newThread = scrapeThread(i, db)
        newThread.start()
    db.commit()
