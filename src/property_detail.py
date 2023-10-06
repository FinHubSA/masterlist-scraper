import os
import time

from pymongo import MongoClient

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.by import By

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

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
    listing_details_col = db.get_collection("listing_details")

    driver.get(listing_url)

    listing_detail_doc = {"listing_url": listing_url}

    # get the price
    price = driver.find_element(
        By.XPATH, r"//*[@class='p24_mBM']//*[@class='p24_price']"
    ).text

    listing_detail_doc["Price"] = price

    # get agent
    try:
        agent_name = driver.find_element(
            By.XPATH, r"//*[@class='p24_listingCard']/a/span"
        ).text
    except:
        agent_name = None

    listing_detail_doc["Agent Name"] = agent_name

    # get summary data
    summary_els = driver.find_elements(
        By.XPATH,
        r"//*[@class='p24_keyFeaturesContainer']//*[@class='p24_listingFeatures']",
    )

    for summary_el in summary_els:
        key = summary_el.find_element(By.XPATH, r".//*[@class='p24_feature']").text
        value = summary_el.find_element(
            By.XPATH, r".//*[@class='p24_featureAmount']"
        ).text

        listing_detail_doc[key.split(":")[0]] = value

    # get property details data
    # expand all panels
    panel_els = driver.find_elements(By.XPATH, r"//*[@class='panel']")

    for panel_el in panel_els:
        time.sleep(1)
        panel_el.click()

        time.sleep(2)
        detail_els = panel_el.find_elements(
            By.XPATH, r".//*[@class='row p24_propertyOverviewRow']"
        )

        if detail_els:
            for detail_el in detail_els:
                # get label
                key = detail_el.find_element(
                    By.XPATH, r".//*[@class='col-6 p24_propertyOverviewKey']"
                ).text
                try:
                    # get value for text
                    value = detail_el.find_element(
                        By.XPATH, r".//*[@class='p24_info']"
                    ).text
                except:
                    # get value for date
                    value = detail_el.find_element(
                        By.XPATH,
                        r".//*[@class='js_displayMap p24_addressPropOverview']",
                    ).text

                listing_detail_doc[key] = value
        else:
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

    print(listing_detail_doc)

    listing_details_col.insert_one(listing_detail_doc)

    print("updated listing_details_col collection")


# initialise the driver
driver = set_local_chrome_driver()

# establish connection with the database
print("connecting db")
db = connect_db()

# get the listing_url collection
listing_url_col = db.get_collection("listing_url")

# loop_times = int(os.getenv("loopTimes", "1"))

# for i in range(loop_times):
#     print("scraping listing: " + str(i + 1) + "/" + str(loop_times))

#     # Find and update one document that matches the query
#     listing_url = listing_url_col.find_one_and_update(
#         {"scraped": False}, {"$set": {"scraped": True}}
#     )

# get_listing_details(listing_url["listing_url"])
get_listing_details(
    "https://www.property24.com/for-sale/vredekloof-east/brackenfell/western-cape/16641/113406616"
)
