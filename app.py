import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from fuzzywuzzy import process

# ✅ Google Sheets API 연결
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(r"C:\Users\dulos\Documents\faq-chatbot\credentials.json", scopes=scope)
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
def save_chat_log_to_google_sheets(question, answer):
    try:
        log_sheet.append_row([question, answer])
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

# 🎨 제목
st.markdown("<h1 style='text-align: center; color: blue;'>FAQ 챗봇</h1>", unsafe_allow_html=True)

# 🔍 사용자 질문 입력
user_input = st.text_input("💬 질문을 입력하세요:", "")

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
                st.success(f"📌 **{best_match}**")
                st.write(f"🤖 {answer}")
                save_chat_log_to_google_sheets(user_input, answer)  # 🚀 Google Sheets에 로그 저장!

                # 📌 피드백 버튼
                if st.button("👍 도움이 됐어요"):
                    st.success("✅ 감사합니다! 피드백이 반영되었습니다.")

                if st.button("👎 부족한 답변이에요"):
                    st.warning("📩 개선을 위해 피드백을 저장했습니다.")
            else:
                st.warning("❌ 관련된 질문을 찾지 못했어요.")
