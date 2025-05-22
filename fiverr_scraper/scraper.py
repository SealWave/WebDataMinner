import selenium.webdriver as webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import random
import logging
import csv
import json
import os
from datetime import datetime
import pandas as pd
import argparse # Added for command-line argument parsing
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from selenium.common.exceptions import TimeoutException, WebDriverException

# Setup dedicated logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Constants ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/109.0"
]
PAGE_LOAD_WAIT_SECONDS = random.uniform(8, 12)  # Time to wait for page to load its dynamic content.
MIN_INTER_PAGE_DELAY = 5                        # Minimum delay between fetching subsequent pages (seconds).
MAX_INTER_PAGE_DELAY = 10                       # Maximum delay between fetching subsequent pages (seconds).
OUTPUT_DIR = "output"                           # Directory to save scraped data.
MAX_PAGES_TO_SCRAPE = 2                         # Maximum number of pages to scrape per keyword. Set to a low number for testing.
RETRY_ATTEMPTS = 3                              # Number of retry attempts for fetching a page.
RETRY_WAIT_MIN_SECONDS = 2                      # Minimum wait time for exponential backoff retry.
RETRY_WAIT_MAX_SECONDS = 6                      # Maximum wait time for exponential backoff retry.

@retry(
    stop=stop_after_attempt(RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN_SECONDS, max=RETRY_WAIT_MAX_SECONDS),
    retry=retry_if_exception_type((WebDriverException, TimeoutException)),
    before_sleep=lambda retry_state: logger.info(
        f"Retrying {retry_state.fn.__name__} for keyword '{retry_state.args[1]}' page {retry_state.args[2]} "
        f"due to {retry_state.outcome.exception()}, attempt #{retry_state.attempt_number}"
    )
)
def get_page_html(driver: webdriver.Chrome, keyword: str, page_number: int) -> str | None:
    """
    Fetches the HTML content of a Fiverr search results page for a given keyword and page number.

    Uses an existing WebDriver instance and implements retry logic for robustness.

    Args:
        driver: An initialized Selenium WebDriver instance.
        keyword: The search term to use on Fiverr.
        page_number: The page number of the search results to fetch.

    Returns:
        The HTML content of the page as a string, or None if fetching fails after retries
        or an unexpected error occurs. Returns a minimal HTML string ("<html><body></body></html>")
        if Fiverr indicates no results or an error on their end.

    Raises:
        WebDriverException: If a Selenium-related error occurs that is configured for retry
                            (propagated by tenacity).
        TimeoutException: If a page load times out and is configured for retry
                          (propagated by tenacity).
    """
    if page_number == 1:
        fiverr_search_url = f"https://www.fiverr.com/search/gigs?query={keyword}"
    else:
        fiverr_search_url = f"https://www.fiverr.com/search/gigs?query={keyword}&page={page_number}"
    
    logger.info(f"Attempting to fetch URL: {fiverr_search_url} (Keyword: '{keyword}', Page: {page_number})")
    
    try:
        driver.get(fiverr_search_url)
        # Wait for dynamic content to load. This is a simple fixed wait.
        # More advanced techniques might involve waiting for specific elements to be present.
        logger.info(f"Waiting for page to load... ({PAGE_LOAD_WAIT_SECONDS:.2f} seconds)")
        time.sleep(PAGE_LOAD_WAIT_SECONDS)
        page_html = driver.page_source
        
        # Check for common Fiverr messages indicating no results or errors.
        if "Hmm, something seems to have gone wrong" in page_html or "No services found for your search" in page_html:
            logger.warning(f"Page {page_number} for keyword '{keyword}' appears empty or is an error page (e.g., 'No services found').")
            # Return a minimal HTML structure; parse_gigs will handle this by returning an empty list.
            return "<html><body></body></html>" 
            
        logger.info(f"Successfully fetched HTML for page {page_number} of keyword '{keyword}'.")
        return page_html
    except (WebDriverException, TimeoutException) as e:
        # Log the specific error type that triggered a retry.
        logger.warning(f"A WebDriver/Timeout error occurred while fetching page {page_number} for '{keyword}': {type(e).__name__} - {e}")
        raise # Re-raise the exception for tenacity to handle the retry.
    except Exception as e:
        # Catch any other unexpected errors not covered by tenacity's retry conditions.
        logger.error(f"Unexpected error fetching page HTML for keyword '{keyword}' on page {page_number}: {e}", exc_info=True)
        return None # For these errors, don't retry; return None to signal failure.

def parse_gigs(html_content: str) -> list[dict]:
    """
    Parses gig information from the HTML content of a Fiverr search results page.

    Args:
        html_content: The HTML content of a search results page as a string.

    Returns:
        A list of dictionaries, where each dictionary contains details of a gig
        (e.g., title, seller_name, price). Returns an empty list if no gigs
        are found or if the HTML content is invalid.
    """
    if not html_content:
        logger.warning("HTML content is empty. Cannot parse gigs.")
        return []

    logger.info("Starting to parse HTML content for gigs. Attempting to extract seller country if available on search page.")
    # --- IMPORTANT NOTE ON SELLER COUNTRY ---
    # The selectors used below for 'seller_country' are HYPOTHETICAL and based on common web patterns.
    # They MUST BE VERIFIED by inspecting the live Fiverr website's search results page.
    # If seller country is not available on the search results page, this extraction will consistently yield "N/A",
    # and this note serves as the finding of the investigation.
    # Do NOT fetch individual gig pages to find this information, as per constraints.
    # --- END IMPORTANT NOTE ---
    soup = BeautifulSoup(html_content, 'html.parser')
    gigs_data = []
    
    # Primary CSS selectors for gig cards. These are based on observed patterns and may need updates
    # if Fiverr's site structure changes. Using `data-testid` is often more robust.
    gig_cards = soup.select('div[data-testid="gig-card-layout"], div.gig-card, article.gig-card')
    logger.info(f"Found {len(gig_cards)} potential gig cards using primary selectors.")

    if not gig_cards:
        # Fallback: Try a broader search if specific selectors fail.
        # This looks for 'article' or 'div' tags with class names containing 'gig' and 'card'.
        logger.info("Primary selectors found 0 cards, trying generic fallback selectors.")
        gig_cards = soup.find_all(['article', 'div'], class_=lambda x: x and 'gig' in x.lower() and 'card' in x.lower())
        logger.info(f"Found {len(gig_cards)} cards with fallback selectors.")

    if not gig_cards:
        logger.warning("No gig cards found on the page by any selector. Page might be structured differently or be genuinely empty.")
        return []

    for i, card in enumerate(gig_cards):
        # Initialize a dictionary for each gig's data to ensure all keys are present.
        gig_info = {
            "title": None, "seller_name": None, "seller_level": None, "seller_country": "N/A",
            "price": None, "num_reviews": None, "rating": None, "gig_url": None
        }
        card_identifier = f"Card {i+1}/{len(gig_cards)}" # For logging purposes

        try:
            # Gig Title and URL extraction
            # Selects the first link that seems to be the main gig link/title.
            title_element = card.select_one('a[data-testid="gig-title"], a.gig-title-link, h3 a, a[href*="/gigs/"]')
            if title_element:
                gig_info["title"] = title_element.text.strip()
                gig_url_raw = title_element.get('href')
                if gig_url_raw:
                    # Clean and normalize the URL.
                    # URLs might be relative, so prepend the base Fiverr URL.
                    # Also, strip query parameters (e.g., from '?source=...')
                    if gig_url_raw.startswith('/'):
                        gig_info["gig_url"] = f"https://www.fiverr.com{gig_url_raw.split('?')[0]}"
                    elif gig_url_raw.startswith('http'):
                        gig_info["gig_url"] = gig_url_raw.split('?')[0]
                    else:
                        # Log if an unexpected URL format is encountered.
                        logger.warning(f"[{card_identifier}] Unusual gig URL format: {gig_url_raw}")
                        gig_info["gig_url"] = gig_url_raw # Store as is if unsure.
            else:
                logger.warning(f"[{card_identifier}] Title not found.")

            # Seller Name extraction
            seller_element = card.select_one('a[data-testid="seller-name"], a[href*="/users/"], p.seller-name')
            seller_info_container = None # Will try to find a common parent for seller name and country
            if seller_element:
                gig_info["seller_name"] = seller_element.text.strip()
                # Try to find a parent container that might also hold the country
                # This is a guess; structure varies wildly. Common parents might be 2-3 levels up.
                seller_info_container = seller_element.find_parent('div', class_=lambda x: x and ('seller-info' in x or 'seller-details' in x)) 
                if not seller_info_container:
                    seller_info_container = seller_element.parent # Default to direct parent if specific class not found
            else:
                logger.warning(f"[{card_identifier}] Seller name not found.")

            # Seller Level extraction (e.g., "Top Rated Seller", "Level Two Seller")
            seller_level_element = card.select_one('span[data-testid="seller-level"], span.seller-level')
            if seller_level_element:
                gig_info["seller_level"] = seller_level_element.text.strip()
            else:
                gig_info["seller_level"] = "N/A" 

            # Seller Country Extraction (Hypothetical - MUST BE VERIFIED)
            # Attempt 1: Look for a specific data-testid or class within the card or seller_info_container
            country_element = None
            if seller_info_container: # Prioritize searching within the assumed seller info block
                 country_element = seller_info_container.select_one('span[data-testid*="country"], span[class*="country"], span[class*="location"]')
            if not country_element: # Fallback to searching the whole card
                country_element = card.select_one('span[data-testid*="country"], span[class*="country"], span[class*="location"], div.seller-location span')
            
            if country_element:
                country_text = country_element.text.strip()
                # Sometimes country is prefixed, e.g., "From United States"
                if country_text.lower().startswith("from "):
                    country_text = country_text[5:].strip()
                gig_info["seller_country"] = country_text
            else:
                # Attempt 2: Look for a 'title' attribute on a flag icon (less likely on search page)
                flag_icon = card.select_one('img[class*="flag"], span[class*="flag-icon"]')
                if flag_icon and flag_icon.has_attr('title'):
                    gig_info["seller_country"] = flag_icon['title'].strip()
                else:
                    logger.warning(f"[{card_identifier}] Seller country not found using common selectors or flag icon title.")
                    # gig_info["seller_country"] remains "N/A" as initialized

            # Price extraction
            price_element = card.select_one('span[data-testid="price"], p.price, span[class*="price"]')
            if price_element:
                gig_info["price"] = clean_price(price_element.text.strip())
            else:
                logger.warning(f"[{card_identifier}] Price not found.")

            # Rating and Number of Reviews extraction
            # These are often found together or close by in the HTML.
            rating_review_area = card.select_one('div[data-testid="gig-rating"], span[class*="rating"], div[class*="rating"]')
            if rating_review_area:
                rating_element = rating_review_area.select_one('span[data-testid="star-rating-score"], span.rating-score, b') # 'b' tag for bolded rating
                if rating_element:
                    gig_info["rating"] = clean_rating(rating_element.text.strip())
                else:
                    logger.warning(f"[{card_identifier}] Rating score not found within designated rating area.")

                review_count_element = rating_review_area.select_one('span[data-testid="review-count"], span.rating-count, span[class*="reviews"]')
                if review_count_element:
                    gig_info["num_reviews"] = clean_reviews(review_count_element.text.strip())
                else:
                    logger.warning(f"[{card_identifier}] Review count not found within designated rating area.")
            else: 
                # Fallback if a combined rating/review area isn't found.
                rating_element = card.select_one('span[data-testid="star-rating-score"], span.rating-score, b[class*="rating"]')
                if rating_element:
                    gig_info["rating"] = clean_rating(rating_element.text.strip())
                else:
                    logger.warning(f"[{card_identifier}] Rating score not found (fallback search).")

                review_count_element = card.select_one('span[data-testid="review-count"], span.rating-count, span[class*="reviews"]')
                if review_count_element:
                    gig_info["num_reviews"] = clean_reviews(review_count_element.text.strip())
                else:
                    gig_info["num_reviews"] = "0" # Assume 0 reviews if not found.

            gigs_data.append(gig_info)
        except Exception as e:
            # Log any error during parsing of a single card and add placeholder data.
            logger.error(f"[{card_identifier}] Error parsing a gig card: {e}", exc_info=True)
            gigs_data.append({ # Append placeholder to maintain row count if needed downstream.
                "title": "Error parsing card", "seller_name": "Error", "seller_level": "Error",
                "price": "Error", "num_reviews": "Error", "rating": "Error", "gig_url": "Error"
            })
            
    if not gigs_data and gig_cards: 
        # This case means cards were identified by selectors, but no data was extracted from any of them.
        logger.warning("Gig cards were found, but no data could be extracted from any of them. CSS Selectors might be outdated or page structure is vastly different.")
    
    logger.info(f"Successfully parsed {len(gigs_data)} gigs from the page content.")
    return gigs_data

def clean_price(price_str: str) -> str | None:
    """
    Extracts a numerical string from a price string (e.g., "$10.50" -> "10.50").

    Args:
        price_str: The raw price string.

    Returns:
        The cleaned numerical price string, or None if no numerical part is found.
    """
    if not price_str: return None
    import re # Local import for utility function
    match = re.search(r'[\d\.,]+', price_str) # Finds sequences of digits, dots, or commas
    return match.group(0).replace(',', '') if match else None # Removes commas for consistency

def clean_reviews(reviews_str: str) -> str | None:
    """
    Cleans review count string (e.g., "(1.2k)" -> "1200", "25" -> "25").

    Args:
        reviews_str: The raw review count string.

    Returns:
        The cleaned review count as a string, or "0" if parsing fails.
    """
    if not reviews_str: return None
    import re # Local import
    reviews_str = reviews_str.lower().replace('(', '').replace(')', '').replace(',', '')
    match = re.search(r'([\d\.]+)(k?)', reviews_str) # Looks for number, optionally followed by 'k'
    if match:
        num = float(match.group(1))
        if match.group(2) == 'k': # If 'k' is present, multiply by 1000
            return str(int(num * 1000))
        return str(int(num))
    return "0" # Default to "0" if no number found

def clean_rating(rating_str: str) -> str | None:
    """
    Cleans rating string to ensure it's a numerical value (e.g., "4.9 stars" -> "4.9").

    Args:
        rating_str: The raw rating string.

    Returns:
        The cleaned rating string, or None if no numerical part is found.
    """
    if not rating_str: return None
    import re # Local import
    match = re.search(r'[\d\.]+', rating_str) # Finds sequences of digits or dots
    return match.group(0) if match else None

def ensure_output_directory_exists():
    """
    Checks if the output directory (defined by OUTPUT_DIR constant) exists,
    and creates it if it doesn't.

    Raises:
        OSError: If the directory creation fails.
    """
    if not os.path.exists(OUTPUT_DIR):
        logger.info(f"Output directory '{OUTPUT_DIR}' does not exist. Creating it.")
        try:
            os.makedirs(OUTPUT_DIR)
            logger.info(f"Successfully created output directory: '{OUTPUT_DIR}'")
        except OSError as e:
            logger.error(f"Error creating output directory '{OUTPUT_DIR}': {e}", exc_info=True)
            raise # Re-raise if directory creation fails, as saving will be impossible.
    else:
        logger.info(f"Output directory '{OUTPUT_DIR}' already exists.")


def save_to_csv(data: list[dict], base_filename: str, keyword: str):
    """
    Saves the provided data to a CSV file.

    The filename will include the base_filename, keyword, and a timestamp.
    Data is saved in the directory specified by the OUTPUT_DIR constant.

    Args:
        data: A list of dictionaries to save.
        base_filename: The base name for the output file (e.g., "fiverr_gigs").
        keyword: The keyword used for scraping, included in the filename.
    """
    if not data:
        logger.info("No data provided to save_to_csv. Skipping file creation.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sanitized_keyword = keyword.replace(" ", "_").lower() # Basic sanitization for filename
    filename = os.path.join(OUTPUT_DIR, f"{base_filename}_{sanitized_keyword}_{timestamp}.csv")
    
    try:
        df = pd.DataFrame(data)
        # Define a consistent column order for the CSV.
        column_order = ["title", "seller_name", "seller_level", "seller_country", "price", "rating", "num_reviews", "gig_url"]
        # Filter to only include columns that are actually present in the DataFrame to avoid errors.
        df_columns = [col for col in column_order if col in df.columns]
        
        df.to_csv(filename, index=False, encoding='utf-8', columns=df_columns)
        logger.info(f"Successfully saved {len(data)} gigs to CSV: {filename}")
    except Exception as e:
        logger.error(f"Error saving data to CSV file '{filename}': {e}", exc_info=True)

def save_to_json(data: list[dict], base_filename: str, keyword: str):
    """
    Saves the provided data to a JSON file.

    The filename will include the base_filename, keyword, and a timestamp.
    Data is saved in the directory specified by the OUTPUT_DIR constant.
    JSON is saved in a human-readable format (indented).

    Args:
        data: A list of dictionaries to save.
        base_filename: The base name for the output file (e.g., "fiverr_gigs").
        keyword: The keyword used for scraping, included in the filename.
    """
    if not data:
        logger.info("No data provided to save_to_json. Skipping file creation.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sanitized_keyword = keyword.replace(" ", "_").lower() # Basic sanitization for filename
    filename = os.path.join(OUTPUT_DIR, f"{base_filename}_{sanitized_keyword}_{timestamp}.json")

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4) # indent=4 for pretty printing
        logger.info(f"Successfully saved {len(data)} gigs to JSON: {filename}")
    except Exception as e:
        logger.error(f"Error saving data to JSON file '{filename}': {e}", exc_info=True)


def main():
    """
    Main function to orchestrate the Fiverr gig scraping process.

    Steps:
    1. Sets up logging and ensures the output directory exists.
    2. Defines search parameters (keyword, max pages).
    3. Initializes the Selenium WebDriver with configured options (headless, user-agent).
    4. Iterates through search result pages for the given keyword:
        a. Fetches HTML content for each page, with retries for robustness.
        b. Parses gig data from the HTML.
        c. Appends extracted gigs to a master list.
        d. Implements delays between page requests.
    5. After scraping, saves all collected gig data to CSV and JSON files.
    6. Cleans up by closing the WebDriver.
    """
    logger.info("--- Fiverr Scraper Started ---")
    
    # --- Setup Phase ---
    try:
        ensure_output_directory_exists()
    except Exception: 
        # Error is already logged by ensure_output_directory_exists
        logger.critical("Failed to create or access output directory. Scraper cannot continue. Exiting.")
        return # Exit if output directory can't be made or accessed.

    search_keyword = "python developer" # Keyword to search on Fiverr.
    # MAX_PAGES_TO_SCRAPE is now a global constant.
    
    logger.info(f"Target keyword: '{search_keyword}', Max pages to scrape: {MAX_PAGES_TO_SCRAPE}")

    # Configure Selenium WebDriver options
    options = Options()
    options.add_argument("--headless") # Run Chrome in headless mode (no GUI).
    options.add_argument("--disable-gpu") # Recommended for headless mode.
    options.add_argument("--window-size=1920x1080") # Specify window size.
    selected_user_agent = random.choice(USER_AGENTS) # Pick a random User-Agent.
    options.add_argument(f"user-agent={selected_user_agent}")
    logger.info(f"Using User-Agent for this session: {selected_user_agent}")

    driver = None
    all_gigs_data = []
    pages_actually_scraped = 0
    
    # --- WebDriver Initialization and Scraping Phase ---
    try:
        logger.info("Initializing WebDriver...")
        # Installs or uses cached ChromeDriver.
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        logger.info("WebDriver initialized successfully.")
        
        # Pagination loop
        for page_num in range(1, MAX_PAGES_TO_SCRAPE + 1):
            logger.info(f"Processing page {page_num} for keyword '{search_keyword}'...")
            try:
                # Fetch HTML for the current page. Retries are handled by the decorator.
                html_content = get_page_html(driver, search_keyword, page_num)
            except Exception as e: 
                # This catches the exception if all retries in get_page_html fail.
                logger.error(f"Failed to get HTML for page {page_num} of keyword '{search_keyword}' after all retries: {e}", exc_info=True)
                html_content = None # Ensure html_content is None to stop further processing for this page.

            if html_content:
                # Parse gigs from the fetched HTML.
                gigs_on_page = parse_gigs(html_content)
                if gigs_on_page:
                    all_gigs_data.extend(gigs_on_page)
                    logger.info(f"Extracted {len(gigs_on_page)} gigs from page {page_num}.")
                else:
                    # No gigs found on this page.
                    logger.info(f"No gigs found or parsed on page {page_num}. This might be the last page or an issue with parsing for this page.")
                    # If not the first page, and no gigs found, assume it's the end of results.
                    if page_num > 1: 
                        logger.info(f"Assuming end of results at page {page_num} as no gigs were parsed.")
                        pages_actually_scraped = page_num 
                        break 
            else:
                # HTML content was None, meaning fetching failed definitively for this page.
                logger.error(f"Failed to retrieve HTML for page {page_num} (content was None). Stopping pagination for this keyword.")
                pages_actually_scraped = page_num 
                break 
            
            pages_actually_scraped = page_num # Update count after successful processing of a page.
            # Polite delay before fetching the next page, if not the last page.
            if page_num < MAX_PAGES_TO_SCRAPE:
                sleep_duration = random.uniform(MIN_INTER_PAGE_DELAY, MAX_INTER_PAGE_DELAY)
                logger.info(f"Waiting {sleep_duration:.2f} seconds before fetching next page...")
                time.sleep(sleep_duration)
        
        logger.info(f"Scraping finished. Attempted to scrape {pages_actually_scraped} page(s). Total gigs collected: {len(all_gigs_data)}.")
        
        # --- Data Saving Phase ---
        if all_gigs_data:
            logger.info(f"Total of {len(all_gigs_data)} gigs collected. Preparing to save...")
            save_to_csv(all_gigs_data, "fiverr_gigs", search_keyword)
            save_to_json(all_gigs_data, "fiverr_gigs", search_keyword)
            logger.info("Data saving process completed.")
        else:
            logger.warning("No gigs were collected from any page. No files will be saved.")
            
    except WebDriverException as e:
        # Handle critical WebDriver errors during initialization or major operations.
        logger.critical(f"WebDriver initialization or critical operation failed: {e}", exc_info=True)
    except Exception as e:
        # Catch any other unexpected critical errors during the main process.
        logger.critical(f"An unexpected critical error occurred in the main scraping process: {e}", exc_info=True)
    finally:
        # --- Cleanup Phase ---
        if driver:
            logger.info("Closing WebDriver...")
            driver.quit()
            logger.info("WebDriver closed.")
        logger.info("--- Fiverr Scraper Finished ---")

if __name__ == "__main__":
    main()
