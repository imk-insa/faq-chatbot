import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from fuzzywuzzy import process
import json
import base64
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ✅ Google Sheets API 연결
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Streamlit Secrets에서 credentials.json 가져오기
google_credentials = st.secrets["google"]["credentials"]

# base64로 인코딩된 JSON을 파이썬 딕셔너리로 변환
decoded_credentials = base64.b64decode(google_credentials).decode('utf-8')
creds_dict = json.loads(decoded_credentials)

# 자격 증명 객체 만들기
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

# ✅ Google Sheets 스프레드시트 열기 (한 개의 스프레드시트에서 모든 시트 관리)
spreadsheet = client.open("FAQ_Chatbot_DB")  # 📝 스프레드시트 이름 통합
faq_sheet = spreadsheet.worksheet("FAQ_DB")  # 📝 FAQ 데이터 시트
log_sheet = spreadsheet.worksheet("FAQ_Logs")  # 📝 로그 저장용 시트
blocked_sheet = spreadsheet.worksheet("Blocked_Questions")  # 🚨 차단된 질문 기록용 시트

@st.cache_data
def load_faq_data():
    """ Google Sheets에서 FAQ 데이터를 불러와 DataFrame으로 변환 """
    try:
        faq_data = faq_sheet.get_all_values()
        if len(faq_data) > 1:
            return pd.DataFrame(faq_data[1:], columns=faq_data[0])
        else:
            return pd.DataFrame(columns=["질문", "답변"])  # 데이터가 없는 경우 빈 DataFrame 반환
    except Exception as e:
        st.error(f"❌ Google Sheets 데이터 로드 오류: {e}")
        return pd.DataFrame(columns=["질문", "답변"])

df = load_faq_data()

# ✅ 로그 저장 함수
def save_chat_log_to_google_sheets(question, answer, feedback):
    try:
        log_sheet.append_row([question, answer, feedback])
    except Exception as e:
        st.error(f"❌ 로그 저장 오류: {e}")

# ✅ 금지어 목록 (필요에 따라 추가 가능)
blocked_keywords = ["ㅅㅂ", "ㅄ", "폭력", "혐오", "불법"]

# ✅ 금지된 질문인지 확인하는 함수
def is_blocked_question(user_input):
    for word in blocked_keywords:
        if word in user_input.lower():  # 소문자로 변환 후 체크
            return True
    return False

# ✅ 차단된 질문을 Google Sheets에 저장하는 함수
def save_blocked_question(user_input):
    try:
        blocked_sheet.append_row([user_input, "차단된 질문"])
    except Exception as e:
        st.error(f"❌ 차단된 질문 저장 오류: {e}")

# ✅ 이메일 보내는 함수
def send_email(user_input, answer):
    sender_email = "imkinsa@gmail.com"  # 발신자 이메일
    receiver_email = "junh.park@imarketkorea.com"  # 수신자 이메일 (담당자 이메일)
    
    # Streamlit Secrets에서 비밀번호 가져오기
    password = st.secrets["email"]["EMAIL_PASSWORD"]

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = "FAQ 챗봇 - 질문 전송"

    body = f"질문: {user_input}\n답변: {answer}"
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, password)
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)
        server.quit()
        st.success("✅ 담당자에게 이메일이 전송되었습니다.")
    except Exception as e:
        st.error(f"❌ 이메일 전송 오류: {e}")


# 🎨 제목
st.markdown("<h1 style='text-align: center; color: blue;'>FAQ 챗봇</h1>", unsafe_allow_html=True)

# 🔍 사용자 질문 입력
user_input = st.text_input("💬 질문을 입력하세요:", key="input_text")

if user_input:
    # 🚨 민감한 질문 필터링
    if is_blocked_question(user_input):
        st.error("🚨 부적절한 질문입니다. 다른 질문을 입력해주세요.")
        save_blocked_question(user_input)  # 차단된 질문 기록
    else:
        # ✅ 데이터가 없을 경우 대비
        if df.empty:
            st.warning("❌ FAQ 데이터가 없습니다.")
        else:
            best_match, score = process.extractOne(user_input, df["질문"].tolist())

            if score > 60:
                answer = df.loc[df["질문"] == best_match, "답변"].values[0]
                
                # 💬 대화창 왼쪽에 답변, 오른쪽에 질문
                st.markdown(f"**챗봇:** {best_match}")
                st.markdown(f"**사용자:** {user_input}")
                st.markdown(f"**챗봇:** {answer}")
                
                # 피드백 버튼
                feedback = ""
                thumbs_up = st.button("👍 도움이 됐어요", key=f"feedback_up_{user_input}_{score}")
                thumbs_down = st.button("👎 부족한 답변이에요", key=f"feedback_down_{user_input}_{score}")
                
                if thumbs_up:
                    feedback = "좋음"
                elif thumbs_down:
                    feedback = "나쁨"
                
                if feedback:
                    save_chat_log_to_google_sheets(user_input, answer, feedback)  # 🚀 Google Sheets에 로그 저장!
                    
                    # 📩 담당자에게 전송 버튼
                    if not thumbs_up and not thumbs_down:
                        send_email(user_input, answer)

                    st.success(f"피드백이 반영되었습니다: {feedback}")

                # 📌 피드백 버튼 
                if st.button("👍 도움이 됐어요", key=f"feedback_up_{user_input}"):
                    st.success("✅ 감사합니다! 피드백이 반영되었습니다.")
                if st.button("👎 부족한 답변이에요", key=f"feedback_down_{user_input}"):
                    st.warning("📩 개선을 위해 피드백을 저장했습니다.")
            else:
                st.warning("❌ 관련된 질문을 찾지 못했어요.")
