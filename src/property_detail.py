import os

from pymongo import MongoClient

from selenium import webdriver
from selenium.webdriver.common.by import By

# set global variables
next_page = True
base_url = "https://www.property24.com/for-sale/western-cape/9/p"
category = "?PropertyCategory=House%2cApartmentOrFlat%2cTownhouse"
page_number = 1


def set_local_chrome_driver():
    # Set User Agent and chrome option
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36"
    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("headless")
    chrome_options.add_argument("window-size=1920,1080")
    chrome_options.add_argument(f"user-agent={USER_AGENT}")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_experimental_option(
        "prefs",
        {
            "download.prompt_for_download": False,  # To auto download the file
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,  # It will not show PDF directly in chrome
            "credentials_enable_service": False,  # gets rid of password saver popup
            "profile.password_manager_enabled": False,  # gets rid of password saver popup
        },
    )

    # Start driver
    driver = webdriver.Chrome(
        # ChromeDriverManager().install(),
        options=chrome_options,
    )

    return driver


def connect_db():
    mongodbUri = os.getenv(
        "mongodb_uri",
        "mongodb://danaebouwer:kM8L8hQJYyrA0DkX@ac-6emdxtn-shard-00-00.yzat8l0.mongodb.net:27017,ac-6emdxtn-shard-00-01.yzat8l0.mongodb.net:27017,ac-6emdxtn-shard-00-02.yzat8l0.mongodb.net:27017/?replicaSet=atlas-11gfrx-shard-0&ssl=true&authSource=admin",
    )
    client = MongoClient(mongodbUri)
    db = client.get_database("property24-data")
    return db


def get_listing_details(listing_url):
    driver.get(listing_url)


# initialise the driver
driver = set_local_chrome_driver()

# establish connection with the database
print("connecting db")
db = connect_db()

# get the listing_url collection
listing_url_col = db.get_collection("listing_details")
