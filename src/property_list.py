import os

from datetime import date
from pymongo import MongoClient, ReturnDocument, UpdateOne

from selenium import webdriver
from selenium.webdriver.common.by import By
# from webdriver_manager.chrome import ChromeDriverManager

# set global variables
next_page = True
base_url = os.getenv("base_url","https://www.property24.com/for-sale/western-cape/9")
# base_url = os.getenv("base_url","https://www.property24.com/for-sale/mowbray/cape-town/western-cape/8677")
# base_url = os.getenv("base_url","https://www.property24.com/for-sale/constantia/cape-town/western-cape/11742")

categories = os.getenv("categories","House,ApartmentOrFlat,Townhouse")
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

def get_page_data(page_url):
    global next_page

    print("page "+str(page_number))

    # go to the page url
    driver.get(page_url)

    listings = []

    try:
        # find the list of listed properties
        listing_results = driver.find_elements(
            By.XPATH,
            r"//*[@class='p24_regularTile js_rollover_container ']/a",
        )

        # Check if there are no listing results
        if not listing_results:
            next_page = False
            return

        # get the listing url and append the listingURLList
        for listing in listing_results:
            if not listing.is_displayed():
                continue
            
            listing_info = get_listing_info(listing)
            listing_changes = get_listing_changes(listing, listing_info)
            
            listing_info.update(listing_changes)
            listings.append(listing_info)

        bulk_update(listings)

        print("updated listings collection")

    except Exception as e:
        if "E11000 duplicate key error" in str(e):
            print(page_url)
            print("Duplicates Found")
            print("Number Inserted: "+str(e.details["nInserted"]))
        else:
            print("Error on page " + str(page_url) + " " + str(e))

''' 
Gets the listings and does an upsert.
If a listing already exists, any new fields will be added. 
Old fields will be ignored i.e. NOT updated but IGNORED
'''
def bulk_update(listings):
        
        bulk_update = []
        for listing in listings:
            bulk_update.append(
                UpdateOne(
                    {"url": listing["url"]}, 
                    [{"$set": listing}],
                    upsert=True)
            )
        
        db.listings.bulk_write(bulk_update, ordered=False)

''' Gets any changes to the listing such as Offer, Reduction, Sold '''
def get_listing_changes(listing, listing_info):
    changes_results = listing.find_elements(
            By.XPATH,
            r".//ul[@class='hidden-print p24_Gallerybadge']/li",
        )
    
    changes_dict = {}
    for change in changes_results:
        change_text = (change.text).lower().replace(' ', '_')
        if change_text in ['under_offer','reduced','sold']:
            price = listing_info["price"]["$cond"]["then"]
            changes_dict[change_text+"."+price] = str(date.today())
    
    return changes_dict

''' Gets the info of the listing like province, listingID, etc '''
def get_listing_info(listing):
    url = listing.get_attribute("href")
    listing_locale = url.split("/")[-5:]

    listing_price = listing.find_element(
            By.XPATH,
            r".//span[@class='p24_price']",
        ).get_attribute('content')
    
    try:
        listing_currency = listing.find_element(
                By.XPATH,
                r".//meta[@itemProp='priceCurrency']",
            ).get_attribute('content')
    except Exception as e:
        listing_currency = ""

    listing_badges = listing.find_elements(
            By.XPATH,
            r".//ul[@class='p24_badges']/li",
        )

    listing_info = {
            "url": url,
            "price": get_conditional_set("price",listing_price),
            "currency": listing_currency,
            "scraped": get_conditional_set("scraped",False),
            "suburb":listing_locale[0],
            "town":listing_locale[1],
            "province":listing_locale[2]
        }
    
    for listing_badge in listing_badges:
        badge = (listing_badge.text).lower()
        if not badge:
            continue
        listing_info["badges."+badge] = True

    return listing_info

''' 
Returns a condition for setting the field.
If the field does not exist it will be SET otherwise it will remain UNCHANGED
'''
def get_conditional_set(field_name, field_value):
    return {"$cond": {
                'if':{"$eq": [{"$type": "$"+field_name}, "missing"]},
                'then': field_value,
                'else': "$"+field_name
        }}

# initialise the driver
driver = set_local_chrome_driver()

# establish connection with the database
print("connecting db")
db = connect_db()

# get the url collection
listing_col = db.get_collection("listings")
listing_col.create_index([("url")], unique=True)

# get the page tracker 
listings_page_tracker_col = db.get_collection("listings_page_tracker")
listings_page_tracker_col.create_index([("url")], unique=True)

while next_page:
    try:
        page_tracker = listings_page_tracker_col.find_one_and_update(
            {"url": base_url, "date":str(date.today()), "completed":False}, {"$inc": { 'page': 1 }}, upsert=True, return_document=ReturnDocument.AFTER
        )
    except Exception as e:
        print("Listings Scraping Completed")
        break

    page_number = page_tracker["page"]

    page_url = f"{base_url}/p{page_number}?PropertyCategory={categories}"
    # page_url = f"{base_url}/p{page_number}?sp=pt%3d800000&PropertyCategory={categories}"
    # page_url = f"{base_url}/p{page_number}?sp=pf%3d900000%26pt%3d1000000&PropertyCategory={categories}"

    get_page_data(page_url)

    # If there is no next page reset
    if not next_page:
        page_tracker = listings_page_tracker_col.find_one_and_update(
            {"url": base_url,"date":str(date.today())}, {"$set":{"page": 0,"completed": True}}
        )
    

