import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from gspread_dataframe import set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
import io
import os
from pytz import timezone
import streamlit.components.v1 as components  # ✅ Thêm dòng này

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

# Save locally
def save_to_local_folder(dataframe, username):
    folder_path = r"C:\\Web\\Dữ liệu"
    os.makedirs(folder_path, exist_ok=True)
    filename = f"ket_qua_{username}.xlsx"
    full_path = os.path.join(folder_path, filename)
    dataframe.to_excel(full_path, index=False)
    return full_path

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

    if "user_info_collected" not in st.session_state:
        st.subheader("Thông tin người tham gia")
        full_name = st.text_input("Họ và tên:")
        gender = st.selectbox("Giới tính:", ["Nam", "Nữ", "Khác"])

        age_input = st.text_input("Tuổi (vui lòng nhập số):")
        age = None
        if age_input:
            if age_input.isdigit():
                age = int(age_input)
            else:
                st.warning("⚠️ Tuổi phải là một số nguyên dương.")

        occupation_options = [
            "Sinh viên",
            "Nhân viên văn phòng",
            "Doanh nhân",
            "Lao động tự do",
            "Nghề nghiệp khác (vui lòng ghi rõ):"
        ]
        occupation = st.radio("Nghề nghiệp của bạn là gì?", occupation_options, index=None)

        frequency_options = [
            "6 lần/ tuần",
            "5 lần/ tuần",
            "4 lần/ tuần",
            "3 lần/ tuần",
            "2 lần/tuần",
            "1 lần/ tuần",
            "ít hơn 1 lần/ tuần"
        ]
        frequency = st.radio("Tần suất sử dụng nước tăng lực đóng lon của bạn?", frequency_options, index=None)

        if st.button("Tiếp tục"):
            if not full_name or not occupation or not frequency or age is None:
                st.error("❌ Vui lòng điền đầy đủ tất cả thông tin trước khi tiếp tục.")
            else:
                st.session_state.full_name = full_name
                st.session_state.gender = gender
                st.session_state.age = age
                st.session_state.occupation = occupation
                st.session_state.frequency = frequency
                st.session_state.user_info_collected = True
                st.session_state.show_instruction = True
                st.rerun()

    elif st.session_state.get("show_instruction"):
        st.markdown("""
        <h2 style='text-align: center;'>Hướng dẫn cảm quan</h2>
        <p>Anh/Chị sẽ được nhận các mẫu nước tăng lực được gán mã số, vui lòng đánh giá lần lượt các mẫu từ trái sang phải theo thứ tự đã cung cấp. Anh/Chị vui lòng đánh giá mỗi mẫu theo trình tự sau:</p>
        <ol>
            <li>Dùng thử sản phẩm và đánh giá cường độ các tính chất <b>MÀU SẮC</b>, <b>MÙI</b> và <b>HƯƠNG VỊ</b>.</li>
            <li>Cho biết cường độ của mỗi tính chất mà anh/chị cho là lý tưởng.</li>
            <li>Nếu cường độ tính chất của mẫu phù hợp, chọn lý tưởng = mẫu.</li>
            <li>Cho biết độ ưa thích chung đối với mẫu.</li>
        </ol>
        <p><b style='color:red;'>LƯU Ý:</b></p>
        <ul>
            <li>Thanh vị bằng nước và bánh trước/sau mỗi mẫu.</li>
            <li>Không trao đổi trong quá trình đánh giá.</li>
            <li>Liên hệ thực nghiệm viên nếu cần.</li>
        </ul>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("⬅ Quay lại"):
                st.session_state.show_instruction = False
                st.session_state.user_info_collected = False
                st.rerun()
        with col2:
            if st.button("Bắt đầu"):
                st.session_state.show_instruction = False
                st.rerun()

    else:
        user_row = user_df[user_df.username == st.session_state.user]
        if user_row.empty:
            st.error("⚠️ Không tìm thấy thông tin mẫu cho tài khoản này.")
            st.stop()

        user_order_str = user_row["order"].values[0]
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
                "full_name": st.session_state.full_name,
                "gender": st.session_state.gender,
                "age": st.session_state.age,
                "occupation": st.session_state.occupation,
                "frequency": st.session_state.frequency,
                "timestamp": datetime.now(timezone("Asia/Ho_Chi_Minh")).strftime("%Y-%m-%d %H:%M:%S")
            }

            for attr in ["Màu sắc", "Hương sản phẩm", "Vị ngọt", "Vị chua", "Vị đắng", "Vị chát", "Hậu vị"]:
                with st.container():
                    st.markdown(f"### 🔸 {attr}")
                    col1, col2 = st.columns(2)
                    with col1:
                        rating[f"{attr} - Cường độ mẫu"] = st.slider("Cường độ trong mẫu (1-100)", 1, 100, 50, key=f"{sample}_{attr}_sample")
                    with col2:
                        rating[f"{attr} - Cường độ lý tưởng"] = st.slider("Cường độ lý tưởng (1-100)", 1, 100, 50, key=f"{sample}_{attr}_ideal")
                    st.markdown("<hr style='margin-top: 0.5rem; margin-bottom: 1rem;'>", unsafe_allow_html=True)

            preference = st.radio("Điểm ưa thích chung", options=[
                "1 - Cực kỳ không thích",
                "2 - Rất không thích",
                "3 - Không thích",
                "4 - Tương đối không thích",
                "5 - Không thích cũng không ghét",
                "6 - Tương đối thích",
                "7 - Thích",
                "8 - Rất thích",
                "9 - Cực kỳ thích"
            ], key=f"{sample}_pref", index=None)
            if preference:
                rating["Ưa thích chung"] = int(preference.split(" ")[0])

            if st.button("Tiếp tục", key=f"next_{sample}"):
                if "Ưa thích chung" not in rating:
                    st.error("❌ Vui lòng chọn mức độ ưa thích chung trước khi tiếp tục.")
                else:
                    st.session_state.partial_results.append(rating)
                    st.session_state.current_sample_index += 1

                    # ✅ Tự cuộn lên đầu trang sau khi ấn "Tiếp tục"
                    components.html("""
                        <script>
                            window.scrollTo({ top: 0, behavior: 'smooth' });
                            setTimeout(() => window.parent.postMessage({streamlitScrollToTop:true}, '*'), 100);
                        </script>
                    """, height=0)

                    st.rerun()

        else:
            st.success("✅ Bạn đã hoàn thành tất cả các mẫu!")
            df_results = pd.DataFrame(st.session_state.partial_results)

            local_path = save_to_local_folder(df_results, st.session_state.user)
            st.info(f"📁 Kết quả đã lưu tại: {local_path}")

            try:
                sheet_id = "13XRlhwoQY-ErLy75l8B0fOv-KyIoO6p_VlzkoUnfUl0"
                append_to_google_sheet(df_results, sheet_id)
                st.success("✅ Đã lưu kết quả vào Google Sheet!")
            except Exception as e:
                st.error(f"❌ Lỗi khi ghi vào Google Sheet: {e}")

            towrite = io.BytesIO()
            df_results.to_excel(towrite, index=False, engine='openpyxl')
            towrite.seek(0)
            st.download_button(
                label="📥 Tải kết quả về máy",
                data=towrite,
                file_name=f"ket_qua_{st.session_state.user}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
