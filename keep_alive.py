from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

print("Starting headless browser...")
chrome_options = Options()
chrome_options.add_argument("--headless") 
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

driver = webdriver.Chrome(options=chrome_options)

try:
    print("Accessing DTU Chess Club app...")
    driver.get("https://dtu-chess.streamlit.app/")
    time.sleep(5)
    
    try:
        wake_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Yes, get this app back up!')]")
        wake_button.click()
        print("App was asleep! Clicked the wake-up button.")
        time.sleep(20)
    except:
        print("App is already awake! No button to click.")
        
    time.sleep(10)
    print("Successfully loaded. App is secure!")
    
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    driver.quit()
    print("Browser closed.")
