from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

print("Starting headless browser...")
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

# Initialize the invisible browser
driver = webdriver.Chrome(options=chrome_options)

try:
    print("Accessing DTU Chess Club app...")
    driver.get("https://dtu-chess.streamlit.app/")
    time.sleep(15)
    print("Successfully loaded and waited. App is awake!")
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    driver.quit()
    print("Browser closed.")
