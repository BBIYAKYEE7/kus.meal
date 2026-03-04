import os
import time
import datetime
from datetime import timedelta
import requests
import urllib3
import random
from bs4 import BeautifulSoup  # 새로 추가된 모듈
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv  # 환경변수 로드
import datetime

# SSL 경고 비활성화
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# .env 파일 로드
load_dotenv()

def crawl_menu_data():
    # MENU_PAGE_URL 환경변수에 크롤링할 페이지 URL을 설정합니다.
    url = os.environ.get("MENU_PAGE_URL", "https://sejong.korea.ac.kr/koreaSejong/8028/subview.do")
    try:
        response = requests.get(url, timeout=10, verify=False)
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

def crawl_menu_with_retry(max_attempts=5, delay_between_attempts=30):
    """메뉴 데이터를 성공할 때까지 재시도하는 함수"""
    import time
    
    for attempt in range(max_attempts):
        print(f"\n📡 메뉴 크롤링 시도 {attempt + 1}/{max_attempts}...")
        menu_data = crawl_menu_data()
        
        if menu_data:
            # 학생식당 메뉴가 제대로 있는지 확인
            student_api = menu_data.get("학생식당", {})
            if student_api.get("메뉴"):
                # 오늘 날짜의 메뉴가 있는지 확인
                weekday = datetime.datetime.today().weekday()
                target_day = ["월", "화", "수", "목", "금"][weekday] if weekday < 5 else "월"
                
                has_menu = False
                for meal in ["조식", "중식 - 한식", "중식 - 분식", "중식 - 일품", "석식"]:
                    meal_data = student_api["메뉴"].get(meal, {})
                    if meal_data and target_day in meal_data:
                        items = meal_data[target_day].get("메뉴", [])
                        if items:  # 실제 메뉴 아이템이 있으면
                            has_menu = True
                            break
                
                if has_menu:
                    print(f"✅ 메뉴 크롤링 성공! ({target_day}요일 메뉴 확인됨)")
                    return menu_data
                else:
                    print(f"⚠️ 메뉴 데이터는 있지만 {target_day}요일 메뉴가 비어있음")
            else:
                print("⚠️ 학생식당 메뉴 데이터가 없음")
        else:
            print("❌ 메뉴 크롤링 실패")
        
        if attempt < max_attempts - 1:
            print(f"⏰ {delay_between_attempts}초 후 재시도...")
            time.sleep(delay_between_attempts)
        else:
            print("❌ 모든 재시도 실패. 메뉴를 불러올 수 없습니다.")
    
    return None

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

    # 텍스트 치수 호환성 헬퍼: Pillow 버전에 따라 textbbox가 없을 수 있으므로 폴백을 제공합니다.
    def _text_bbox(draw_obj, txt, fnt):
        try:
            return draw_obj.textbbox((0, 0), txt, font=fnt)
        except Exception:
            # draw.textsize/ font.getsize 를 이용해 (0,0,w,h) 형태로 반환
            try:
                w, h = draw_obj.textsize(txt, font=fnt)
            except Exception:
                w, h = fnt.getsize(txt)
            return (0, 0, w, h)

    # 날짜를 원래의 좌우 위치(고정 x)에 두고, 세로 위치만 조정합니다.
    date_str = datetime.datetime.today().strftime("%Y년 %m월 %d일")
    date_x = 2600
    date_y = height * 0.13  # 0.18에서 0.13으로 줄여서 위로 이동
    draw.text((date_x, date_y), date_str, fill=text_color, font=date_font)

    # 메뉴 텍스트는 원래의 왼쪽 x 위치를 유지하고 세로 위치만 조정하여 그립니다.
    menu_x = 500
    menu_y = height * 0.38
    lines = text.split("\n")
    current_y = menu_y
    for line in lines:
        bbox = _text_bbox(draw, line, font)
        line_height = bbox[3] - bbox[1]
        draw.text((menu_x, current_y), line, fill=text_color, font=font)
        current_y += line_height + line_spacing

    image.save(output_path)
    print(f"Final image saved at {output_path}")

def upload_to_instagram(image_path, caption, username, password):
    from instagrapi import Client
    from instagrapi.exceptions import LoginRequired, ChallengeRequired, FeedbackRequired
    import json
    import random
    
    if not username or not password:
        print("Instagram 자격 증명이 설정되어 있지 않습니다.")
        return False
    
    session_file = "config/instagram_session.json"
    
    try:
        client = Client()
        
        # 향상된 클라이언트 설정 (봇 탐지 회피)
        client.delay_range = [1, 3]  # 요청 간격 랜덤화
        
        # 세션 로드 시도
        login_success = False
        if os.path.exists(session_file):
            try:
                client.load_settings(session_file)
                client.get_timeline_feed()  # 세션 유효성 검증
                login_success = True
                print("저장된 세션으로 로그인 성공!")
            except (LoginRequired, ChallengeRequired, FeedbackRequired) as e:
                print(f"저장된 세션 만료: {e}")
                # 세션 파일 삭제 후 새로 로그인
                if os.path.exists(session_file):
                    os.remove(session_file)
            except Exception as e:
                print(f"세션 로드 오류: {e}")
                if os.path.exists(session_file):
                    os.remove(session_file)
        
        if not login_success:
            print(f"Instagram 새 로그인 시도: {username}")
            # 재시도 로직 추가
            for attempt in range(3):
                try:
                    client = Client()  # 새 클라이언트 인스턴스
                    client.delay_range = [1, 3]
                    time.sleep(random.uniform(2, 5))  # 랜덤 지연
                    client.login(username, password)
                    login_success = True
                    break
                except (ChallengeRequired, FeedbackRequired) as e:
                    print(f"로그인 시도 {attempt + 1} 실패: {e}")
                    if attempt == 2:  # 마지막 시도
                        raise e
                    time.sleep(random.uniform(5, 10))
        
        # 세션 저장
        if login_success:
            os.makedirs("config", exist_ok=True)
            client.dump_settings(session_file)
            print("로그인 성공, 세션 저장됨!")
            
            # 업로드 시도 (재시도 로직 포함)
            print(f"이미지 업로드 중: {image_path}")
            for upload_attempt in range(2):
                try:
                    time.sleep(random.uniform(1, 3))  # 업로드 전 지연
                    media = client.photo_upload(image_path, caption)
                    print(f"업로드 성공! 미디어 ID: {media.id}")
                    return True
                except Exception as upload_e:
                    print(f"업로드 시도 {upload_attempt + 1} 실패: {upload_e}")
                    if upload_attempt == 1:
                        raise upload_e
                    time.sleep(random.uniform(3, 7))
        
        return False
        
    except ChallengeRequired as e:
        print(f"Instagram 보안 검증 필요: {e}")
        print("해결 방법:")
        print("1. Instagram 앱/웹사이트에서 로그인하여 보안 검증 완료")
        print("2. 30분~1시간 후 재시도")
        print("3. 새로운 기기로 인식되었을 가능성 - 앱에서 승인 필요")
        
    except FeedbackRequired as e:
        print(f"Instagram 계정 제한: {e}")
        print("해결 방법:")
        print("1. 계정이 일시적으로 제한됨 - 24시간 후 재시도")
        print("2. 스팸으로 분류되었을 가능성 - 며칠 후 재시도")
        
    except LoginRequired as e:
        print(f"로그인 필요: {e}")
        print("계정 정보를 확인하고 다시 시도해주세요")
        
    except Exception as e:
        error_msg = str(e)
        print(f"Instagram 오류: {type(e).__name__}: {e}")
        if "two_factor" in error_msg.lower():
            print("2단계 인증이 활성화되어 있습니다. 비활성화해주세요")
        elif "checkpoint" in error_msg.lower():
            print("계정 검증이 필요합니다. Instagram 앱에서 확인해주세요")
    
    # 오류 시 세션 파일 삭제
    if os.path.exists(session_file):
        os.remove(session_file)
    return False

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

    # 메뉴 데이터를 성공할 때까지 재시도
    menu_data = crawl_menu_with_retry(max_attempts=3, delay_between_attempts=30)
    if not menu_data:
        print("❌ 초기 크롤링 시도 실패. 1시간 후 재시도합니다.")
        return False  # False를 반환하여 재시도 필요함을 알림

    # 학생식당 처리
    student_api = menu_data.get("학생식당", {})
    if not student_api.get("메뉴"):
        print("학생식당 메뉴 데이터가 없습니다.")
        return False  # False를 반환하여 재시도 필요함을 알림
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
                else:
                    print(f"⚠️ {meal} 메뉴가 비어있습니다. 업로드 건너뜀.")
            else:
                print(f"⚠️ {meal} 메뉴 데이터가 없습니다. 업로드 건너뜀.")
    backgrounds_student = {
        "조식": "assets/morning.png",
        "중식 - 한식": "assets/lunch(k).png",
        "중식 - 분식": "assets/lunch(b).png",
        "중식 - 일품": "assets/lunch(j).png",
        "석식": "assets/dinner.png"
    }

    meal = {
        "조식": "morning",
        "중식 - 한식": "lunch_k",
        "중식 - 분식": "lunch_b",
        "중식 - 일품": "lunch_j",
        "석식": "dinner"
    }

    for menu_name, bg_path in backgrounds_student.items():
        if menu_name in student_menu:  # 메뉴 데이터가 있는 경우만 처리
            menu_text = student_menu[menu_name]
            caption = menu_text
            output_path = os.path.join(build_dir, f"student_{menu_name}.png")
            print(f"📸 {menu_name} 이미지 생성 중... (배경: {bg_path})")
            generate_menu_image(caption, background_path=bg_path, output_path=output_path)
            if not os.path.exists(output_path):
                print(f"❌ {menu_name} 이미지 생성 실패")
            else:
                print(f"📤 {menu_name} 업로드 중... (이미지: {output_path})")
                upload_success = upload_to_instagram(output_path, caption, username, password)
                if upload_success:
                    print(f"✅ {menu_name} 업로드 성공!")
                else:
                    print(f"❌ {menu_name} 업로드 실패, 다음 메뉴로 계속...")
        else:
            print(f"⏭️ {menu_name} 메뉴 없음 - 업로드 건너뜀")

    # 교직원식당 처리
    staff_api = menu_data.get("교직원식당", {})
    staff_menu = {}
    backgrounds_staff = {"조식": "assets/lunch(t).png"}
    meals = ["조식"]

    for meal in meals:
        if "메뉴" in staff_api and meal in staff_api["메뉴"]:
            weekday = datetime.datetime.today().weekday()
            target_day_staff = ["월", "화", "수", "목", "금"][weekday] if weekday < 5 else "월"
            menu_items = staff_api["메뉴"][meal].get(target_day_staff, {}).get("메뉴")
            if menu_items:
                staff_menu[meal] = "\n".join(menu_items)
            else:
                print(f"⚠️ 교직원식당 {meal} 메뉴가 비어있습니다. 업로드 건너뜀.")
        else:
            print(f"⚠️ 교직원식당 {meal} 메뉴 데이터가 없습니다. 업로드 건너뜀.")

    for menu_name, bg_path in backgrounds_staff.items():
        if menu_name in staff_menu:  # 메뉴 데이터가 있는 경우만 처리
            caption = staff_menu[menu_name]
            output_path = os.path.join(build_dir, f"staff_{menu_name}.png")
            print(f"📸 교직원식당 {menu_name} 이미지 생성 중... (배경: {bg_path})")
            generate_menu_image(caption, background_path=bg_path, output_path=output_path)
            if not os.path.exists(output_path):
                print(f"❌ 교직원식당 {menu_name} 이미지 생성 실패")
            else:
                print(f"📤 교직원식당 {menu_name} 업로드 중... (이미지: {output_path})")
                upload_success = upload_to_instagram(output_path, caption, username, password)
                if upload_success:
                    print(f"✅ 교직원식당 {menu_name} 업로드 성공!")
                else:
                    print(f"❌ 교직원식당 {menu_name} 업로드 실패, 다음 메뉴로 계속...")
        else:
            print(f"⏭️ 교직원식당 {menu_name} 메뉴 없음 - 업로드 건너뜀")
    
    print("✅ 모든 메뉴 처리 완료!")
    return True  # 성공적으로 완료

def run_main_with_retry():
    """메뉴 크롤링이 성공할 때까지 1시간 간격으로 재시도하는 함수"""
    while True:
        try:
            print(f"\n🚀 메뉴 처리 시작: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            success = main()
            if success:
                print("✅ 메뉴 처리가 성공적으로 완료되었습니다!")
                break  # 성공하면 루프 종료
            else:
                print("❌ 메뉴 크롤링 실패. 1시간 후 다시 시도합니다.")
                print(f"⏰ 다음 시도 시간: {(datetime.datetime.now() + datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')}")
                time.sleep(3600)  # 1시간 = 3600초 대기
        except KeyboardInterrupt:
            print("\n❌ 사용자가 프로그램을 중단했습니다.")
            break
        except Exception as e:
            print(f"❌ 예상치 못한 오류 발생: {e}")
            print("⏰ 1시간 후 재시도합니다.")
            time.sleep(3600)

if __name__ == "__main__":
    import schedule  # pip install schedule 필요
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        # 월요일만 07:00에 업로드하도록 설정하고, 나머지는 기존 시간(00:00)을 유지합니다.
        at_time = "07:00" if day == "monday" else "00:00"
        schedule.every().__getattribute__(day).at(at_time).do(run_main_with_retry)
    while True:
        schedule.run_pending()
        time.sleep(30)