import os
import time
import shutil
import datetime
from PIL import Image, ImageDraw, ImageFont
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from dotenv import load_dotenv  # 추가: 환경변수 로드 모듈

# .env 파일 로드
load_dotenv()

def get_day_column_index():
    # datetime.weekday(): 월=0, 화=1, ..., 금=4, 주말은 5,6
    weekday = datetime.datetime.today().weekday()
    if weekday < 5:
        return weekday
    else:
        return 0

def get_rendered_html(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 헤드리스 모드 실행
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    time.sleep(3)  # JS 로딩 대기
    html = driver.page_source
    driver.quit()
    return html

def crawl_student_menu():
    url = "https://www.kus-bus.site/menu"
    html = get_rendered_html(url)
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', class_="menu-table")
    if not table:
        print("학생 메뉴 테이블을 찾지 못했습니다.")
        return {"정보 없음", "정보 없음", "정보 없음", "정보 없음", "정보 없음"}
    col_index = get_day_column_index()
    menu_dict = {"morning": "정보 없음", "lunch(b)": "정보 없음", 
                 "lunch(j)": "정보 없음", "lunch(k)": "정보 없음", 
                 "dinner": "정보 없음"}
    rows = table.find('tbody').find_all('tr')
    for row in rows:
        th = row.find('th')
        if not th:
            continue
        th_text = th.get_text(" ", strip=True)
        tds = row.find_all('td')
        day_menu = "정보 없음"
        if len(tds) > col_index:
            menu_items = [div.get_text(strip=True) for div in tds[col_index].find_all('div', class_="menu-item")]
            if menu_items:
                day_menu = ", ".join(menu_items)
        if "조식" in th_text:
            menu_dict["morning"] = day_menu
        elif "중식-분식" in th_text:
            menu_dict["lunch(b)"] = day_menu
        elif "중식-일품" in th_text:
            menu_dict["lunch(j)"] = day_menu
        elif "중식-한식" in th_text:
            menu_dict["lunch(k)"] = day_menu
        elif "석식" in th_text:
            menu_dict["dinner"] = day_menu
    return menu_dict

def crawl_staff_menu():
    url = "https://www.kus-bus.site/menu"
    html = get_rendered_html(url)
    soup = BeautifulSoup(html, 'html.parser')
    staff_section = soup.find('div', id="staffCafeteria", class_="cafeteria-section")
    if not staff_section:
        print("교직원 식당 섹션을 찾지 못했습니다.")
        return {"정보 없음"}
    table = staff_section.find('table', class_="menu-table")
    if not table:
        print("교직원 메뉴 테이블을 찾지 못했습니다.")
        return {"정보 없음"}
    col_index = get_day_column_index()
    day_menu = "정보 없음"
    tbody = table.find('tbody')
    if tbody:
        row = tbody.find('tr')
        if row:
            tds = row.find_all('td')
            if len(tds) > col_index:
                menu_items = [div.get_text(strip=True) for div in tds[col_index].find_all('div', class_="menu-item")]
                if menu_items:
                    day_menu = ", ".join(menu_items)
    return {day_menu}

def generate_menu_image(text, background_path, output_path, font_path="Pretendard-Medium.ttf", font_size=200, line_spacing=30, text_color=(51, 51, 51)):
    try:
        image = Image.open(background_path).convert("RGB")
    except Exception as e:
        print(f"배경 이미지 열기 실패 ({background_path}): {e}")
        return
    draw = ImageDraw.Draw(image)
    width, height = image.size
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        print(f"폰트 파일을 찾을 수 없습니다: {font_path}")
        font = ImageFont.load_default()

    # 날짜용 폰트 크기를 기존 폰트 크기의 50%로 설정
    date_font_size = int(font_size * 0.75)
    try:
        date_font = ImageFont.truetype(font_path, date_font_size)
    except IOError:
        print(f"폰트 파일을 찾을 수 없습니다: {font_path}")
        date_font = ImageFont.load_default()

    # 날짜를 고정 위치에 그립니다. (왼쪽 70px, 이미지 높이의 10% 위치)
    date_str = datetime.datetime.today().strftime("%Y년 %m월 %d일")
    date_x = 2600
    date_y = height * 0.23
    draw.text((date_x, date_y), date_str, fill=text_color, font=date_font)
    
    # 메뉴 텍스트의 시작 위치를 별도로 지정 (왼쪽 70px, 이미지 높이의 30% 위치)
    menu_x = 500
    menu_y = height * 0.4
    lines = text.split("\n")
    current_y = menu_y
    for line in lines:
        draw.text((menu_x, current_y), line, fill=text_color, font=font)
        bbox = draw.textbbox((0, 0), line, font=font)
        line_height = bbox[3] - bbox[1]
        current_y += line_height + line_spacing

    image.save(output_path)
    print(f"Final image saved at {output_path}")

def upload_to_instagram(image_path, caption, username, password):
    from instagrapi import Client
    cl = Client()
    cl.login(username, password)
    cl.photo_upload(image_path, caption)
    time.sleep(0)

def main():
    build_dir = "build"
    if not os.path.exists(build_dir):
        os.makedirs(build_dir)
    
    # .env에서 인스타그램 자격증명을 불러옵니다.
    username = os.environ.get("IG_USERNAME")
    password = os.environ.get("IG_PASSWORD")
    if not username or not password:
        print("Instagram 자격 증명이 설정되어 있지 않습니다.")
        return

    student_menu = crawl_student_menu()
    backgrounds_student = {
        "morning": "assets/morning.png",
        "lunch(b)": "assets/lunch(b).png",
        "lunch(j)": "assets/lunch(j).png",
        "lunch(k)": "assets/lunch(k).png",
        "dinner": "assets/dinner.png"
    }
    for meal, bg_path in backgrounds_student.items():
        menu_text = student_menu.get(meal, "정보 없음").replace(", ", ",\n")
        caption = f"{menu_text}"  # 앞에 불필요한 개행 제거
        output_path = os.path.join(build_dir, f"student_{meal}.png")
        print(f"Generating final image for student cafeteria {meal} using background {bg_path}...")
        generate_menu_image(caption, background_path=bg_path, output_path=output_path)
        if not os.path.exists(output_path):
            print(f"Image generation failed for student cafeteria {meal}")
            continue
        print(f"Uploading student cafeteria {meal} with image {output_path}...")
        upload_to_instagram(output_path, caption, username, password)
    
    staff_menu = crawl_staff_menu()
    backgrounds_staff = {
        "lunch(t)": "assets/lunch(t).png"
    }
    for meal, bg_path in backgrounds_staff.items():
        staff_menu_text = next(iter(staff_menu)) if staff_menu else "정보 없음"
        staff_menu_text = staff_menu_text.replace(", ", ",\n")
        caption = f"{staff_menu_text}"  # 앞에 불필요한 개행 제거
        output_path = os.path.join(build_dir, f"staff_{meal}.png")
        print(f"Generating final image for staff cafeteria {meal} using background {bg_path}...")
        generate_menu_image(caption, background_path=bg_path, output_path=output_path)
        if not os.path.exists(output_path):
            print(f"Image generation failed for staff cafeteria {meal}")
            continue
        print(f"Uploading staff cafeteria {meal} with image {output_path}...")
        upload_to_instagram(output_path, caption, username, password)

if __name__ == "__main__":
    main()