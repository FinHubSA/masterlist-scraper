import os

from datetime import datetime, date
from pymongo import MongoClient, ReturnDocument, UpdateOne

from selenium import webdriver
from selenium.webdriver.common.by import By
# from webdriver_manager.chrome import ChromeDriverManager

# set global variables
next_page = True
base_url = os.getenv("base_url","https://www.property24.com/for-sale/western-cape/9")
# base_url = os.getenv("base_url","https://www.property24.com/for-sale/mowbray/cape-town/western-cape/8677")
# base_url = os.getenv("base_url","https://www.property24.com/for-sale/whispering-pines/gordons-bay/western-cape/16516")

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

def get_page_data(page_url):
    global next_page

    print("page "+str(page_number))

    # go to the page url
    # driver.get("https://api.ipify.org?format=json")
    driver.get(page_url)

    # print(driver.page_source)
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
            
            try:
                listing_info = get_listing_info(listing)
                listing_changes = get_listing_changes(listing)
                
                listing_info.update(listing_changes)
                listings.append(listing_info)
            except Exception as e:
                pass

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
def get_listing_changes(listing):
    changes_results = listing.find_elements(
            By.XPATH,
            r".//ul[@class='hidden-print p24_Gallerybadge']/li",
        )
    
    changes_dict = {}
    for change in changes_results:
        change_text = (change.text).lower().replace(' ', '_')
        if change_text in ['under_offer','reduced','sold']:
            changes_dict[change_text] = get_conditional_set(change_text, datetime.combine(date.today(), datetime.min.time()))
    
    return changes_dict

''' Gets the info of the listing like province, listingID, etc '''
def get_listing_info(listing):
    url = listing.get_attribute("href")

    listing_locale = url.split("/")[-5:]

    listing_price = listing.find_element(
            By.XPATH,
            r".//span[@class='p24_price']",
        ).get_attribute('content')
    
    listing_price = int(listing_price)
    
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
            "current_price": listing_price,
            "currency": listing_currency,
            "scraped": get_conditional_set("scraped",False),
            "suburb":listing_locale[0],
            "town":listing_locale[1],
            "province":listing_locale[2],
            "suburb_id": int(listing_locale[3])
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
    return {"$cond": 
        {
            'if':{"$eq": [{"$type": "$"+field_name}, "missing"]},
            'then': field_value,
            'else': "$"+field_name
        }
    }

def insert_suburb_ids():
    listings = listings_col.find({"suburb_id":{"$eq":None}})

    bulk_update = []
    for listing in listings:
        url = listing["url"]
        listing_locale = url.split("/")[-5:]
        suburb_id = listing_locale[3]

        bulk_update.append(
            UpdateOne(
                {"url": listing["url"]}, 
                [{"$set": {"suburb_id": int(suburb_id)}}])
        )
    
    db.listings.bulk_write(bulk_update, ordered=False)

'''
Rename price -> listing_price
New field -> current price (shows if it was reduced)
Reduced, Under-offer, Sold will now just be dates
'''
def refactor_data():
    listings = listings_col.find(
        # {"url":"https://www.property24.com/for-sale/gordons-bay-central/gordons-bay/western-cape/7833/113453405"}
        )

    bulk_update = []
    for listing in listings:
        
        updates = []

        date_str = '1900-01-01'
        current_date = datetime.strptime(date_str, '%Y-%m-%d')
        current_price = listing["current_price"]

        if ("reduced" in listing and isinstance(listing["reduced"], dict)):

            for price in listing["reduced"]:
                price_date = datetime.strptime(listing["reduced"][price], '%Y-%m-%d')

                if (current_date < price_date):
                    current_date = price_date
                    current_price = price

                    updates.append({"$set": {"reduced": price_date}})

        if ("under_offer" in listing and isinstance(listing["under_offer"], dict)):

            for price in listing["under_offer"]:
                price_date = datetime.strptime(listing["under_offer"][price], '%Y-%m-%d')

                if (current_date < price_date):
                    current_date = price_date
                    current_price = price

                    updates.append({"$set": {"under_offer": price_date}})

        if ("sold" in listing and isinstance(listing["sold"], dict)):

            for price in listing["sold"]:
                price_date = datetime.strptime(listing["sold"][price], '%Y-%m-%d')

                if (current_date < price_date):
                    current_date = price_date
                    current_price = price
                    
                    updates.append({"$set": {"sold": price_date}})

        updates.append({"$set": {"current_price": int(current_price)}})

        bulk_update.append(
            UpdateOne({"url": listing["url"]}, updates)
        )
    
    db.listings.bulk_write(bulk_update, ordered=False)

# initialise the driver
driver = set_local_chrome_driver()

# establish connection with the database
print("connecting db")
db = connect_db()

# get the url collection
listings_col = db.get_collection("listings")
listings_col.create_index([("url")], unique=True)

# get the page tracker 
listings_page_tracker_col = db.get_collection("listings_page_tracker")
listings_page_tracker_col.create_index([("url"),("date")], unique=True)

# refactor_data()

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

    get_page_data(page_url)

    # If there is no next page reset
    if not next_page:
        page_tracker = listings_page_tracker_col.find_one_and_update(
            {"url": base_url,"date":str(date.today())}, {"$set":{"page": 0,"completed": True}}
        )
    

