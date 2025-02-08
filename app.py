import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from fuzzywuzzy import process
import json
import base64
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
blocked_keywords = ["비속어1", "비속어2", "폭력", "혐오", "불법"]

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
    sender_email = "your_email@gmail.com"  # 발신자 이메일
    receiver_email = "junh.park@imarketkorea.com"  # 수신자 이메일 (담당자 이메일)
    password = "your_email_password"  # 발신자 이메일 비밀번호

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
        st.success("✅ 질문이 담당자에게 전송되었습니다.")
    except Exception as e:
        st.error(f"❌ 이메일 전송 오류: {e}")

# 🎨 제목
st.markdown("<h1 style='text-align: center; color: blue;'>FAQ 챗봇</h1>", unsafe_allow_html=True)

# 🔍 사용자 질문 입력
user_input = st.text_input("💬 질문을 입력하세요:", "")

if "messages" not in st.session_state:
    st.session_state.messages = []  # 메시지 초기화

# 사용자 질문이 있을 경우 처리
if user_input:
    # 🚨 민감한 질문 필터링
    if is_blocked_question(user_input):
        st.session_state.messages.append({"role": "user", "text": user_input})
        st.session_state.messages.append({"role": "bot", "text": "🚨 부적절한 질문입니다. 다른 질문을 입력해주세요."})
        save_blocked_question(user_input)  # 차단된 질문 기록
        user_input = ""  # 질문 초기화
    else:
        # ✅ 데이터가 없을 경우 대비
        if df.empty:
            st.session_state.messages.append({"role": "user", "text": user_input})
            st.session_state.messages.append({"role": "bot", "text": "❌ FAQ 데이터가 없습니다."})
            user_input = ""  # 질문 초기화
        else:
            best_match, score = process.extractOne(user_input, df["질문"].tolist())
            if score > 60:
                answer = df.loc[df["질문"] == best_match, "답변"].values[0]
                st.session_state.messages.append({"role": "user", "text": user_input})
                st.session_state.messages.append({"role": "bot", "text": f"📌 **{best_match}**\n🤖 {answer}"})
                save_chat_log_to_google_sheets(user_input, answer, "피드백 대기")  # 🚀 Google Sheets에 로그 저장!

                # 📌 피드백 버튼
                if st.button("👍 도움이 됐어요"):
                    st.session_state.messages.append({"role": "bot", "text": "✅ 감사합니다! 피드백이 반영되었습니다."})
                    save_chat_log_to_google_sheets(user_input, answer, "반영됨")  # 피드백 기록
                    user_input = ""  # 질문 초기화

                if st.button("👎 부족한 답변이에요"):
                    st.session_state.messages.append({"role": "bot", "text": "📩 개선을 위해 피드백을 저장했습니다."})
                    save_chat_log_to_google_sheets(user_input, answer, "반영되지 않음")  # 피드백 기록
                    user_input = ""  # 질문 초기화

                # 📧 이메일 전송 버튼
                if st.button("담당자에게 문의"):
                    send_email(user_input, answer)
                    user_input = ""  # 질문 초기화
            else:
                st.session_state.messages.append({"role": "user", "text": user_input})
                st.session_state.messages.append({"role": "bot", "text": "❌ 관련된 질문을 찾지 못했어요."})
                user_input = ""  # 질문 초기화

# 대화 내용 표시
for message in reversed(st.session_state.messages):
    if message["role"] == "user":
        st.markdown(f"<div style='text-align: right; background-color: lightgray; padding: 10px; border-radius: 10px; margin: 5px; width: fit-content;'>**사용자:** {message['text']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='background-color: #f0f0f0; padding: 10px; border-radius: 10px; margin: 5px; width: fit-content;'>**챗봇:** {message['text']}</div>", unsafe_allow_html=True)
