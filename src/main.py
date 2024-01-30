import os

from scraper import scraper

scraper.db_setup()

driver = scraper.driver_setup()

scraper.update_journal_data()

scraper.print_masterlist_state()

journal = scraper.get_journals_to_scrape()

if journal is None:
    print("Found no journals to scrape")

# number of scraped issues currently
scraped_issues = journal['numberOfIssuesScraped']

# number of issues to scrape
issue_scrape_count = int(os.getenv("ISSUE_SCRAPE_COUNT", "25"))

scraper.scrape_journal(driver, journal, issue_scrape_count)

# quit driver
driver.quit()

journal = scraper.get_journal(journal['journalID'])

# number of scraped newly scraped issues
new_scraped_issues = journal['numberOfIssuesScraped'] - scraped_issues

print(
    "scraped "
    + str(new_scraped_issues)
    + " issues for the journal '"
    + journal['journalName']
    + "'"
)
