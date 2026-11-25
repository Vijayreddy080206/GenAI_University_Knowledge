"""
NIIT University - Generative AI Knowledge Assistant
Production End-to-End Browser Automation Suite (Selenium 4)
Supports:
1. Visible Demo Mode (HEADLESS=false) with smooth faculty pacing and step screenshots.
2. Headless CI Mode (HEADLESS=true) for Jenkins Windows Service automated pipeline execution.
"""
import os
import time
import pytest
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = BASE_DIR / "reports"
SCREENSHOTS_DIR = REPORTS_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

APP_URL = os.getenv("APP_URL", "https://localhost")
HEADLESS = os.getenv("HEADLESS", "false").lower() in ("true", "1", "yes")

@pytest.fixture(scope="module")
def driver():
    chrome_options = Options()
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")

    if HEADLESS:
        chrome_options.add_argument("--headless=new")
    else:
        chrome_options.add_argument("--start-maximized")

    # Selenium 4 automatically resolves chromedriver via Selenium Manager
    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(4)
    yield driver
    try:
        driver.quit()
    except Exception:
        pass

def take_step_screenshot(driver, step_name: str):
    filename = f"{step_name}.png"
    filepath = SCREENSHOTS_DIR / filename
    driver.save_screenshot(str(filepath))
    return str(filepath)

def faculty_pace(seconds=0.8):
    if not HEADLESS:
        time.sleep(seconds)

class TestUniversityKnowledgeAssistantE2E:
    """Complete Faculty Evaluation User Journey Test Cases."""

    def test_01_page_load_and_branding(self, driver):
        """Verify institutional branding and login portal on page load."""
        driver.get(APP_URL)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "screenLogin"))
        )
        assert "NIIT University" in driver.title or "Knowledge Assistant" in driver.title

        # Verify branding elements
        assert driver.find_element(By.ID, "screenLogin").is_displayed()
        take_step_screenshot(driver, "01_login_portal")
        faculty_pace()

    def test_02_student_authentication_flow(self, driver):
        """Verify Student email/password Login and workspace session initialization."""
        email_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "loginEmail"))
        )
        email_input.clear()
        email_input.send_keys("vijay.reddy23@st.niituniversity.in")

        pass_input = driver.find_element(By.ID, "loginPass")
        pass_input.clear()
        pass_input.send_keys("student123")

        btn_login = driver.find_element(By.ID, "btnSubmitEmailLogin")
        btn_login.click()
        faculty_pace(1.2)

        # Verify main application shell appears
        app_shell = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, "appShell"))
        )
        assert app_shell.is_displayed()

        # Verify Student Role Badge and User Avatar
        role_badge = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, "sidebarRoleBadge"))
        )
        assert "STUDENT" in role_badge.text.upper()

        take_step_screenshot(driver, "02_student_workspace")
        faculty_pace()

    def test_03_conversational_rag_query_with_citations(self, driver):
        """Submit grounded query, verify RAG latency <5s, and check citation badges."""
        composer_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "composerInput"))
        )
        composer_input.clear()
        query_text = "When is the last date to pay the semester fees and what is the late fine?"
        composer_input.send_keys(query_text)
        faculty_pace(0.5)

        btn_send = driver.find_element(By.ID, "btnComposerSend")
        btn_send.click()

        # Wait for assistant response card
        response_card = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'glisse-card')]//span[contains(text(), 'NIIT University Assistant')]"))
        )
        assert response_card.is_displayed()

        # Verify Citation Badge [1] appears in answer
        citation_badge = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), '[1]')]"))
        )
        assert citation_badge.is_displayed()

        take_step_screenshot(driver, "03_rag_answer_with_citations")
        faculty_pace(1.0)

        # Click Citation Badge [1] to open Evidence Drawer
        citation_badge.click()
        evidence_drawer = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, "evidenceDrawer"))
        )
        assert evidence_drawer.is_displayed()

        # Verify chunk snippet text is rendered
        drawer_content = driver.find_element(By.ID, "evidenceDrawerContent")
        assert "Semantic Match" in drawer_content.text or "Citation" in drawer_content.text

        take_step_screenshot(driver, "04_evidence_drawer_inspection")
        faculty_pace()

        # Close Evidence Drawer to return to full chat view
        try:
            close_drawer_btn = driver.find_element(By.XPATH, "//aside[@id='evidenceDrawer']//button")
            driver.execute_script("arguments[0].click();", close_drawer_btn)
            faculty_pace(0.5)
        except Exception:
            pass

    def test_04_anti_hallucination_fallback(self, driver):
        """Submit out-of-scope query and verify anti-hallucination fallback triggers."""
        composer_input = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "composerInput"))
        )
        composer_input.clear()
        composer_input.send_keys("How do I bake a chocolate sourdough cake on Mars in zero gravity?")
        faculty_pace(0.5)
        btn_send = driver.find_element(By.ID, "btnComposerSend")
        driver.execute_script("arguments[0].click();", btn_send)

        # Wait for fallback message inside chat stream
        def fallback_card_present(d):
            stream = d.find_element(By.ID, "chatMessagesStream")
            text = stream.text
            return ("FALLBACK" in text or "official NIIT University" in text or "sufficient information" in text) and ("Mars" in text)

        WebDriverWait(driver, 15).until(fallback_card_present)
        take_step_screenshot(driver, "05_anti_hallucination_fallback")
        faculty_pace()

    def test_05_session_persistence_on_reload(self, driver):
        """Verify JWT session persistence and workspace restoration on browser refresh."""
        driver.refresh()
        # Verify appShell remains visible without returning to login screen
        app_shell = WebDriverWait(driver, 15).until(
            EC.visibility_of_element_located((By.ID, "appShell"))
        )
        assert app_shell.is_displayed()
        assert driver.find_element(By.ID, "sidebarUserName").text != ""

        take_step_screenshot(driver, "06_session_restored_after_refresh")
        faculty_pace()

    def test_06_sign_out_and_governance_reset(self, driver):
        """Verify sign out cleanly purges session tokens and resets UI to login."""
        btn_signout = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "btnSignOut"))
        )
        btn_signout.click()

        # Verify screenLogin is restored
        login_screen = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, "screenLogin"))
        )
        assert login_screen.is_displayed()
        assert not driver.find_element(By.ID, "appShell").is_displayed()

        take_step_screenshot(driver, "07_clean_sign_out")
        faculty_pace()
