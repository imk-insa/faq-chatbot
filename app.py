import streamlit as st
import pandas as pd
import gspread
import base64
import json
from google.oauth2.service_account import Credentials
from fuzzywuzzy import process

# ✅ Streamlit에서 secrets 가져오기
google_credentials = st.secrets["google"]["credentials"]

# base64로 인코딩된 credentials을 복호화
decoded_credentials = base64.b64decode(google_credentials)

# JSON으로 변환
creds_dict = json.loads(decoded_credentials)

# 구글 스프레드시트 API 인증
creds = Credentials.from_service_account_info(creds_dict, scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
client = gspread.authorize(creds)

# 스프레드시트 열기
spreadsheet = client.open("FAQ_Chatbot_DB")  # 스프레드시트 이름 수정 필요
worksheet = spreadsheet.sheet1  # 첫 번째 시트 선택

# 예시: 시트에서 데이터 가져오기
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# Streamlit 앱 내용
st.title("FAQ 챗봇")
st.write(df)
