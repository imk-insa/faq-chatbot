import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from fuzzywuzzy import process
import json
import smtplib
from email.mime.text import MIMEText

# ✅ Google Sheets API 연결
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Streamlit Secrets에서 credentials.json 가져오기
google_credentials = st.secrets["google"]["credentials"]
creds_dict = json.loads(google_credentials)
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

# ✅ Google Sheets 스프레드시트 열기 (한 개의 스프레드시트에서 모든 시트 관리)
spreadsheet = client.open("FAQ_Chatbot_DB")
faq_sheet = spreadsheet.worksheet("FAQ_DB")
log_sheet = spreadsheet.worksheet("FAQ_Logs")
blocked_sheet = spreadsheet.worksheet("Blocked_Questions")

@st.cache_data
def load_faq_data():
    """Google Sheets에서 FAQ 데이터를 불러와 DataFrame으로 변환"""
    try:
        faq_data = faq_sheet.get_all_values()
        if len(faq_data) > 1:
            return pd.DataFrame(faq_data[1:], columns=faq_data[0])
        else:
            return pd.DataFrame(columns=["질문", "답변"])
    except Exception as e:
        st.error(f"❌ Google Sheets 데이터 로드 오류: {e}")
        return pd.DataFrame(columns=["질문", "답변"])

df = load_faq_data()

# ✅ 로그 저장 함수
def save_chat_log_to_google_sheets(question, answer, feedback=""):
    try:
        log_sheet.append_row([question, answer, feedback])
    except Exception as e:
        st.error(f"❌ 로그 저장 오류: {e}")

# ✅ 금지어 목록
blocked_keywords = ["비속어1", "비속어2", "폭력", "혐오", "불법"]

# ✅ 금지된 질문인지 확인하는 함수
def is_blocked_question(user_input):
    return any(word in user_input.lower() for word in blocked_keywords)

# ✅ 차단된 질문을 Google Sheets에 저장하는 함수
def save_blocked_question(user_input):
    try:
        blocked_sheet.append_row([user_input, "차단된 질문"])
    except Exception as e:
        st.error(f"❌ 차단된 질문 저장 오류: {e}")

# ✅ 네이버 SMTP 이메일 발송 설정
SMTP_SERVER = "smtp.naver.com"
SMTP_PORT = 587  # TLS 필요
NAVER_ID = "dulos_kratai"
NAVER_PW = st.secrets["naver"]["password"]  # Streamlit secrets에서 비밀번호 가져오기

def send_email(to_email, subject, message):
    """ 네이버 SMTP를 이용한 이메일 발송 함수 """
    try:
        msg = MIMEText(message, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = f"{NAVER_ID}@naver.com"
        msg["To"] = to_email

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()  # TLS 보안 연결
        server.login(NAVER_ID, NAVER_PW)
        server.sendmail(msg["From"], msg["To"], msg.as_string())
        server.quit()
        st.success("📩 이메일이 성공적으로 발송되었습니다!")
    except Exception as e:
        st.error(f"❌ 이메일 발송 중 오류 발생: {e}")

# ✅ 챗봇 UI (대화형)
st.markdown("<h1 style='text-align: center; color: blue;'>FAQ 챗봇</h1>", unsafe_allow_html=True)

chat_history = st.session_state.get("chat_history", [])

# 🔍 사용자 질문 입력
user_input = st.text_input("💬 질문을 입력하세요:", "")

if user_input:
    # 🚨 금지된 질문 필터링
    if is_blocked_question(user_input):
        st.error("🚨 부적절한 질문입니다. 다른 질문을 입력해주세요.")
        save_blocked_question(user_input)
    else:
        if df.empty:
            st.warning("❌ FAQ 데이터가 없습니다.")
        else:
            best_match, score = process.extractOne(user_input, df["질문"].tolist())

            if score > 60:
                answer = df.loc[df["질문"] == best_match, "답변"].values[0]
                chat_history.append(("사용자", user_input))
                chat_history.append(("챗봇", answer))
                st.session_state.chat_history = chat_history
                save_chat_log_to_google_sheets(user_input, answer)

            else:
                chat_history.append(("사용자", user_input))
                chat_history.append(("챗봇", "❌ 관련된 질문을 찾지 못했어요."))
                st.session_state.chat_history = chat_history

# ✅ 대화 내역 표시 (최신 메시지가 아래로 가도록)
for speaker, message in chat_history:
    if speaker == "사용자":
        st.markdown(f"<div style='text-align: right; background-color: #d9f7be; padding: 10px; border-radius: 10px; margin: 5px;'>**{speaker}:** {message}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='text-align: left; background-color: #f5f5f5; padding: 10px; border-radius: 10px; margin: 5px;'>**{speaker}:** {message}</div>", unsafe_allow_html=True)

# ✅ 피드백 버튼 (좋아요/싫어요)
if chat_history:
    last_question = chat_history[-2][1]
    last_answer = chat_history[-1][1]

    col1, col2 = st.columns(2)

    with col1:
        if st.button("👍 도움이 됐어요", key=f"feedback_up_{last_question}"):
            save_chat_log_to_google_sheets(last_question, last_answer, "좋음")
            st.success("✅ 감사합니다! 피드백이 반영되었습니다.")

    with col2:
        if st.button("👎 부족한 답변이에요", key=f"feedback_down_{last_question}"):
            save_chat_log_to_google_sheets(last_question, last_answer, "나쁨")
            st.warning("📩 개선을 위해 피드백을 저장했습니다.")

# ✅ 담당자 문의 버튼
if chat_history:
    if st.button("📧 담당자에게 문의"):
        last_question = chat_history[-2][1]
        send_email(
            "junh.park@imarketkorea.com",
            "FAQ 챗봇 문의 접수",
            f"사용자가 '{last_question}' 에 대한 답변을 찾지 못하고 담당자 문의를 요청했습니다."
        )
