import os
import time
import traceback
from datetime import datetime

from pymongo import MongoClient

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.by import By

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
# from webdriver_manager.chrome import ChromeDriverManager

# set global variables
next_page = True
base_url = "https://www.property24.com/for-sale/western-cape/9/p"
category = "?PropertyCategory=House%2cApartmentOrFlat%2cTownhouse"
page_number = 1


def set_local_chrome_driver():
    # Set User Agent and chrome option
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36"
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("headless")
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

    # TOR network proxy in case of scraper blocks
    PROXY = os.getenv("PROXY",None)
    # PROXY = '34.172.116.14:8118'
    if (PROXY):
        chrome_options.add_argument('--proxy-server=%s' % PROXY)

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
        # "mongodb://localhost:27017",
    )
    client = MongoClient(mongodbUri)
    db = client.get_database("property24-data")
    return db


def server_timeout(listing_url, sleep_time):
    max_attempts = 3
    attempts = 0
    while attempts <= max_attempts:
        # go to the listing page
        driver.get(listing_url)
        try:
            WebDriverWait(driver, 2).until(
                EC.presence_of_element_located(
                    (By.XPATH, r"//*[@class='navbar-brand']")
                )
            )
            break
        except:
            print("server timeout failure, wait 2 mins. URL: " + listing_url)
            time.sleep(sleep_time)
            attempts += 1
    else:
        raise


def get_listing_details(listing_url):

    # try to avoid server timeout
    time.sleep(2)

    # server timeout
    server_timeout(listing_url, 120)

    # create the listing dictionary
    listing_detail_doc = {"listing_url": listing_url}

    # check if property is available
    not_available = driver.find_elements(By.XPATH, r"//*[@class='col-12']/h2")
    not_found = driver.find_elements(By.XPATH, r"//*[@class='col-6']/h1")


    if not_available or not_found:
        print("property no longer available")
        return

    # accept the cookies
    try:
        cookies = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, r"//*[@id='cookieBannerClose']"))
        )

        cookies.click()
    except:
        print("no cookies")

    # get description and update dictionary
    # time.sleep(2)
    try:
        overview = driver.find_element(By.XPATH, r"//*[@class='p24_mBM']/h1").text
    except:
        overview = None

    listing_detail_doc["Overview"] = overview

    # get agent and update dictionary
    # time.sleep(2)
    try:
        agent_name = driver.find_element(
            By.XPATH, r"//*[@class='p24_listingCard']/a/span"
        ).text
    except:
        agent_name = None

    listing_detail_doc["Agent Name"] = agent_name

    # get summary data and update dictionary
    # only left panel summary data added
    summary_els = WebDriverWait(driver, 1).until(
        EC.presence_of_all_elements_located(
            (
                By.XPATH,
                 r"//*[contains(@class, 'p24_keyFeaturesContainer')]//*[@class='p24_listingFeatures']",
            )
        )
    )

    for summary_el in summary_els:
        key = (
            WebDriverWait(summary_el, 1)
            .until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        r".//*[@class='p24_feature']",
                    )
                )
            )
            .text
        )
        
        try:
            value = (
                WebDriverWait(summary_el, 1)
                .until(
                    EC.presence_of_element_located(
                        (
                            By.XPATH,
                            r".//*[@class='p24_featureAmount']",
                        )
                    )
                )
                .text
            )
        except Exception as e:
            value = True

        value = get_typed_value(value)

        listing_detail_doc[key.split(":")[0]] = value

    # get property details data and update dictionary
    # expand all panels

    panel_els = WebDriverWait(driver, 2).until(
        EC.presence_of_all_elements_located(
            (
                By.XPATH,
                r"//*[@class='panel']",
            )
        )
    )

    get_panel_data(panel_els[0], listing_detail_doc)

    listing_details_col.insert_one(listing_detail_doc)

    print("updated listing_details_col collection")


def get_typed_value(value):
    if type(value) != bool:
        # try make value into integer
        try:
            value = int(value)
            return value
        except Exception as e:
            pass
        try:
            value = int(value[1:].replace(" ", ""))
            return value
        except Exception as e:
            pass
        try:
            value = int(value[:-2].replace(" ", ""))
            return value
        except Exception as e:
            pass
        try:
            value = datetime.strptime(value,'%d %B %Y')
            return value
        except Exception as e:
            pass
    return value

def get_panel_data(panel_el, listing_detail_doc):
    # time.sleep(2)
    panel_el.click()

    panel_heading = panel_el.find_element(
        By.XPATH, r".//*[contains(@class, 'panel-heading')]"
    ).text

    # time.sleep(2)
    detail_els = panel_el.find_elements(
        By.XPATH, r".//*[@class='row p24_propertyOverviewRow']"
    )

    if detail_els:
        for detail_el in detail_els:
            # get data label
            key = detail_el.find_element(
                By.XPATH, r".//*[@class='col-6 p24_propertyOverviewKey']"
            ).text
            try:
                # get data value (text field)
                value = detail_el.find_element(
                    By.XPATH, r".//*[@class='p24_info']"
                ).text
            except:
                # get data value (date field)
                value = detail_el.find_element(
                    By.XPATH,
                    r".//*[@class='js_displayMap p24_addressPropOverview']",
                ).text

            value = get_typed_value(value)
            
            if panel_heading.lower() == 'property overview':
                listing_detail_doc[key] = value
            else:
                if panel_heading not in listing_detail_doc:
                    listing_detail_doc[panel_heading] = {}
                listing_detail_doc[panel_heading][key] = value
    else:
        get_points_of_interest(panel_el, listing_detail_doc)

def get_points_of_interest(panel_el, listing_detail_doc):
    # get points of interest information
    panel_el_details = panel_el.find_element(
        By.XPATH, r".//*[@id='P24_pointsOfInterest']"
    )

    # scroll to element to avoid error
    ActionChains(driver).move_to_element(panel_el_details).perform()

    point_of_int_els = driver.find_elements(
        By.XPATH, r".//*[@class='js_P24_POICategory p24_poiCategory']"
    )

    for point_of_int_el in point_of_int_els:
        try:
            time.sleep(2)
            # click on view more
            view_more_el = WebDriverWait(point_of_int_el, 5).until(
                EC.element_to_be_clickable(
                    (By.XPATH, r".//*[@class='col-12']/a")
                )
            )
            view_more_el.click()
        except:
            print("\nNo view more")

        # get the category name
        time.sleep(1)
        category = point_of_int_el.find_element(
            By.XPATH, r".//*[@class='p24_semibold']"
        ).text

        location_elements = point_of_int_el.find_elements(
            By.XPATH, r".//*[@class='col-6']"
        )

        distance_elements = point_of_int_el.find_elements(
            By.XPATH, r".//*[@class='col-6 noPadding p24_semibold']"
        )

        if "Points of interest" not in listing_detail_doc:
            listing_detail_doc["Points of interest"] = {}

        if category not in listing_detail_doc["Points of interest"]:
            listing_detail_doc["Points of interest"][category] = {}

        poi_doc = listing_detail_doc["Points of interest"][category]

        for location_element, distance_element in zip(
            location_elements[1:], distance_elements
        ):
            key = location_element.text
            value = distance_element.text

            if key not in poi_doc:
                poi_doc[key] = []

            poi_doc[key].append(value)

def delete_duplicates():
    fields_to_check = ['listing_url']  # Add the field names you want to check

    for field in fields_to_check:
        # Find duplicate values
        pipeline = [
            # { "$limit" : 40000 },
            {
                "$group": {
                    "_id": f"${field}",
                    "count": {"$sum": 1},
                    "duplicates": {"$push": "$_id"}
                }
            },
            {
                "$match": {
                    "count": {"$gt": 1}
                }
            }
        ]

        duplicates = list(listing_details_col.aggregate(pipeline))

        if (len(duplicates) == 0):
            break

        # Iterate over duplicate values and delete the records
        for duplicate in duplicates:
            duplicate_ids = duplicate['duplicates'][1:]  # Keep one, delete others
            listing_details_col.delete_many({"_id": {"$in": duplicate_ids}})

# initialise the driver
driver = set_local_chrome_driver()

# establish connection with the database
print("connecting db")
db = connect_db()

# get the listing_url collection
listings_col = db.get_collection("listings")

listing_details_col = db.get_collection("listing_details")
listing_details_col.create_index([("listing_url")], unique=True)

loop_times = int(os.getenv("loopTimes", "10"))

for i in range(loop_times):
    try:
        print("scraping listing: " + str(i + 1) + "/" + str(loop_times))

        # Find and update one document that matches the query
        listing_url = listings_col.find_one_and_update(
            {"scraped": False}, {"$set": {"scraped": True, "completed": False}}
        )

        if listing_url is None:
            listing_url = listings_col.find_one({"completed": False})

        if listing_url is None:
            print("no more listings to scrape")
            break
        
        if  listing_details_col.count_documents({"listing_url":listing_url["url"]}, limit = 1) == 0:
            get_listing_details(listing_url["url"])

        listings_col.update_many(
            {"url": listing_url["url"]}, {"$set": {"completed": True}}
        )
    except Exception as e:
        # Get the listing_detail_error collection
        listing_detail_error_col = db.get_collection("listing_detail_error")

        error = traceback.format_exc()
        # Create a new document as a Python dictionary
        new_error_doc = {
            "failed_request": listing_url["url"],
            "error": error,
        }

        # Insert the new document into the collection
        listing_detail_error_col.insert_one(new_error_doc)
        
        print("updated listing_detail_error collection")

        listings_col.update_many(
            {"url": listing_url["url"]}, {"$set": {"completed": True}}
        )
        
