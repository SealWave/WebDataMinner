**Manual Testing Checklist for Fiverr Scraper**

Thank you for helping test the Fiverr Scraper! Please follow these steps and note any issues or unexpected behavior.

**A. Setup:**
1.  Ensure you have Python 3.7+ and Google Chrome installed.
2.  Navigate to the `fiverr_scraper` directory in your terminal.
3.  If you haven't already, create a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
4.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
    (If you see errors during `pip install -r requirements.txt` related to `psutil`, you might be on an M1/M2 Mac. Try `pip install psutil` first, then `pip install -r requirements.txt` again.)

**B. First Run - Simple Keyword (e.g., "logo design"):**
1.  Run with a command-line keyword:
    ```bash
    python scraper.py --keyword "logo design"
    ```
2.  **Observe**:
    *   Does the script start? Do you see log messages in the console (e.g., "--- Fiverr Scraper Started ---", "Initializing scraper for keyword: 'logo design'")?
    *   Does a Chrome browser window open and close (quickly, as it's headless by default)? This might not be visible.
    *   How many pages does it say it's scraping in the logs (e.g., "Processing page 1 for keyword 'logo design'...")? The default is set to 2 pages (`MAX_PAGES_TO_SCRAPE = 2` in the script).
    *   Does it report the total number of gigs found (e.g., "Total gigs collected: X")?
3.  **Check Output Files**:
    *   Look in the `fiverr_scraper/output/` directory.
    *   You should find a CSV file and a JSON file, named with the keyword "logo_design" and a timestamp (e.g., `fiverr_gigs_logo_design_YYYYMMDD_HHMMSS.csv`).
    *   Open the CSV file (e.g., with Excel, Google Sheets, or a text editor).
        *   Are all expected columns present: `title`, `seller_name`, `seller_level`, `price`, `rating`, `num_reviews`, `gig_url`? **There should NOT be a 'Seller Country' column.**
        *   Does the data in a few rows look reasonable for "logo design" gigs? (e.g., titles make sense, prices are present).
        *   Are there any obvious missing fields for many gigs? (Some missing fields are okay, e.g., a brand new gig might not have reviews, or `seller_level` might be "N/A").
    *   Open the JSON file (e.g., with a text editor or code editor).
        *   Does the structure look correct (a list of objects, each object being a gig)?
        *   Does it contain similar data to the CSV (and **no** 'seller_country' field)?

**C. Second Run - Different Keyword & Interactive Mode (e.g., "python script"):**
1.  Run without a command-line keyword:
    ```bash
    python scraper.py
    ```
2.  When prompted (`Please enter the keyword to search on Fiverr (e.g., 'python developer'):`), enter a different keyword, e.g., "python script".
3.  **Observe & Check Output Files**: Repeat observation and file checks as in step B, ensuring new output files are created for "python_script" and that they also do **not** contain a 'seller_country' field.

**D. Testing Pagination (use a common keyword that yields many results, e.g., "voice over"):**
1.  Run with a keyword known to have many results:
    ```bash
    python scraper.py --keyword "voice over"
    ```
2.  **Observe Logs**:
    *   Pay attention to log messages indicating page numbers being scraped (e.g., "INFO: Processing page 1 for keyword 'voice over'...", "INFO: Successfully fetched HTML for page 2 of keyword 'voice over'.").
    *   The script is configured by default to scrape a maximum of 2 pages (`MAX_PAGES_TO_SCRAPE = 2`). Confirm it attempts to scrape up to this many pages if results are available.
    *   Does the total number of gigs collected seem appropriate for the number of pages scraped? (e.g., if 2 pages are scraped, you'd expect more gigs than from a single page, assuming the keyword has enough results).

**E. CSS Selector Verification (Crucial - if data is missing or incorrect):**
*   This is the most complex part if things go wrong. If you notice that many gigs are missing data for specific fields (e.g., no prices, no seller levels, very few titles), the CSS selectors in `scraper.py` might be outdated due to Fiverr website changes.
*   **If you suspect selector issues**:
    1.  Open `fiverr_scraper/scraper.py`.
    2.  Look at the `parse_gigs` function. The selectors are directly embedded in `card.select_one(...)` calls (e.g., `card.select_one('a[data-testid="gig-title"], ...)`).
    3.  Manually open Fiverr in your browser with a search term (e.g., `https://www.fiverr.com/search/gigs?query=voice%20over`).
    4.  Use your browser's Developer Tools (right-click on an element, then "Inspect") to examine the HTML structure of a few gig cards.
    5.  Compare the HTML elements and their classes/attributes on the live Fiverr site to the selectors in `scraper.py` for the problematic field(s).
    6.  **Note down any discrepancies.** For example, if the script looks for a title with `a[data-testid="gig-title"]` but on the site it's now `h2[data-testid="gig-title-main"]`, that's a problem.
    7.  Report these discrepancies.

**F. Reporting Feedback:**
*   What keyword(s) did you use for testing?
*   Did the script run successfully for each keyword? If not, what was the error message (please copy the full traceback if possible)?
*   Were the output files (CSV/JSON) created correctly in the `output/` directory?
*   For the data you spot-checked, was it generally accurate and complete for the expected fields?
*   Were any fields consistently missing or incorrect? If so, this might point to selector issues (see step E).
*   Did pagination seem to work as expected (attempting to scrape up to `MAX_PAGES_TO_SCRAPE`)?
*   Did you encounter any issues during setup or installation?
*   Any other observations, suggestions, or issues.

Thank you for your time and effort!
```
