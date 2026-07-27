import os
import time
import base64
import hashlib
import hmac
import struct
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InstagramBot:
    def __init__(self, headless=True):
        """Initialize Chrome driver with headless mode for Railway"""
        self.driver = None
        self.headless = headless
        self._setup_driver()
    
    def _setup_driver(self):
        """Configure and initialize Chrome driver"""
        options = webdriver.ChromeOptions()
        
        # Headless mode for Railway
        if self.headless:
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
        
        # Additional options to avoid detection
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Disable notifications
        prefs = {
            'profile.default_content_setting_values.notifications': 2,
            'profile.default_content_setting_values.popups': 2
        }
        options.add_experimental_option('prefs', prefs)
        
        # User agent
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            self.driver = webdriver.Chrome(options=options)
            # Hide webdriver property
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
            })
            logger.info("Chrome driver initialized successfully")
        except Exception as e:
            logger.error(f'Failed to initialize Chrome driver: {e}')
            raise Exception(f'Failed to initialize Chrome driver: {e}')
    
    def login_with_cookies(self, cookies):
        """Login using cookie array (supports both list and dict formats)"""
        try:
            # Navigate to Instagram
            logger.info("Navigating to Instagram...")
            self.driver.get('https://www.instagram.com')
            time.sleep(3)
            
            # Handle cookie consent if present
            self._handle_cookies()
            
            # Add cookies - support both formats
            cookie_count = 0
            for cookie in cookies:
                if 'name' in cookie and 'value' in cookie:
                    try:
                        # Prepare cookie
                        cookie_dict = {
                            'name': cookie['name'],
                            'value': cookie['value'],
                            'domain': cookie.get('domain', '.instagram.com'),
                            'path': cookie.get('path', '/')
                        }
                        # Add optional fields if present
                        if 'secure' in cookie:
                            cookie_dict['secure'] = cookie['secure']
                        if 'httpOnly' in cookie:
                            cookie_dict['httpOnly'] = cookie['httpOnly']
                        
                        self.driver.add_cookie(cookie_dict)
                        cookie_count += 1
                        logger.debug(f"Added cookie: {cookie['name']}")
                    except Exception as e:
                        logger.warning(f"Failed to add cookie {cookie.get('name')}: {e}")
            
            logger.info(f"Successfully added {cookie_count} cookies")
            
            # Refresh to apply cookies
            self.driver.refresh()
            time.sleep(5)
            
            # Check if logged in
            return self._verify_login()
            
        except Exception as e:
            logger.error(f'Cookie login error: {e}')
            return False
    
    def _verify_login(self):
        """Verify if login was successful"""
        try:
            current_url = self.driver.current_url.lower()
            
            # Check for login indicators
            if 'login' in current_url:
                # Check for error messages
                body_text = self.driver.find_element(By.TAG_NAME, 'body').text.lower()
                if 'incorrect' in body_text or 'wrong password' in body_text:
                    return False
                return False
            
            # Check for navigation elements that indicate logged-in state
            nav_elements = self.driver.find_elements(By.XPATH, 
                "//a[contains(@href, 'direct/inbox') or contains(@href, 'explore') or @aria-label='Home']")
            
            if nav_elements:
                logger.info("Login successful - navigation elements found")
                return True
            
            # Check URL for logged-in patterns
            if 'accounts/onetap' in current_url or 'instagram.com/direct' in current_url:
                logger.info("Login successful - redirect to logged-in page")
                return True
            
            # Check for profile icon
            profile_elements = self.driver.find_elements(By.XPATH, 
                "//a[contains(@href, '/accounts/edit/') or contains(@href, '/settings/')]")
            if profile_elements:
                logger.info("Login successful - profile elements found")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f'Login verification error: {e}')
            return False
    
    def login_with_credentials(self, username, password, two_factor_key=None):
        """Login using username/password with optional 2FA"""
        try:
            logger.info("Navigating to Instagram login page...")
            self.driver.get('https://www.instagram.com/accounts/login/')
            time.sleep(3)
            
            # Handle cookies consent
            self._handle_cookies()
            
            # Find and fill login fields
            username_field = self._find_element(By.NAME, 'username')
            password_field = self._find_element(By.NAME, 'password')
            
            if not username_field or not password_field:
                logger.error("Could not find login fields")
                return False
            
            logger.info("Entering credentials...")
            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)
            
            # Submit form
            submit_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
            submit_btn.click()
            time.sleep(5)
            
            # Check for 2FA
            if self._is_2fa_required():
                logger.info("2FA required")
                if two_factor_key:
                    code = self._get_totp_code(two_factor_key)
                    if code:
                        logger.info(f"Generated 2FA code: {code}")
                        self._enter_2fa_code(code)
                    else:
                        logger.warning("Failed to generate 2FA code")
                        return False
                else:
                    # Wait for manual 2FA entry (not recommended for API)
                    logger.warning("2FA key not provided")
                    return False
            
            # Check login success
            return self._verify_login()
            
        except Exception as e:
            logger.error(f'Credential login error: {e}')
            return False
    
    def connect_to_business_suite(self):
        """Navigate to Facebook Business Suite and connect ad account"""
        try:
            logger.info("Navigating to Facebook Business Suite...")
            self.driver.get('https://business.facebook.com/business/loginpage/?next=https%3A%2F%2Fbusiness.facebook.com%2F')
            time.sleep(5)
            
            # Handle cookies if present
            self._handle_cookies()
            
            # Click 'Continue with Instagram'
            logger.info("Looking for 'Continue with Instagram' button...")
            ig_btn = self._find_element(By.XPATH, '//button[contains(text(), "Continue with Instagram")]', timeout=10)
            if ig_btn:
                logger.info("Clicking 'Continue with Instagram'...")
                try:
                    ig_btn.click()
                except:
                    self.driver.execute_script("arguments[0].click();", ig_btn)
                time.sleep(5)
                
                # Handle popup
                main_window = self.driver.current_window_handle
                if len(self.driver.window_handles) > 1:
                    for handle in self.driver.window_handles:
                        if handle != main_window:
                            self.driver.switch_to.window(handle)
                            logger.info("Switched to popup window")
                            time.sleep(3)
                            
                            # Handle professional conversion if needed
                            self._handle_professional_conversion()
                            
                            # Close popup
                            logger.info("Closing popup window...")
                            self.driver.close()
                            self.driver.switch_to.window(main_window)
                            
                            # Refresh main page
                            logger.info("Refreshing main page...")
                            self.driver.refresh()
                            time.sleep(5)
                
                logger.info("Successfully connected to Business Suite")
                return True
            
            logger.warning("Could not find 'Continue with Instagram' button")
            return False
            
        except Exception as e:
            logger.error(f'Business Suite connection error: {e}')
            return False
    
    def navigate_to_ad_picker(self, asset_id, business_id=None):
        """Navigate directly to the boosted post picker page"""
        if not asset_id:
            logger.error("asset_id is required")
            return None
        
        try:
            url = f'https://business.facebook.com/latest/boosted_item_picker/?asset_id={asset_id}'
            if business_id:
                url += f'&business_id={business_id}'
            url += '&ir_qe_exposed=1&content_filter=All&entry_point=bizweb_home_header&nav_ref=internal_nav&selected_item=boosted_instagram_media_picker'
            
            logger.info(f"Navigating to ad picker: {url}")
            self.driver.get(url)
            time.sleep(5)
            return self.driver.current_url
            
        except Exception as e:
            logger.error(f'Error navigating to ad picker: {e}')
            return None
    
    def get_current_url(self):
        """Get current page URL"""
        try:
            return self.driver.current_url if self.driver else None
        except:
            return None
    
    def get_page_title(self):
        """Get current page title"""
        try:
            return self.driver.title if self.driver else None
        except:
            return None
    
    def quit(self):
        """Close browser and cleanup"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
            logger.info("Browser closed")
    
    # Helper methods
    def _find_element(self, by, value, timeout=10):
        """Find element with timeout"""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
        except TimeoutException:
            return None
    
    def _handle_cookies(self):
        """Handle cookie consent dialogs"""
        try:
            cookie_btns = self.driver.find_elements(By.XPATH, 
                '//button[contains(text(), "Accept") or contains(text(), "Allow") or contains(text(), "Agree")]')
            for btn in cookie_btns:
                if btn.is_displayed():
                    logger.info("Handling cookie consent...")
                    btn.click()
                    time.sleep(2)
                    break
        except Exception as e:
            logger.debug(f'Cookie handling error: {e}')
    
    def _is_2fa_required(self):
        """Check if 2FA is required"""
        try:
            # Check for 2FA input
            inputs = self.driver.find_elements(By.NAME, 'verificationCode')
            if inputs:
                return True
                
            # Check URL for 2FA indicators
            current_url = self.driver.current_url.lower()
            if 'two_step' in current_url or 'two_factor' in current_url:
                return True
            
            # Check for 2FA text
            body_text = self.driver.find_element(By.TAG_NAME, 'body').text.lower()
            if 'verification code' in body_text or 'two-factor' in body_text:
                return True
                
            return False
        except:
            return False
    
    def _enter_2fa_code(self, code):
        """Enter 2FA verification code"""
        try:
            # Find verification input
            inputs = self.driver.find_elements(By.NAME, 'verificationCode')
            if not inputs:
                inputs = self.driver.find_elements(By.XPATH, '//input[@type="text"]')
            
            if inputs:
                logger.info("Entering 2FA code...")
                inputs[0].clear()
                inputs[0].send_keys(code)
                time.sleep(2)
                
                # Find and click submit button
                submit_btn = self.driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
                submit_btn.click()
                time.sleep(5)
                return True
            
            return False
        except Exception as e:
            logger.error(f'Error entering 2FA code: {e}')
            return False
    
    def _handle_professional_conversion(self):
        """Handle professional account conversion steps"""
        try:
            logger.info("Checking for professional conversion steps...")
            
            # Define steps with their text and action
            steps = [
                ('Which best describes you', 'Creator'),
                ('Select a category', 'Art'),
                ('Switch to a professional', 'Continue'),
                ('account is ready', 'Done'),
                ('Creator account is ready', 'Done')
            ]
            
            for text, action in steps:
                try:
                    elements = self.driver.find_elements(By.XPATH, 
                        f'//*[contains(text(), "{text}")]')
                    if elements:
                        logger.info(f"Found step: {text}")
                        
                        # Select option
                        options = self.driver.find_elements(By.XPATH, 
                            f'//*[contains(text(), "{action}")]')
                        for opt in options:
                            if opt.is_displayed():
                                logger.info(f"Selecting: {action}")
                                try:
                                    opt.click()
                                except:
                                    self.driver.execute_script("arguments[0].click();", opt)
                                time.sleep(2)
                                break
                        
                        # Click continue/done/next
                        btns = self.driver.find_elements(By.XPATH, 
                            '//button[contains(text(), "Continue") or contains(text(), "Done") or contains(text(), "Next")]')
                        for btn in btns:
                            if btn.is_displayed():
                                logger.info(f"Clicking: {btn.text}")
                                try:
                                    btn.click()
                                except:
                                    self.driver.execute_script("arguments[0].click();", btn)
                                time.sleep(3)
                                break
                except:
                    continue
                    
            logger.info("Professional conversion handling complete")
                    
        except Exception as e:
            logger.error(f'Professional conversion error: {e}')
    
    def _get_totp_code(self, secret):
        """Generate TOTP code from secret key"""
        try:
            secret = secret.replace(' ', '').upper()
            padding = len(secret) % 8
            if padding:
                secret += '=' * (8 - padding)
            
            key = base64.b32decode(secret)
            counter = struct.pack('>Q', int(time.time() / 30))
            mac = hmac.new(key, counter, hashlib.sha1).digest()
            offset = mac[-1] & 0x0F
            binary = struct.unpack('>I', mac[offset:offset+4])[0] & 0x7FFFFFFF
            code = binary % 1000000
            return f'{code:06d}'
        except Exception as e:
            logger.error(f'Error generating TOTP code: {e}')
            return None
