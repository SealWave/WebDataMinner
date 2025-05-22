# Fiverr Gig Scraper

## Description
This Python script scrapes gig information from Fiverr based on a search keyword. It uses Selenium for dynamic content loading, handles pagination, and saves the extracted data to CSV and JSON formats.

## Features
- Scrapes gig data from Fiverr search results.
- Handles dynamic JavaScript-loaded content using Selenium (headless Chrome).
- Supports pagination to navigate through multiple search result pages.
- Extracts: Gig Title, Seller Name, Seller Level, Price, Number of Reviews, Average Rating, Gig URL.
- Implements User-Agent rotation.
- Uses `tenacity` for retry logic on failed requests.
- Saves data in both CSV and JSON formats (in the `output/` directory).
- Configurable search keyword via command-line argument or interactive input.
- Includes logging for key events and errors.

## Requirements
- Python 3.7+
- Google Chrome browser installed.
- `webdriver-manager` will automatically download and manage ChromeDriver. If you encounter issues, you might need to ensure ChromeDriver is compatible with your Chrome version or install it manually and adjust the script.

## Setup Instructions
1.  **Clone the Repository / Download Files**:
    Ensure you have the `fiverr_scraper` directory containing `scraper.py`, `requirements.txt`, etc.

2.  **Create a Virtual Environment (Recommended)**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies**:
    Navigate to the `fiverr_scraper` directory and run:
    ```bash
    pip install -r requirements.txt
    ```

## How to Run
Execute the script from within the `fiverr_scraper` directory.

1.  **Using Command-Line Argument (Recommended)**:
    ```bash
    python scraper.py --keyword "your search term"
    ```
    Replace `"your search term"` with the actual keyword you want to search for (e.g., `"python developer"`, `"logo design"`).

2.  **Interactive Input**:
    If you run the script without the `--keyword` argument, it will prompt you to enter one:
    ```bash
    python scraper.py
    # Output: Please enter the keyword to search on Fiverr: 
    ```

3.  **Output**:
    - Scraped data will be saved in timestamped CSV and JSON files in the `output/` directory.
    - Logs will be printed to the console.

## Code Structure Overview
- **`scraper.py`**: The main script containing all the logic.
    - `main()`: Orchestrates the scraping process, handles user input, and calls other functions.
    - `get_page_html()`: Fetches the HTML content of a search result page using Selenium, with retry logic.
    - `parse_gigs()`: Parses the HTML to extract gig information using BeautifulSoup. Helper functions (`clean_price`, `clean_reviews`, `clean_rating`) are used for data cleaning.
    - `save_to_csv()` / `save_to_json()`: Save the extracted data to files.
    - `ensure_output_directory_exists()`: Creates the output directory if it doesn't exist.
- **`requirements.txt`**: Lists the Python dependencies.
- **`output/`**: Directory where CSV and JSON files are saved.

## Important Notes & Limitations
- **Website Changes**: Web scrapers are sensitive to changes in the target website's structure. If Fiverr updates its layout, the CSS selectors in `parse_gigs()` may need to be updated. The current selectors are based on observed patterns and may require verification if data is not extracted correctly.
- **Ethical Scraping**: Always use web scrapers responsibly. Be mindful of Fiverr's Terms of Service. Avoid sending too many requests in a short period. This script includes delays, but adjust as needed.
- **Bot Detection**: While this scraper uses User-Agent rotation and delays, advanced bot detection measures on Fiverr might still block it.
- **Error Handling**: The script includes error handling and retries, but complex scenarios or CAPTCHAs are not handled.

## (Optional) Future Enhancements
- Advanced IP Rotation / Proxy Support.
- More sophisticated CAPTCHA handling (if encountered).
- More robust handling of different gig card layouts or A/B testing by Fiverr.
- GUI for easier use.
