import os
import time
import shutil
import datetime
from PIL import Image, ImageDraw, ImageFont
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from instabot import Bot

def get_day_column_index():
    # datetime.weekday(): 월=0, 화=1, ..., 금=4, 주말은 5,6
    weekday = datetime.datetime.today().weekday()
    # 테이블의 데이터 열(tds)의 인덱스가 월:0, 화:1, …로 설정됨
    if weekday < 5:
        return weekday
    else:
        # 주말엔 월요일 메뉴 사용 (0번 열)
        return 0

def get_rendered_html(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 헤드리스 모드 실행
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # ChromeDriver가 PATH에 있다면 바로 사용, 아니면 executable_path 인자를 사용하세요.
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    time.sleep(3)  # JS 로딩 대기 (필요시 시간을 늘려주세요)
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
    # 요일별 열 인덱스 (월:0, 화:1, …, 금:4)
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
        elif "중식-한식" in th_text:
            menu_dict["lunch(b)"] = day_menu
        elif "중식-일품" in th_text:
            menu_dict["lunch(j)"] = day_menu
        elif "중식-plus" in th_text:
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

def generate_menu_image(text, background_path, output_path, font_path="Pretendard-Medium.ttf", font_size=200, line_spacing=30):
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

    # 텍스트를 줄 단위로 분리
    lines = text.split("\n")
    # 각 줄의 크기를 측정합니다.
    line_sizes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    line_widths = [bbox[2] - bbox[0] for bbox in line_sizes]
    line_heights = [bbox[3] - bbox[1] for bbox in line_sizes]
    total_text_height = sum(line_heights) + line_spacing * (len(lines) - 1)
    max_line_width = max(line_widths) if line_widths else 0

    # 중앙 정렬 후 왼쪽으로 20픽셀 이동
    x = (width - max_line_width) / 2 - 950
    y = (height - total_text_height) / 2

    # 각 줄을 그리며 line_spacing을 적용합니다.
    current_y = y
    for line, h in zip(lines, line_heights):
        draw.text((x, current_y), line, fill=(0, 0, 0), font=font)
        current_y += h + line_spacing

    image.save(output_path)
    print(f"Final image saved at {output_path}")

def upload_to_instagram(image_path, caption, username, password):
    if os.path.exists("config"):
        shutil.rmtree("config")
    bot = Bot()
    bot.login(username=username, password=password)
    bot.upload_photo(image_path, caption=caption)
    uploaded_file = image_path + ".REMOVE"
    if os.path.exists(uploaded_file):
        os.remove(uploaded_file)
    time.sleep(10)

def main():
    build_dir = "build"
    if not os.path.exists(build_dir):
        os.makedirs(build_dir)
    
    username = "kus.meal"
    password = "kus2025!"
    
    student_menu = crawl_student_menu()
    backgrounds_student = {
        "morning": "build/student_morning.png",
        "lunch(b)": "build/student_lunch(b).png",
        "lunch(j)": "build/student_lunch(j).png",
        "lunch(k)": "build/student_lunch(k).png",
        "dinner": "build/student_dinner.png"
    }
    for meal, bg_path in backgrounds_student.items():
        menu_text = student_menu.get(meal, "정보 없음").replace(", ", ",\n")
        caption = f"\n{menu_text}"
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
        # staff_menu는 set이므로 첫번째 요소를 사용합니다.
        staff_menu_text = next(iter(staff_menu)) if staff_menu else "정보 없음"
        staff_menu_text = staff_menu_text.replace(", ", ",\n")
        caption = f"\n{staff_menu_text}"
        output_path = os.path.join(build_dir, f"staff_{meal}.png")
        print(f"Generating final image for staff cafeteria {meal} using background {bg_path}...")
        generate_menu_image(caption, background_path=bg_path, output_path=output_path)
        if not os.path.exists(output_path):
            print(f"Image generation failed for staff cafeteria {meal}")
            continue
        print(f"Uploading staff cafeteria {meal} with image {output_path}...")
        upload_to_instagram(output_path, caption, username, password)

if __name__ == "__main__":
    import schedule  # pip install schedule 필요
    # 매일 00:01에 main() 함수를 실행하도록 스케줄 설정
    schedule.every().day.at("00:01").do(main)
    while True:
        schedule.run_pending()
        time.sleep(30)