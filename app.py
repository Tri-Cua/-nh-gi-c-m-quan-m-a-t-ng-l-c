import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from gspread_dataframe import set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
import io

# Load user info and sample order
@st.cache_data
def load_user_data():
    df = pd.read_excel("Thứ tự câu hỏi Mía tăng lực.xlsx")
    df.columns = ["username", "password", "order"]
    return df

# Append results to Google Sheet
def append_to_google_sheet(dataframe, sheet_id):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.get_worksheet(0)
    existing = pd.DataFrame(worksheet.get_all_records())
    updated = pd.concat([existing, dataframe], ignore_index=True)
    worksheet.clear()
    set_with_dataframe(worksheet, updated)

# Main app
user_df = load_user_data()
st.set_page_config(page_title="Đánh giá cảm quan sản phẩm")
st.title("🔍 Đánh giá cảm quan sản phẩm")

# Session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None

# Login
if not st.session_state.logged_in:
    st.subheader("Đăng nhập")
    username = st.text_input("Tên đăng nhập")
    password = st.text_input("Mật khẩu", type="password")
    if st.button("Đăng nhập"):
        user_match = user_df[(user_df.username == username) & (user_df.password == password)]
        if not user_match.empty:
            st.session_state.logged_in = True
            st.session_state.user = username
            st.success("Đăng nhập thành công!")
            st.rerun()
        else:
            st.error("Sai tên đăng nhập hoặc mật khẩu.")

else:
    st.success(f"Chào mừng {st.session_state.user}!")

    # Lấy thứ tự mẫu
    user_order_str = user_df[user_df.username == st.session_state.user]["order"].values[0]
    sample_codes = [code.strip() for code in user_order_str.split("–")]

    if "current_sample_index" not in st.session_state:
        st.session_state.current_sample_index = 0
        st.session_state.partial_results = []

    if st.session_state.current_sample_index < len(sample_codes):
        sample = sample_codes[st.session_state.current_sample_index]
        st.subheader(f"Đánh giá mẫu: {sample}")
        rating = {
            "sample": sample,
            "username": st.session_state.user,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        for attr in ["Màu sắc", "Hương sản phẩm", "Vị ngọt", "Vị chua", "Vị đắng", "Vị chát", "Hậu vị"]:
            rating[attr] = st.slider(f"{attr} (1-100)", 1, 100, 50, key=f"{sample}_{attr}")

        preference = st.radio("Ưa thích chung", options=[
            "1 - Cực kỳ không thích",
            "2", "3", "4",
            "5 - Không thích cũng không ghét",
            "6", "7", "8",
            "9 - Cực kỳ thích"
        ], key=f"{sample}_pref")
        rating["Ưa thích chung"] = int(preference.split(" ")[0])

        if st.button("Tiếp tục"):
            st.session_state.partial_results.append(rating)
            st.session_state.current_sample_index += 1
            st.rerun()
    else:
        st.success("✅ Bạn đã hoàn thành tất cả các mẫu!")
        df_results = pd.DataFrame(st.session_state.partial_results)
        output_file = f"ket_qua_{st.session_state.user}.xlsx"
        df_results.to_excel(output_file, index=False)

        # Ghi vào Google Sheet
        try:
            sheet_id = "13XRlhwoQY-ErLy75l8B0fOv-KyIoO6p_VlzkoUnfUl0"
            append_to_google_sheet(df_results, sheet_id)
            st.success("✅ Đã lưu kết quả vào Google Sheet!")
        except Exception as e:
            st.error(f"❌ Lỗi khi ghi vào Google Sheet: {e}")

        # Cho phép tải file Excel nếu cần
        towrite = io.BytesIO()
        df_results.to_excel(towrite, index=False, engine='openpyxl')
        towrite.seek(0)
        st.download_button(
            label="📥 Tải kết quả về máy",
            data=towrite,
            file_name=output_file,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

