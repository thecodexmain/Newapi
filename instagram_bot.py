import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

logger = logging.getLogger(__name__)

class InstagramBot:
    def __init__(self, headless=True):
        self.driver = None
        self.headless = headless
        self._setup_driver()
    
    def _setup_driver(self):
        try:
            options = Options()
            
            if self.headless:
                options.add_argument('--headless=new')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--window-size=1920,1080')
            
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option('excludeSwitches', ['enable-automation'])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Use Chromium
            options.binary_location = '/usr/bin/chromium'
            service = Service('/usr/bin/chromedriver')
            
            self.driver = webdriver.Chrome(service=service, options=options)
            logger.info("Chrome driver initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise
    
    def login_with_cookies(self, cookies):
        try:
            self.driver.get('https://www.instagram.com')
            time.sleep(3)
            
            for cookie in cookies:
                try:
                    if 'name' in cookie and 'value' in cookie:
                        self.driver.add_cookie(cookie)
                except:
                    pass
            
            self.driver.refresh()
            time.sleep(5)
            
            current_url = self.driver.current_url.lower()
            return 'login' not in current_url
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    
    def connect_to_business_suite(self):
        try:
            self.driver.get('https://business.facebook.com/')
            time.sleep(5)
            return True
        except Exception as e:
            logger.error(f"Connect error: {e}")
            return False
    
    def get_current_url(self):
        try:
            return self.driver.current_url if self.driver else None
        except:
            return None
    
    def quit(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
