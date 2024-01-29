from pathlib import Path
import time
import pickle
import random
import os
import re
from datetime import datetime
import requests
import warnings
import sys
import emoji

from termcolor import colored
import speech_recognition as sr
import pydub
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# from src.helpers import system

warnings.filterwarnings("ignore", category=UserWarning)


def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def frame(driver):
    frames = driver.find_elements(By.TAG_NAME, "iframe")

    recaptcha_control_frame = None
    recaptcha_challenge_frame = None

    for index, frame in enumerate(frames):
        # Find the reCAPTCHA checkbox
        if re.search("reCAPTCHA", frame.get_attribute("title")):
            recaptcha_control_frame = frame
            print("[INF] ReCAPTCHA box located")

        # Find the reCAPTCHA puzzle
        if re.search(
            "recaptcha challenge expires in two minutes", frame.get_attribute("title")
        ):
            recaptcha_challenge_frame = frame
            print("[INF] ReCAPTCHA puzzle located")

    return recaptcha_control_frame, recaptcha_challenge_frame


def check_solved(driver, wait):
    try:
        WebDriverWait(driver, wait).until(
            expected_conditions.presence_of_element_located(
                (By.ID, "rc-anchor-container")
            )
        )

        print("[INF] ReCAPTCHA not solved")
        # print(driver.page_source)
        solved = False

    except:
        # print(driver.page_source)
        print("[INF] ReCAPTCHA solved")
        # print(driver.page_source)
        solved = True
    
    return solved


def recaptcha_solver(driver, wait, misc_directory):
    recaptcha_log = 0

    start_time = success = None

    is_recaptcha_control_active = True

    print("\n[INF] Trying to find reCAPTCHA")

    time.sleep(10)

    recaptcha_control_frame, recaptcha_challenge_frame = frame(driver)

    if not (recaptcha_control_frame and recaptcha_challenge_frame):
        print("[ERR] Unable to find reCAPTCHA")
        is_recaptcha_control_active = False

    while is_recaptcha_control_active:
        recaptcha_log += 1
        randint = random.randrange(3, 5)

        # Make sure that reCAPTCHA does not get stuck in a loop
        if recaptcha_log >= randint:
            print("[ERR] IP address has been blocked by reCAPTCHA or network error")

            success = False

            break

        try:
            # switch to checkbox

            # test to make reCAPTCHA solve fail: driver.switch_to.frame(recaptcha_challenge_frame)
            driver.switch_to.default_content()
            driver.switch_to.frame(recaptcha_control_frame)

            # click on checkbox to activate recaptcha
            WebDriverWait(driver, wait).until(
                expected_conditions.element_to_be_clickable(
                    (By.CLASS_NAME, "recaptcha-checkbox-border")
                )
            ).click()
            # driver.find_element(By.CLASS_NAME, "recaptcha-checkbox-border").click()
            print("[INF] Checkbox clicked")

            start_time = datetime.now().timestamp()

        except:
            print("[ERR] Cannot solve reCAPTCHA checkbox")

            success = False

            break
        
        # print(driver.page_source)

        if check_solved(driver, wait):
            success = True

            break

        else:
            is_recaptcha_challenge_active = True

            switched_to_audio = False
            while is_recaptcha_challenge_active:
                if not switched_to_audio:
                    # Try to click on the button that allows you to do a voice challenge
                    
                    try:
                        time.sleep(wait * 2)
                        driver.switch_to.default_content()
                        
                        time.sleep(wait * 2)
                        driver.switch_to.frame(recaptcha_challenge_frame)

                        WebDriverWait(driver, wait).until(
                            expected_conditions.element_to_be_clickable(
                                (By.ID, "recaptcha-audio-button")
                            )
                        ).click()
                        # driver.find_element(By.ID, "recaptcha-audio-button").click()
                        print("[INF] Switched to audio control frame")
                        switched_to_audio = True

                    except:
                        print("[INF] Recurring checkbox")
                        break

                # Get the audio source (the mp3 file)
                try:
                    # Switch to recaptcha audio challenge frame
                    driver.switch_to.default_content()
                    driver.switch_to.frame(recaptcha_challenge_frame)

                    # Get the mp3 audio file
                    time.sleep(wait * 2)
                    src = driver.find_element(By.ID, "audio-source").get_attribute(
                        "src"
                    )

                except Exception as e:
                    print("[ERR] Error when using Audio challenge frame")
                    print(e)
                    print(driver.page_source)
                    success = False
                    is_recaptcha_control_active = False
                    break

                file_path_mp3 = os.path.normpath(
                    os.path.join(misc_directory, "sample.mp3")
                )
                file_path_wav = os.path.normpath(
                    os.path.join(misc_directory, "sample.wav")
                )

                # Download the mp3 audio file from the source
                with open(os.path.join(misc_directory, "cookies.pkl"), "rb") as f:
                    cookie_list = pickle.load(f)

                cookie = {}
                for elem in cookie_list:
                    cookie[elem["name"]] = elem["value"]

                try:
                    s = requests.Session()
                    s.cookies = requests.utils.cookiejar_from_dict(cookie)

                    local_filename = "sample.mp3"
                    r = s.get(src, verify=False)
                    with open(os.path.join(misc_directory, local_filename), "wb") as f:
                        for chunk in r.iter_content(chunk_size=1024):
                            if chunk:  # filter out keep-alive new chunks
                                f.write(chunk)

                except Exception as e:
                    print("[ERR] Could not download audio file")
                    print(e)
                    success = False
                    is_recaptcha_control_active = False
                    break

                # Mp3 to wav conversion using ffmpeg
                try:
                    sound = pydub.AudioSegment.from_mp3(file_path_mp3)
                    sound.export(file_path_wav, format="wav")

                except Exception as e:
                    print(e)

                    is_windows = False #system()

                    print(
                        "\n"
                        + colored(" ! ", "red", attrs=["reverse"]) * (is_windows)
                        + emoji.emojize(":red_exclamation_mark:") * (not is_windows)
                        + "   Could not run ffmpeg script."
                    )

                    print(
                        "\n"
                        + colored(" i ", "blue", attrs=["reverse"]) * (is_windows)
                        + emoji.emojize(":information:") * (not is_windows)
                        + "   Consult the Aaron's Kit troubleshooting section on our website to fix this issue and restart Aaron's Toolkit."
                    )

                    driver.close()

                    os._exit(0)

                # Translate audio to text with google voice recognition
                time.sleep(5)
                r = sr.Recognizer()
                sample_audio = sr.AudioFile(file_path_wav)
                with sample_audio as source:
                    audio = r.record(source)
                    try:
                        key = r.recognize_google(audio)
                        print(f"[INF] ReCAPTCHA Passcode: {key}")
                        print("[INF] Audio Snippet was recognised")
                    except Exception as e:
                        print(
                            "[ERR] ReCAPTCHA voice segment is too difficult to solve."
                        )
                        success = False
                        is_recaptcha_control_active = False
                        break

                    # key in results and submit
                    time.sleep(5)

                    try:
                        driver.find_element(By.ID, "audio-response").send_keys(
                            key.lower()
                        )
                        driver.find_element(By.ID, "audio-response").send_keys(
                            Keys.ENTER
                        )

                        start_time = datetime.now().timestamp()

                        time.sleep(5)
                        driver.switch_to.default_content()
                        time.sleep(5)
                        print("[INF] Audio snippet submitted")

                    except Exception as e:
                        print("[ERR] IP address might have been blocked for reCAPTCHA")
                        success = False
                        is_recaptcha_control_active = False
                        break

                    # Check if reCAPTCHA has been solved
                    if check_solved(driver, wait):
                        success = True
                        is_recaptcha_control_active = False
                        break

    return success, start_time
