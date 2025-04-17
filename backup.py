import os
import time
import datetime
import requests
from bs4 import BeautifulSoup  # 새로 추가된 모듈
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv  # 환경변수 로드
import datetime

# .env 파일 로드
load_dotenv()

def crawl_menu_data():
    # MENU_PAGE_URL 환경변수에 크롤링할 페이지 URL을 설정합니다.
    url = os.environ.get("MENU_PAGE_URL", "https://sejong.korea.ac.kr/koreaSejong/8028/subview.do")
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"HTTP error! status: {response.status_code}")
            return None
    except Exception as e:
        print(f"메뉴 페이지 요청 에러: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    days = ['월', '화', '수', '목', '금']
    result = {}

    for menu_block in soup.select(".diet-menu"):
        title_el = menu_block.select_one(".title")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        print(f"\n🍽️ {title}")

        # 제목에 따라 식당 구분 (필요에 따라 조정)
        if "학생" in title:
            cafeteria = "학생식당"
        elif "교직원" in title:
            cafeteria = "교직원식당"
        else:
            cafeteria = title

        if cafeteria not in result:
            result[cafeteria] = {"메뉴": {}}

        rows = menu_block.select("table tbody tr")
        for row_index, row in enumerate(rows):
            if row_index == 0:
                meal_label = "조식"
            elif row_index == 1:
                meal_label = "중식 - 한식"
            elif row_index == 2:
                meal_label = "중식 - 일품"
            elif row_index == 3:
                meal_label = "중식 - 분식"
            elif row_index == 5:
                meal_label = "석식"
            else:
                meal_label = f"기타{row_index}"

            if meal_label not in result[cafeteria]["메뉴"]:
                result[cafeteria]["메뉴"][meal_label] = {}

            cells = row.find_all("td")
            for cell_index, cell in enumerate(cells):
                day = days[cell_index] if cell_index < len(days) else f"Day{cell_index+1}"
                p_el = cell.select_one("p.offTxt")
                if not p_el:
                    continue
                menu_items = list(p_el.stripped_strings)
                if menu_items:
                    print(f"\n📆 {day}요일 ({meal_label})")
                    for idx, item in enumerate(menu_items):
                        print(f"  {idx+1}. {item}")
                    result[cafeteria]["메뉴"][meal_label][day] = {"메뉴": menu_items}
    return result

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

    date_font_size = int(font_size * 0.75)
    try:
        date_font = ImageFont.truetype(font_path, date_font_size)
    except IOError:
        print(f"폰트 파일을 찾을 수 없습니다: {font_path}")
        date_font = ImageFont.load_default()

    # 날짜를 고정 위치 (x=2600, 이미지 높이의 23%)에 그립니다.
    date_str = datetime.datetime.today().strftime("%Y년 %m월 %d일")
    date_x = 2600
    date_y = height * 0.23
    draw.text((date_x, date_y), date_str, fill=text_color, font=date_font)
    
    # 메뉴 텍스트 시작 위치 (x=500, 이미지 높이의 40%)에 그립니다.
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
    client = Client()
    client.login(username, password)
    client.photo_upload(image_path, caption)

def main():
    build_dir = "build"
    if not os.path.exists(build_dir):
        os.makedirs(build_dir)
    
    # .env에서 인스타그램 자격 증명을 불러옵니다.
    username = os.environ.get("IG_USERNAME")
    password = os.environ.get("IG_PASSWORD")
    if not username or not password:
        print("Instagram 자격 증명이 설정되어 있지 않습니다.")
        return

    menu_data = crawl_menu_data()
    if not menu_data:
        print("전체 메뉴 데이터를 불러오는데 실패했습니다.")
        return

    # 학생식당 처리
    student_api = menu_data.get("학생식당", {})
    if not student_api.get("메뉴"):
        print("학생식당 메뉴 데이터가 없습니다.")
    else:
        student_menu_api = student_api["메뉴"]
        student_menu = {
            "조식": "정보 없음",
            "중식 - 한식": "정보 없음",
            "중식 - 분식": "정보 없음",
            "중식 - 일품": "정보 없음",
            "석식": "정보 없음"
        }
    # 오늘 요일 결정 (월=0, ..., 일=6). 주중(월~금)가 아니면 월요일 메뉴 사용
    weekday = datetime.datetime.today().weekday()  
    target_day = ["월", "화", "수", "목", "금"][weekday] if weekday < 5 else "월"

    for meal in ["조식", "중식 - 한식", "중식 - 분식", "중식 - 일품", "석식"]:
        meal_data = student_menu_api.get(meal, {})
        if meal_data and target_day in meal_data:
            items = meal_data[target_day].get("메뉴", [])
            if items:
                student_menu[meal] = "\n".join(items)
    backgrounds_student = {
        "조식": "assets/morning.png",
        "중식 - 한식": "assets/lunch(k).png",
        "중식 - 분식": "assets/lunch(b).png",
        "중식 - 일품": "assets/lunch(j).png",
        "석식": "assets/dinner.png"
    }

    for meal, bg_path in backgrounds_student.items():
        menu_text = student_menu.get(meal, "정보 없음")
        caption = menu_text
        output_path = os.path.join(build_dir, f"student_{meal}.png")
        print(f"Generating final image for student cafeteria {meal} using background {bg_path}...")
        generate_menu_image(caption, background_path=bg_path, output_path=output_path)
        if not os.path.exists(output_path):
            print(f"Image generation failed for student cafeteria {meal}")
        else:
            print(f"Uploading student cafeteria {meal} with image {output_path}...")
            upload_to_instagram(output_path, caption, username, password)

    # 교직원식당 처리
    staff_api = menu_data.get("교직원식당", {})
    # 여러 식사(예: 조식, 중식)를 처리할 수 있도록 딕셔너리 사용
    staff_menu_text = {}
    backgrounds_staff = {}
    # 여기서 원하는 식사 목록 설정 (현재 교직원은 중식만 존재)
    meals = ["중식"]
    
    for meal in meals:
        if "메뉴" in staff_api and meal in staff_api["메뉴"]:
            weekday = datetime.datetime.today().weekday()  
            target_day_staff = ["월", "화", "수", "목", "금"][weekday] if weekday < 5 else "월"
            menu_items = staff_api["메뉴"][meal].get(target_day_staff, {}).get("메뉴")
            if menu_items:
                staff_menu_text[meal] = "\n".join(menu_items)
                # 각 식사에 따른 배경 이미지 등록 (교직원 조식 이미지가 있다면 해당 경로로)
                if meal == "중식":
                    backgrounds_staff[meal] = "assets/lunch(t).png"
    
    for meal, bg_path in backgrounds_staff.items():
        caption = staff_menu_text.get(meal, "정보 없음")
        output_path = os.path.join(build_dir, f"staff_{meal}.png")
        print(f"Generating final image for staff cafeteria {meal} using background {bg_path}...")
        generate_menu_image(caption, background_path=bg_path, output_path=output_path)
        if not os.path.exists(output_path):
            print(f"Image generation failed for staff cafeteria {meal}")
        else:
            print(f"Uploading staff cafeteria {meal} with image {output_path}...")
            upload_to_instagram(output_path, caption, username, password)

if __name__ == "__main__":
    main()