import os
import sys
import time
import base64
import hashlib
import hmac
import struct
import json
import logging
import gc
import shutil
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

logger = logging.getLogger(__name__)

# The target Facebook Business Suite login page url
FB_LOGIN_URL = (
    "https://business.facebook.com/business/loginpage/"
    "?next=https%3A%2F%2Fbusiness.facebook.com%2F%3Fnav_ref%3Dbiz_unified_f3_login_page_to_mbs"
    "&login_options%5B0%5D=FB&login_options%5B1%5D=IG&login_options%5B2%5D=SSO"
    "&config_ref=biz_login_tool_flavor_mbs"
)

class InstagramBot:
    def __init__(self, headless=True):
        self.driver = None
        self.headless = headless
        self.temp_dir = None
        self.username = None
        self._setup_driver()
    
    def _setup_driver(self):
        """Setup Chrome driver with temporary profile"""
        try:
            import tempfile
            self.temp_dir = tempfile.mkdtemp(prefix='chrome_profile_')
            logger.info(f"Created temporary Chrome profile: {self.temp_dir}")
            
            options = Options()
            options.add_argument(f'--user-data-dir={self.temp_dir}')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-setuid-sandbox')
            options.add_argument('--clear-cache')
            options.add_argument('--clear-cookies')
            
            if self.headless:
                options.add_argument('--headless=new')
                options.add_argument('--window-size=1920,1080')
            
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            prefs = {
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_setting_values.images": 2,
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_settings.cookies": 2,
                "profile.cookie_controls_mode": 2,
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False
            }
            options.add_experimental_option("prefs", prefs)
            
            chromium_paths = ['/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome']
            for path in chromium_paths:
                if os.path.exists(path):
                    options.binary_location = path
                    break
            
            chromedriver_paths = ['/usr/bin/chromedriver', '/usr/local/bin/chromedriver']
            service = None
            for path in chromedriver_paths:
                if os.path.exists(path):
                    service = Service(path)
                    break
            
            if service:
                self.driver = webdriver.Chrome(service=service, options=options)
            else:
                self.driver = webdriver.Chrome(options=options)
            
            self.driver.set_page_load_timeout(60)
            self.driver.set_script_timeout(60)
            
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
            })
            
            logger.info("ChromeDriver initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Chrome Driver: {e}")
            self._cleanup_temp_dir()
            raise
    
    def _cleanup_temp_dir(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"Could not cleanup temp dir: {e}")
            finally:
                self.temp_dir = None
    
    def get_username(self):
        """Get the extracted username"""
        return self.username
    
    def _sanitize_cookie(self, cookie):
        """Sanitize cookie - exactly like 099.py"""
        valid_cookie = {}
        if "name" in cookie:
            valid_cookie["name"] = str(cookie["name"])
        if "value" in cookie:
            valid_cookie["value"] = str(cookie["value"])
        
        domain = str(cookie.get("domain", ".instagram.com"))
        valid_cookie["domain"] = domain if domain.startswith(".") else f".{domain}"
        valid_cookie["path"] = str(cookie.get("path", "/"))
        
        if "secure" in cookie and isinstance(cookie["secure"], bool):
            valid_cookie["secure"] = cookie["secure"]
        if "httpOnly" in cookie and isinstance(cookie["httpOnly"], bool):
            valid_cookie["httpOnly"] = cookie["httpOnly"]
        
        return valid_cookie
    
    def _js_click(self, elem, name):
        """JavaScript click with scrolling"""
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", elem)
            time.sleep(0.3)
            self.driver.execute_script("arguments[0].click();", elem)
            logger.info(f"    ✅ Clicked: {name}")
            return True
        except:
            logger.warning(f"    ❌ Failed: {name}")
            return False
    
    def _click_button(self, texts, label):
        """Find and click button by text - exactly like your script"""
        for txt in texts:
            selectors = [
                f"//button[text()='{txt}']",
                f"//button[contains(text(), '{txt}')]",
                f"//div[@role='button'][contains(., '{txt}')]",
                f"//span[contains(text(), '{txt}')]",
                f"//div[contains(text(), '{txt}')]",
                f"//*[@role='button'][contains(., '{txt}')]",
                f"//*[@aria-label='{txt}']",
            ]
            for sel in selectors:
                try:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    for elem in elems:
                        if elem.is_displayed():
                            txt_found = elem.text.strip()[:50]
                            logger.info(f"    🎯 [{label}] Found: '{txt_found}'")
                            if self._js_click(elem, label):
                                time.sleep(2)
                                return True
                except:
                    continue
        return False
    
    def _close_popup(self):
        """Close any popup - exactly like your script"""
        for sel in [
            "//*[@aria-label='Close']", 
            "//*[@aria-label='close']", 
            "//div[@role='button'][.//*[local-name()='svg']]", 
            "//button[contains(text(), 'Not Now')]", 
            "//button[contains(text(), 'Skip')]"
        ]:
            try:
                for elem in self.driver.find_elements(By.XPATH, sel):
                    if elem.is_displayed():
                        self.driver.execute_script("arguments[0].click();", elem)
                        time.sleep(0.5)
                        return True
            except:
                pass
        try:
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(0.3)
        except:
            pass
        return False
    
    def _find_and_click_boost(self):
        """Find Boost button with scrolling - exactly like your script"""
        logger.info("  🔍 Scanning for Boost button...")
        for i in range(5):
            self.driver.execute_script(f"window.scrollBy(0, {400 + i*200});")
            time.sleep(1)
        return self._click_button(['Boost', 'Boost post', 'Boost Post'], 'BOOST')
    
    def _navigate_to_posts_page(self):
        """Go to Instagram posts page - exactly like your script"""
        urls = [
            "https://business.facebook.com/latest/instagram_account/instagram_posts",
            "https://business.facebook.com/latest/instagram_account",
            "https://business.facebook.com/latest/home",
        ]
        for url in urls:
            self.driver.get(url)
            time.sleep(5)
            if 'login' not in self.driver.current_url.lower():
                return True
        return False
    
    def perform_cookie_login(self, cookies):
        """Perform cookie login - exactly like your script"""
        try:
            logger.info("Attempting cookie-based login...")
            
            # Navigate to Instagram
            logger.info("Navigating to Instagram...")
            self.driver.get("https://www.instagram.com")
            time.sleep(4)
            
            # Clear and inject cookies
            self.driver.delete_all_cookies()
            logger.info(f"Injecting {len(cookies)} cookies...")
            injected_count = 0
            for cookie in cookies:
                try:
                    clean_cookie = self._sanitize_cookie(cookie)
                    self.driver.add_cookie(clean_cookie)
                    injected_count += 1
                except Exception as e:
                    logger.warning(f"Skipped cookie ({cookie.get('name')}): {e}")
            
            logger.info(f"Successfully injected {injected_count} cookies.")
            
            # Reload page
            logger.info("Reloading page with injected session...")
            self.driver.refresh()
            time.sleep(5)
            
            # Handle One-Tap 'Continue' screen
            self._handle_continue_screen()
            
            # Verify login
            current_url = self.driver.current_url.lower()
            body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            
            nav_elements = self.driver.find_elements(By.XPATH, 
                "//a[contains(@href, 'direct/inbox') or contains(@href, 'explore') or @aria-label='Home']")
            
            is_logged_in = False
            if any(kw in current_url for kw in ["accounts/onetap", "instagram.com/direct", "instagram.com/explore"]) or len(nav_elements) > 0:
                is_logged_in = True
            elif "login" not in current_url and "phone number, username, or email" not in body_text:
                is_logged_in = True
            
            # Extract username
            if is_logged_in:
                try:
                    profile_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/') and contains(@href, '_')]")
                    for link in profile_links:
                        href = link.get_attribute('href')
                        if '/accounts/' not in href and '/p/' not in href and '/explore/' not in href:
                            username = href.split('/')[-1] if href.endswith('/') else href.split('/')[-1]
                            if username and len(username) > 3:
                                self.username = username
                                logger.info(f"Extracted username: {self.username}")
                                break
                    
                    if not self.username:
                        body_text = self.driver.find_element(By.TAG_NAME, "body").text
                        username_match = re.search(r'@([a-zA-Z0-9_.]+)', body_text)
                        if username_match:
                            self.username = username_match.group(1)
                            logger.info(f"Extracted username from text: {self.username}")
                except Exception as e:
                    logger.warning(f"Could not extract username: {e}")
                    self.username = "Unknown"

            if is_logged_in:
                logger.info(f"STATUS: SUCCESS ✅ - Authenticated via cookies! (Username: {self.username})")
                return True
            else:
                logger.error("STATUS: FAILED ❌ - Cookie expired or invalid.")
                return False
                
        except Exception as e:
            logger.error(f"Error during cookie login: {e}")
            return False
    
    def _handle_continue_screen(self):
        """Handle continue screen - exactly like 099.py"""
        logger.info("Checking for 'Continue' button on One Tap screen...")
        
        continue_selectors = [
            "//button[contains(text(), 'Continue')]",
            "//button[contains(., 'Continue')]",
            "//a[contains(text(), 'Continue')]",
            "//div[@role='button' and contains(., 'Continue')]",
            "//button[type='button' and contains(., 'Continue')]"
        ]
        
        for selector in continue_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                for el in elements:
                    if el.is_displayed():
                        logger.info(f"Found 'Continue' button with text: '{el.text.strip()}'. Clicking...")
                        try:
                            el.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(5)
                        return True
            except:
                continue
        
        logger.info("No active 'Continue' button detected.")
        return False
    
    def _handle_cookies(self):
        """Handle cookies - exactly like 099.py"""
        try:
            cookie_texts = [
                "Allow all cookies", "Allow essential and optional cookies",
                "Decline optional cookies", "Accept All", "Accept", "Allow", "Agree",
                "Allow essential", "Accept cookies"
            ]
            for text in cookie_texts:
                btns = self.driver.find_elements(By.XPATH, 
                    f"//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]")
                for btn in btns:
                    if btn.is_displayed():
                        btn.click()
                        logger.info(f"Clicked cookie/consent dialog button: '{text}'")
                        time.sleep(2)
                        return
        except:
            pass
    
    def _find_continue_with_instagram_button(self):
        """Find 'Continue with Instagram' button"""
        selectors = [
            "//button[contains(text(), 'Continue with Instagram')]",
            "//a[contains(text(), 'Continue with Instagram')]",
            "//div[contains(text(), 'Continue with Instagram')]",
            "//span[contains(text(), 'Continue with Instagram')]",
            "//*[contains(text(), 'Continue with Instagram')]"
        ]
        
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                for el in elements:
                    href = el.get_attribute("href") or ""
                    if "instagram.com" in href and "loginpage" not in href and "continue" not in href.lower():
                        continue
                    if el.is_displayed():
                        return el
            except:
                continue
        
        return None
    
    def connect_to_business_suite(self):
        """Connect to Business Suite - exactly like your boost script flow"""
        try:
            # ═══════════════ STEP 1: FB BUSINESS AUTH ═══════════════
            logger.info("Navigating to Facebook Business login page...")
            fb_url = "https://business.facebook.com/business/loginpage/?next=https%3A%2F%2Fbusiness.facebook.com%2Flatest%2Fhome&login_options%5B0%5D=IG"
            self.driver.get(fb_url)
            time.sleep(5)
            self._handle_cookies()
            
            existing_handles = set(self.driver.window_handles)
            logger.info("Looking for 'Continue with Instagram' button...")
            
            if not self._click_button(['Continue with Instagram', 'Instagram'], 'Continue with Instagram'):
                logger.error("✗ Button not found!")
                return False
            
            # ═══════════════ STEP 2: OATH TAB ═══════════════
            logger.info("⏳ Waiting for OAuth tab...")
            new_handle = None
            for i in range(20):
                time.sleep(1)
                diff = set(self.driver.window_handles) - existing_handles
                if diff:
                    new_handle = list(diff)[0]
                    logger.info(f"🆕 OAuth tab opened! ({i+1}s)")
                    break
            
            if not new_handle:
                logger.error("✗ OAuth tab not opened!")
                return False
            
            # ═══════════════ STEP 3: AUTHORIZE ═══════════════
            self.driver.switch_to.window(new_handle)
            time.sleep(5)
            logger.info("🔍 Clicking 'Continue as' / 'Log in as'...")
            
            if not self._click_button(['Continue as', 'Log in as', 'Allow', 'Authorize'], 'Auth'):
                ActionChains(self.driver).send_keys(Keys.ENTER).perform()
                time.sleep(3)
                logger.info("⌨️ ENTER pressed")
            
            time.sleep(8)
            
            # ═══════════════ STEP 4: FIND DASHBOARD ═══════════════
            for handle in self.driver.window_handles:
                self.driver.switch_to.window(handle)
                time.sleep(1)
                if 'business.facebook.com' in self.driver.current_url and 'login' not in self.driver.current_url.lower():
                    logger.info("🏠 Dashboard found!")
                    break
            
            # Close popups
            for _ in range(5):
                self._close_popup()
                time.sleep(0.5)
            
            logger.info("✓ Authorization complete!")
            
            # ═══════════════ STEP 5: 1st BOOST CLICK ═══════════════
            logger.info("▶ 1st Boost - Finding & Clicking...")
            if not self._navigate_to_posts_page():
                logger.error("✗ Cannot access posts page!")
                return False
            
            if not self._find_and_click_boost():
                logger.error("✗ Boost button not found!")
                return False
            logger.info("✓ 1st Boost clicked!")
            
            # ═══════════════ STEP 6: CONTINUE POPUP ═══════════════
            logger.info("▶ Clicking 'Continue' on popup...")
            time.sleep(3)
            if not self._click_button(['Continue', 'Next', 'Submit'], 'Continue Popup'):
                ActionChains(self.driver).send_keys(Keys.ENTER).perform()
                time.sleep(2)
                logger.info("⌨️ ENTER pressed")
            time.sleep(3)
            logger.info("✓ Continue clicked!")
            
            # ═══════════════ STEP 7: CONTINUE AS USER (NEW TAB) ═══════════════
            logger.info("▶ Handling 'Continue as User'...")
            all_tabs = self.driver.window_handles
            if len(all_tabs) > 1:
                self.driver.switch_to.window(all_tabs[-1])
                time.sleep(4)
                logger.info("🔄 Switched to new tab")
                logger.info(f"📄 Page: {self.driver.title[:60]}")
                
                if not self._click_button(['Continue as', 'Continue', 'Log in as', 'OK'], 'Continue as User'):
                    ActionChains(self.driver).send_keys(Keys.ENTER).perform()
                    time.sleep(2)
                    logger.info("⌨️ ENTER pressed")
                
                time.sleep(4)
                # Close this tab and go back to main
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    time.sleep(2)
                    logger.info("🔙 Returned to main tab")
            
            logger.info("✓ Continue as User done!")
            
            # ═══════════════ STEP 8: 2nd BOOST → CONTINUE → OK ═══════════════
            logger.info("▶ 2nd Boost - Find Boost → Continue → OK...")
            
            # 8A: Go to posts page & find Boost again
            if not self._navigate_to_posts_page():
                logger.error("✗ Cannot access posts page!")
                return False
            
            logger.info("🔍 Looking for 2nd Boost button...")
            if not self._find_and_click_boost():
                logger.error("✗ 2nd Boost button not found!")
                return False
            logger.info("✓ 2nd Boost clicked!")
            
            # 8B: Click Continue on popup
            logger.info("💬 Waiting for Continue popup...")
            time.sleep(3)
            if not self._click_button(['Continue', 'Next', 'Submit'], 'Continue 2nd'):
                ActionChains(self.driver).send_keys(Keys.ENTER).perform()
                time.sleep(2)
            time.sleep(3)
            logger.info("✓ Continue clicked!")
            
            # 8C: Click OK button
            logger.info("🔵 Looking for OK button...")
            time.sleep(2)
            # Close any popups first
            for _ in range(3):
                self._close_popup()
                time.sleep(0.5)
            
            if self._click_button(['OK', 'Ok', 'Confirm', 'Done', 'Submit', 'Publish', 'Continue'], 'OK BUTTON'):
                logger.info("✅ OK BUTTON CLICKED!")
            else:
                # Try blue button
                logger.info("🔍 Trying blue button...")
                try:
                    for sel in ["//button[contains(@class, 'primary')]", "//button[@type='submit']", "//div[@role='dialog']//button"]:
                        elems = self.driver.find_elements(By.XPATH, sel)
                        for elem in elems:
                            if elem.is_displayed():
                                self._js_click(elem, 'OK (blue)')
                                time.sleep(2)
                                break
                except:
                    pass
            
            time.sleep(3)
            
            # ═══════════════ STEP 9: CLOSE POPUPS & FINISH ═══════════════
            logger.info("▶ Final cleanup...")
            for _ in range(5):
                self._close_popup()
                time.sleep(0.5)
            
            logger.info("🎉🎉🎉 TASK COMPLETE! OK DONE! 🎉🎉🎉")
            
            # Get the final URL for asset_id
            final_url = self.driver.current_url
            logger.info(f"Final URL: {final_url}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to Business Suite: {e}")
            return False
    
    def get_current_url(self):
        """Get current URL"""
        try:
            return self.driver.current_url if self.driver else None
        except:
            return None
    
    def get_page_title(self):
        """Get page title"""
        try:
            return self.driver.title if self.driver else None
        except:
            return None
    
    def quit(self):
        """Clean quit with full memory cleanup"""
        if self.driver:
            try:
                self.driver.delete_all_cookies()
                for handle in self.driver.window_handles:
                    try:
                        self.driver.switch_to.window(handle)
                        self.driver.close()
                    except:
                        pass
                self.driver.quit()
            except:
                pass
            self.driver = None
        
        self._cleanup_temp_dir()
        gc.collect()
        logger.info("Chrome driver cleaned up and memory freed")
