import json
import os
import random
import time
import codecs
import bibtexparser
import pandas as pd
import base64
import numpy as np
import psycopg2
import psycopg2.extras

from datetime import datetime
from urllib.request import urlopen

# from selenium import webdriver
from seleniumwire import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.remote import remote_connection
from scraper.recaptcha_solver import recaptcha_solver


# Sets up the webdriver on the selenium grid machine.
# The grid ochestrates the tests on the various machines that are setup.
# We only setup the chrome instaled machine for the scraper.
def driver_setup():

    # Set User Agent and chrome option
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36"
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless=new")
    # chrome_options.add_argument("window-size=1920,1080")
    # chrome_options.add_argument(f"user-agent={USER_AGENT}")
    # chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    # chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    # chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_experimental_option(
        "prefs",
        {
            "download.prompt_for_download": False,  # To auto download the file
            # "download.default_directory": download_path,
            "plugins.always_open_pdf_externally": True,  # It will not show PDF directly in chrome
            "credentials_enable_service": False,  # gets rid of password saver popup
            "profile.password_manager_enabled": False,  # gets rid of password saver popup
        },
    )

    # Oxylabs proxy settings
    PROXY_USER = os.getenv("PROXY_USER", None)
    PROXY_PASSWORD = os.getenv("PROXY_PASSWORD", None)
    PROXY_URL = os.getenv("PROXY_URL", None)

    service = Service(executable_path=ChromeDriverManager().install())
    proxies = chrome_proxy(PROXY_USER, PROXY_PASSWORD, PROXY_URL)
    driver = webdriver.Chrome(
        service=service, 
        options=chrome_options, 
        seleniumwire_options=proxies
    )

    return driver

def chrome_proxy(user: str, password: str, endpoint: str) -> dict:
    wire_options = {
        "proxy": {
            "http": f"http://{user}:{password}@{endpoint}",
            "https": f"https://{user}:{password}@{endpoint}",
        }
    }

    return wire_options

def db_setup():
    global connection, cursor

    # db connection
    connection = psycopg2.connect(
        database = "masterlist",
        user = "admin",
        password = "",
        host = "localhost",
        port = "5432"
    )

    cursor = connection.cursor(cursor_factory = psycopg2.extras.RealDictCursor)


def get_masterlist_state():
    
    ## all journals
    sql = 'SELECT count(*) from api_journal'
    cursor.execute(sql) 

    journals_count = dict(cursor.fetchone())['count']

    ## unscraped journals
    sql = 'SELECT count(*) from api_journal WHERE "numberOfIssuesScraped" = 0'
    cursor.execute(sql) 

    unscraped_journals_count = dict(cursor.fetchone())['count']

    ## being scraped journals
    sql = 'SELECT count(*) from api_journal WHERE "numberOfIssuesScraped" > 0 AND "numberOfIssues" > "numberOfIssuesScraped"'
    cursor.execute(sql) 

    scraping_journals_count = dict(cursor.fetchone())['count']

    ## scraped journals
    sql = 'SELECT count(*) from api_journal WHERE "numberOfIssuesScraped" > 0 AND "numberOfIssues" = "numberOfIssuesScraped"'
    cursor.execute(sql) 

    scraped_journals_count = dict(cursor.fetchone())['count']

    return (
        journals_count,
        unscraped_journals_count,
        scraping_journals_count,
        scraped_journals_count,
    )


def print_masterlist_state():

    (
        journals_count,
        unscraped_journals_count,
        scraping_journals_count,
        scraped_journals_count,
    ) = get_masterlist_state()

    print("***  Masterlist State  ***")
    print("Total Journals       : ", journals_count)
    print(
        "Unscraped Journals : ",
        "{0:.0f}%".format(unscraped_journals_count / float(journals_count) * 100),
    )
    print(
        "Scraping Journals  : ",
        "{0:.0f}%".format(scraping_journals_count / float(journals_count) * 100),
    )
    print(
        "Scraped Journals   : ",
        "{0:.0f}%".format(scraped_journals_count / float(journals_count) * 100),
    )
    print("*** -Masterlist State- ***")


# count is the amount of new issues to scrape
# For unlimited count of scraping put a negative number
# This is useful when the scraping task service has a time limit
def scrape_journal(driver, journal, issue_scrape_count=-1):
    journal_url = journal['url']

    print("scrapping journal " + journal['url'])

    directory = os.path.dirname(__file__)

    scrape_start = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
    scraper_log_path = os.path.join(directory, "data/logs/scraper_log.txt")

    load_page(driver, journal_url, issue_scrape_count)

    accept_cookies(driver, journal_url)

    issue_url_list, original_issue_url_list = scrape_issue_urls(driver, journal_url)
    number_of_issues = len(original_issue_url_list)

    if len(issue_url_list) == 0:
        journal['numberOfIssuesScraped'] = number_of_issues
        save_journal(journal, number_of_issues, {})
        return

    count = 0
    # loops through a dataframe of issue urls and captures metadata per issue
    for issue_url in issue_url_list:

        if count == issue_scrape_count:
            break

        downloaded = download_citations(driver, issue_url)

        # if issue not downloadable then reduce number of issues of journal
        if not downloaded:
            number_of_issues = number_of_issues - 1
            save_journal(journal, number_of_issues , {})
            continue
        
        old_name = os.path.join(directory, "data/logs/citations.txt")
        new_name = os.path.join(
            directory, "data/logs/" + issue_url.split("/")[-1] + ".txt"
        )

        # check if page source has the citations
        content = driver.find_element(By.XPATH, "/html/body").text
        if (not content.startswith("JSTOR Citation List")):
            
            files = WebDriverWait(driver, 30, 1).until(get_downloaded_files)
            print("number of downloads: " + str(len(files)))
            print(files[0])

            # get the content of the first file remotely
            content = get_file_content(driver, files[0])

            # save the content in a local file in the working directory
            with open(old_name, "wb") as f:
                f.write(content)
            
            os.rename(old_name, new_name)
            
            citations_data = bibtexparser.parse_file(new_name)
        else:
            citations_data = bibtexparser.parse_string(content)
        
        citations_dicts = []
        for entry in citations_data.entries:
            print(entry.fields_dict)
            print(entry.items()[1:])
            citations_dicts.append(dict((x, y) for x, y in entry.items()[1:]))

        dataframe = pd.DataFrame(citations_dicts)

        save_issue_articles(
            dataframe, journal, issue_url, number_of_issues
        )

        if os.path.exists(new_name): os.remove(new_name)

        count = count + 1

    scrape_end = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")

    # Append log file
    with open(scraper_log_path, "a+") as log:
        log.write("\n")
        log.write("\nJournal: " + journal_url)
        log.write("\nNumber of Issues scraped: " + str(len(issue_url_list)))
        log.write("\nStart time: " + scrape_start)
        log.write("\nEnd time: " + scrape_end)

    return {"message": "Scraped {}".format(journal['journalName'])}


# Downloads the list of journals as a txt from the jstor and returns it as a pandas dataframe
def fetch_journal_data():
    directory = os.path.dirname(__file__)
    url = "https://www.jstor.org/kbart/collections/all-archive-titles?contentType=journals"

    if not os.path.exists(os.path.join(directory, "data/logs")):
        os.makedirs(os.path.join(directory, "data/logs"))

    journal_data_path = os.path.join(directory, "data/logs/journal_data.txt")

    with urlopen(url) as response:
        body = response.read()

    new_data = body.decode('utf-8')
    with open(journal_data_path, encoding="utf-8", mode="w") as file:
        file.write(new_data)

    df = pd.read_csv(journal_data_path, sep="\t")
    os.remove(journal_data_path)

    return df


# Renames the columns and saves into DB if they aren't in already
def update_journal_data():

    journal_data = fetch_journal_data()

    # remove the dash print_identifier
    journal_data["print_identifier"] = journal_data["print_identifier"].str.replace(
        "-", ""
    )

    journal_data["online_identifier"] = journal_data["online_identifier"].str.replace(
        "-", ""
    )

    journal_data.rename(
        columns={
            "publication_title": "journalName",
            "print_identifier": "issn",
            "online_identifier": "altISSN",
            "title_url": "url",
            "date_last_issue_online": "lastIssueDate",
        },
        inplace=True,
    )

    journal_data["issn"].fillna(journal_data["altISSN"], inplace=True)

    sm_journal_data = journal_data[
        ["issn", "altISSN", "journalName", "url", "lastIssueDate"]
    ]

    save_db_journals(sm_journal_data)


def save_db_journals(db_journal_data):

    # get all the records first
    cursor.execute("SELECT * FROM api_journal")

    journal_objects = cursor.fetchall()
    journal_objects = [dict(row) for row in journal_objects]
        
    print("** starting journals update")

    # convert to dict so as to iterate
    # journal_records = db_journal_data.to_dict('records')
    journal_groups = db_journal_data.groupby("issn")

    for record in journal_objects:

        if record['issn'] in journal_groups.groups.keys():
            journal_update = journal_groups.get_group(record['issn'])

            record['lastIssueDate'] = journal_update.iloc[0]["lastIssueDate"]

    # update the records
    if journal_objects:
        print("** doing bulk update **", len(journal_objects))

        columns = journal_objects[0].keys()
        query = 'UPDATE api_journal SET "lastIssueDate" = %(lastIssueDate)s WHERE "journalID" = %(journalID)s'

        cursor.executemany(query,journal_objects)
        connection.commit()
        # psycopg2.extras.execute_values (
        #     cursor, query, journal_objects, template=None, page_size=100
        # )

        print("** after bulk update **")

    print("** doing bulk create")
    journal_records = db_journal_data.to_dict("records")
    
    # create those that aren't there
    journal_data = [
        {
            'altISSN':record["altISSN"],
            'issn':record["issn"],
            'journalName':record["journalName"],
            'url':record["url"],
            'lastIssueDate': record["lastIssueDate"],
            'lastIssueDateScraped': datetime.strftime(datetime.min,'%Y-%m-%d'),
            'numberOfIssues': 0,
            'numberOfIssuesScraped':0,
        }
        for record in journal_records
    ]

    save_many('api_journal',journal_data)

    print("** done journals create ", len(journal_records))

# saves an array of dictionaries for a table
def save_many(table_name, table_data):
    if (table_data):
        columns = table_data[0].keys()
        query = "INSERT INTO {0} ({1}) VALUES ({2}) ON CONFLICT DO NOTHING".format(table_name, ','.join('"' + c +'"' for c in columns),','.join('%(' + c +')s' for c in columns))
        
        cursor.executemany(query,table_data)
        connection.commit()

# Gets a journal that hasn't been scraped at all or with a new issue to be scraped
def get_journals_to_scrape():
    cursor.execute('SELECT * FROM api_journal WHERE "numberOfIssues" > "numberOfIssuesScraped" OR "lastIssueDate" <> "lastIssueDateScraped" ORDER BY random() LIMIT 1')

    journal_objects = cursor.fetchall()
    journal_objects = [dict(row) for row in journal_objects]

    if journal_objects:
        return journal_objects[0]

    return None

def get_journal(journal_id):
    cursor.execute('SELECT * FROM api_journal WHERE "journalID" = {}'.format(journal_id))

    journal_objects = cursor.fetchall()
    journal_objects = [dict(row) for row in journal_objects]

    if journal_objects:
        return journal_objects[0]

    return None


def filter_issues_urls(issue_url_list):
    cursor.execute('SELECT url FROM api_issue WHERE url = ANY (%s)',(issue_url_list,))

    remove_urls = cursor.fetchall()
    remove_urls = [row['url'] for row in remove_urls]

    filtered_list = list(set(issue_url_list) - set(remove_urls))
    return filtered_list


def load_page(driver, journal_url, issue_scrape_count):

    try:
        driver.get(journal_url)
            
        # for request in driver.requests:
        #     print(request.url, request.body)

        time.sleep(2)
        driver.maximize_window()
        WebDriverWait(driver, 5).until(
            expected_conditions.presence_of_element_located(
                (By.XPATH,r"//main[@id='content']")
            )
        )
        print("passed")

    except Exception as e:
        print("Failed to access journal page ")

        # print(driver.page_source)
        directory = os.path.dirname(__file__)
        misc_directory = os.path.join(directory, "misc/")

        recaptcha_solver(driver, 1, misc_directory)


def accept_cookies(driver, journal_url):
    try:
        WebDriverWait(driver, 5).until(
            expected_conditions.element_to_be_clickable(
                (By.XPATH, r"//button[@id='onetrust-accept-btn-handler']")
            )
        )

        driver.find_element(
            By.XPATH, r".//button[@id='onetrust-accept-btn-handler']"
        ).click()
        print("cookies accepted")
    except:
        print("No cookies, continue")

    time.sleep(5)


def scrape_issue_urls(driver, journal_url):

    random.seed(time.time())
    issue_url_list = []

    time.sleep(2)

    # captures the year elements within the decade
    decade_List = driver.find_elements(By.XPATH, r".//div//ol//li")

    # captures the issues of the year element and records the issue url
    for element in decade_List:
        year_list = element.find_elements(
            By.XPATH, r".//ol//li//collection-view-pharos-link"
        )
        temp = element.get_attribute("data-year")
        if temp == None:
            continue
        for item in year_list:
            issue_url = item.get_attribute("href")
            if not issue_url.startswith("http") and not issue_url.startswith("https"):
                issue_url = "https://www.jstor.org" + issue_url
            issue_url_list.append(issue_url)

    # print("issue number before filter: " + str(len(issue_url_list)))
    original_issue_url_list = issue_url_list

    issue_url_list = filter_issues_urls(issue_url_list)

    # print("issue number after filter: " + str(len(issue_url_list)))

    # filter out scraped issues by url
    return issue_url_list, original_issue_url_list


def download_citations(driver, issue_url):
    # time.sleep(5 * random.random())
    driver.get(issue_url)

    print("download citations ", issue_url)

    try:
        # Download Citations
        WebDriverWait(driver, 20).until(
            expected_conditions.element_to_be_clickable(
                (
                    By.XPATH,
                    r".//*[@id='select_all_citations']/span[@slot='label']",
                )
            )
        ).click()

        print("citations 1")

        WebDriverWait(driver, 10).until(
            expected_conditions.element_to_be_clickable((By.ID, "bulk-cite-button"))
        ).click()

        print("citations 2")

        time.sleep(5)

        # click the link to download the bibtex
        WebDriverWait(driver, 5).until(
            expected_conditions.element_to_be_clickable(
                (
                    By.XPATH,
                    r"//*[@id='bulk-citation-dropdown']/mfe-bulk-cite-pharos-dropdown-menu-item[5]",
                )
            )
        ).click()
        
        print("citations 3")

        return True
    except Exception as e:
        print("failed to download citations for ", issue_url)
        print(e)
        # print(driver.page_source)
        directory = os.path.dirname(__file__)
        misc_directory = os.path.join(directory, "misc/")

        success, start_time = recaptcha_solver(driver, 10, misc_directory)

        return success


# This must run atomically
def save_issue_articles(citations_data, journal, issue_url, number_of_issues):

    # print("** columns: ", citations_data.head())

    if "volume" in citations_data:
        citations_data["volume"] = pd.to_numeric(
            citations_data["volume"], errors="coerce"
        ).fillna(0)

    if "number" in citations_data:
        citations_data["number"] = pd.to_numeric(
            citations_data["number"], errors="coerce"
        ).fillna(0)

    journal_data = citations_data.iloc[0].to_dict()

    print(
        "saving citations: "
        + issue_url
        + " number: "
        + str(journal_data.get("volume", ""))
        + " issue: "
        + str(journal_data.get("number", ""))
    )

    # save the issue
    issue, issue_created = save_issue(issue_url, journal, journal_data)

    # if issue was created update the journal
    if issue_created:
        journal['numberOfIssuesScraped'] = journal['numberOfIssuesScraped'] + 1
        save_journal(journal, number_of_issues, journal_data)

    articles_ids, authors_names, article_author_names = save_articles_and_authors(
        citations_data, issue
    )

    save_article_author_relations(articles_ids, authors_names, article_author_names)

def save_issue(issue_url, journal, journal_data):
    issue_id = issue_url.rsplit("/", 1)[-1]
    issue_created = True
    
    issue = get_issue(issue_url)
    if issue:
        issue_created = False

    if (not issue):
        issue_details = {
                "journal_id": journal["journalID"],
                "issueJstorID": issue_id,
                "url": issue_url,
                "volume": journal_data.get("volume", "0"),
                "number": journal_data.get("number", "0"),
                "year": journal_data["year"],
            }
        
        save_many('api_issue',[issue_details])

        issue = get_issue(issue_url)

    return issue, issue_created


def get_issue(issue_url):
    cursor.execute('SELECT * FROM api_issue WHERE "url" = \'{}\''.format(issue_url))

    issue_objects = cursor.fetchall()
    issue_objects = [dict(row) for row in issue_objects]

    if issue_objects:
        return issue_objects[0]
    
    return None

def save_journal(journal, number_of_issues, journal_data):
    number_of_issues_scraped = journal['numberOfIssuesScraped']

    print(
        "number of issues: "
        + str(number_of_issues)
        + " number of issues scraped: "
        + str(number_of_issues_scraped)
    )

    journal['numberOfIssues'] = number_of_issues

    if number_of_issues <= number_of_issues_scraped:
        journal['numberOfIssuesScraped'] = number_of_issues
        journal['lastIssueDateScraped'] = journal['lastIssueDate']
    else:
        journal['numberOfIssuesScraped'] = number_of_issues_scraped
        if "year" in journal_data:
            journal['lastIssueDateScraped'] = journal_data["year"] + "-01-01"

    query = 'UPDATE api_journal SET "numberOfIssuesScraped" = %(numberOfIssuesScraped)s, "lastIssueDateScraped" = %(lastIssueDateScraped)s WHERE "journalID" = %(journalID)s'

    cursor.executemany(query, [journal])
    connection.commit()

def save_articles_and_authors(citations_data, issue):

    article_records = citations_data.to_dict("records")

    article_author_names = {}

    articles = []
    authors = []

    articles_ids = []
    authors_names = []

    for record in article_records:

        if not "title" in record:
            continue

        if record["title"] == "Front Matter" or record["title"] == "Back Matter":
            continue

        articles.append(
            {
                "issue_id":issue["issueID"],
                "articleJstorID":record["ID"],
                "title":record["title"],
                "abstract":record.get("abstract", ""),
                "articleURL":record.get("url", None),
            }
        )

        articles_ids.append(record.get("ID", ""))

        try:
            if record.get("author"):

                names = [x.strip() for x in record.get("author").split("and")]
                article_author_names[record.get("ID", "")] = names

                for name in names:
                    authors.append({"authorName":name})

                    authors_names.append(name)
        except:
            pass

    # save articles and authors
    save_many('api_article',articles)
    save_many('api_author',authors)

    print("completed bulk author and article save")

    return articles_ids, authors_names, article_author_names

def save_article_author_relations(articles_ids, authors_names, article_author_names):

    print("saving article author relations")

    cursor.execute('SELECT * FROM api_article WHERE "articleJstorID" = ANY (%s)',(articles_ids,))
    saved_articles = cursor.fetchall()
    saved_articles = [dict(row) for row in saved_articles]

    cursor.execute('SELECT * FROM api_author WHERE "authorName" = ANY (%s)',(authors_names,))
    saved_authors = cursor.fetchall()
    saved_authors = [dict(row) for row in saved_authors]

    authors_dict = {}
    for author in saved_authors:
        authors_dict[author['authorName']] = author

    article_authors = []

    # link articles and authors
    for article in saved_articles:
        if article['articleJstorID'] in article_author_names:
            author_names = article_author_names[article['articleJstorID']]

            for name in author_names:
                # print("article id: "+str(article.articleID)+" author id: "+str(author.authorID))
                author = authors_dict[name]
                article_authors.append(
                    {
                        "article_id":article['articleID'], "author_id":author['authorID']
                    }
                )

    save_many('api_article_authors',article_authors)

    print("completed article author relations")


def get_downloaded_files(driver):
    if not driver.current_url.startswith("chrome://downloads"):
        driver.get("chrome://downloads/")

    execute_result = driver.execute_script(
        "return  document.querySelector('downloads-manager')  "
        " .shadowRoot.querySelector('#downloadsList')         "
        " .items.filter(e => e.state === 'COMPLETE')          "
        " .map(e => e.filePath || e.file_path || e.fileUrl || e.file_url); "
    )

    print(execute_result)
    
    return execute_result


def get_file_content(driver, path):
    elem = driver.execute_script(
        "var input = window.document.createElement('INPUT'); "
        "input.setAttribute('type', 'file'); "
        "input.hidden = true; "
        "input.onchange = function (e) { e.stopPropagation() }; "
        "return window.document.documentElement.appendChild(input); "
    )

    elem._execute("sendKeysToElement", {"value": [path], "text": path})

    result = driver.execute_async_script(
        "var input = arguments[0], callback = arguments[1]; "
        "var reader = new FileReader(); "
        "reader.onload = function (ev) { callback(reader.result) }; "
        "reader.onerror = function (ex) { callback(ex.message) }; "
        "reader.readAsDataURL(input.files[0]); "
        "input.remove(); ",
        elem,
    )

    if not result.startswith("data:"):
        raise Exception("Failed to get file content: %s" % result)

    return base64.b64decode(result[result.find("base64,") + 7 :])


def save_current_page(path, driver):
    # open file in write mode with encoding
    f = codecs.open(path, "w", "utf−8")
    # obtain page source
    h = driver.page_source
    # write page source content to file
    f.write(h)
