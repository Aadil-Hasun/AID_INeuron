import time
import requests
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
import json

from src.utils import zip_images_folder, save_image_to_s3, delete_files, CONFIG_FILE_PATH
from src.logger import logging

with open(CONFIG_FILE_PATH, 'r') as config_file:
    config = json.load(config_file)

s3_bucket_name = config['bucket_name']


class ScrapData:
    def __init__(self):
        try:
            self.chrome_options = Options()
            self.chrome_options.add_argument("--headless")
            self.chrome_options.add_argument("--start-maximized")
            self.chrome_options.add_argument('--disable-useAutomationExtension')
            self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            self.chrome_options.add_argument("window-size=1200x600")
            chrome_options.add_experimental_options("excludeSwitches", Collections.singletonList("enable-automation"))
            self.c = DesiredCapabilities.CHROME
            self.c["pageLoadStrategy"] = "eager"
            s = Service(executable_path='./chromedriver')
            self.driver = webdriver.Chrome(options=self.chrome_options, service=s)
        except Exception as e:
            print(f"Error Occurred: {e}")

    def scroll_to_end(self):
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)

    def fetch_image_urls(self, category_name: str, max_imgs_to_fetch: int, sleep_time: int = 1):

        url = "https://www.google.com/search?safe=off&site=&tbm=isch&source=hp&q={q}&oq={q}&gs_l=img"

        # load the page
        self.driver.get(url.format(q=category_name))

        image_urls = set()
        image_count = 0
        results_start = 0
        while image_count < max_imgs_to_fetch:
            self.scroll_to_end()

            # get all image thumbnail results
            thumbnail_results = self.driver.find_elements(By.CSS_SELECTOR, "img.Q4LuWd")
            number_results = len(thumbnail_results)

            for img in thumbnail_results[results_start:number_results]:
                try:
                    img.click()
                    time.sleep(sleep_time)
                except Exception:
                    continue
                try:
                    # extract image urls
                    actual_image = WebDriverWait(self.driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR,
                                                                                                        "img.iPVvYb")))
                    # actual_image = self.driver.find_element(By.CSS_SELECTOR, '')
                except Exception as e:
                    print(f"Error Occurred: {e}")
                    continue

                if actual_image.get_attribute('src') and 'http' in actual_image.get_attribute('src'):
                    image_urls.add(actual_image.get_attribute('src'))

                image_count = len(image_urls)

                if len(image_urls) >= max_imgs_to_fetch:
                    break
                else:
                    print("Found:", len(image_urls), "image links, scrapping for more...")
                    time.sleep(5)
                    if img == thumbnail_results[number_results-1]:
                        load_more_button = self.driver.find_element(By.CSS_SELECTOR, ".mye4qd")
                        if load_more_button:
                            self.driver.execute_script("document.querySelector('.mye4qd').click();")

            # update results_start
            results_start = len(thumbnail_results)

        return image_urls

    def scrap_data(self, category_name: str, max_images: int, user_name: str):
        logging.info("Data Scrapping Initialized")
        try:
            cur_dir = os.path.curdir
            image_folder_path = os.path.join(cur_dir, "Images")
            user_folder_path = os.path.join(image_folder_path, user_name)
            file_name = category_name + datetime.now().strftime("%Y%m%d%H%M%S")
            category_folder_path = os.path.join(user_folder_path,
                                                file_name)
            if not os.path.exists(category_folder_path):
                # Create the folder
                os.makedirs(category_folder_path)

            image_urls = self.fetch_image_urls(category_name=category_name, max_imgs_to_fetch=max_images)
            for i, image_url in enumerate(image_urls):
                try:
                    response = requests.get(image_url)
                except Exception as e:
                    print(f"Couldn't access {image_url} - {e}")
                    continue
                try:
                    # Save the image to a local folder
                    with open(f"{category_folder_path}/{category_name}{i}.jpg", "wb") as f:
                        f.write(response.content)

                except Exception as e:
                    logging.error(f"Error Occurred while saving the file: {e}")
                    print(f"Error: Couldn't save the image at {image_url} - {e}")

            logging.info("Data Scrapping completed successfully")

            # Zip the images folder
            zip_filename = zip_images_folder(category_folder_path, file_name)

            # Upload the zip file to S3
            with open(zip_filename, 'rb') as zip_file:
                save_image_to_s3(zip_file.read(), user_name, zip_filename)
            s3_zipfile_name = zip_filename
            os.remove(zip_filename)
            delete_files(category_folder_path)
            os.rmdir(category_folder_path)
            return s3_zipfile_name

        except Exception as e:
            logging.error(f"Error Occurred while saving the file: {e}")
            print(f"Error Occurred: {e}")
            return ""
