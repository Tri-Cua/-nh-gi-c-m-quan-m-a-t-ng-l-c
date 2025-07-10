import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from gspread_dataframe import set_with_dataframe
import io
import os
from pytz import timezone
import streamlit.components.v1 as components
import json

# --- CONFIGURATION & SETUP ---

st.set_page_config(
    page_title="Đánh giá cảm quan sản phẩm",
    page_icon="🧪",
    layout="centered"
)

# --- GOOGLE SHEETS CONNECTION (IMPROVED & SECURE) ---

# Function to connect to Google Sheets using Streamlit Secrets
def connect_to_google_sheets():
    """
    Connects to Google Sheets using service account credentials
    stored in Streamlit's secrets management.
    """
    try:
        # Load credentials from st.secrets
        # In your local .streamlit/secrets.toml file, this would look like:
        # [gcp_service_account]
        # type = "service_account"
        # project_id = "your-project-id"
        # ... (copy all key-value pairs from your JSON file)
        creds_json = st.secrets["gcp_service_account"]
        sa = gspread.service_account_from_dict(creds_json)
        client = sa
        return client
    except Exception as e:
        st.error(f"Lỗi kết nối với Google Sheets: Không thể tìm thấy thông tin xác thực trong st.secrets. Vui lòng kiểm tra lại. Lỗi: {e}")
        return None

def append_to_google_sheet(dataframe, sheet_id, client):
    """
    Appends a DataFrame to a specified Google Sheet without overwriting existing data.
    This is much more efficient than reading/clearing/writing.
    """
    if client is None:
        st.error("Không thể ghi vào Google Sheet do kết nối không thành công.")
        return

    try:
        sheet = client.open_by_key(sheet_id)
        worksheet = sheet.get_worksheet(0)

        # Get existing headers from the first row of the sheet
        existing_headers = worksheet.row_values(1)
        
        # If the sheet is empty (no headers), write the dataframe with headers
        if not existing_headers:
             set_with_dataframe(worksheet, dataframe)
             return

        # Ensure the dataframe columns are in the same order as the sheet headers
        # and filter out columns that are not in the sheet
        ordered_df = dataframe[existing_headers]
        values_to_append = ordered_df.values.tolist()

        # Append new rows to the sheet
        worksheet.append_rows(values_to_append, value_input_option='USER_ENTERED')

    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Lỗi: Không tìm thấy Google Sheet với ID: {sheet_id}")
    except Exception as e:
        st.error(f"❌ Lỗi khi ghi vào Google Sheet: {e}")


# --- DATA LOADING ---

@st.cache_data
def load_user_data():
    """
    Loads user login data from an Excel file.
    NOTE: For a real application, consider a more secure way to store user data.
    """
    try:
        df = pd.read_excel("Thứ tự câu hỏi Mía tăng lực.xlsx")
        df.columns = ["username", "password", "order"]
        # Ensure password is treated as a string for robust comparison
        df['password'] = df['password'].astype(str)
        return df
    except FileNotFoundError:
        st.error("Lỗi: Không tìm thấy file 'Thứ tự câu hỏi Mía tăng lực.xlsx'. Vui lòng đảm bảo file này tồn tại trong cùng thư mục với ứng dụng.")
        return pd.DataFrame(columns=["username", "password", "order"])


# --- MAIN APP LOGIC ---

def main():
    st.title("🔍 Đánh giá cảm quan sản phẩm")

    # Load user data
    user_df = load_user_data()

    # --- SESSION STATE INITIALIZATION ---
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user" not in st.session_state:
        st.session_state.user = None
    if "current_view" not in st.session_state:
        st.session_state.current_view = "login" # Manages app flow: 'login', 'user_info', 'instructions', 'evaluation', 'thank_you'
    if "partial_results" not in st.session_state:
        st.session_state.partial_results = []
    if "current_sample_index" not in st.session_state:
        st.session_state.current_sample_index = 0

    # --- VIEW: LOGIN ---
    if st.session_state.current_view == "login":
        st.subheader("Đăng nhập")
        with st.form("login_form"):
            username = st.text_input("Tên đăng nhập")
            password = st.text_input("Mật khẩu", type="password")
            submitted = st.form_submit_button("Đăng nhập")

            if submitted:
                # Ensure password from input is also treated as string
                password_str = str(password)
                user_match = user_df[(user_df.username == username) & (user_df.password == password_str)]
                if not user_match.empty:
                    st.session_state.logged_in = True
                    st.session_state.user = username
                    st.session_state.current_view = "user_info"
                    st.success("Đăng nhập thành công!")
                    st.rerun()
                else:
                    st.error("Sai tên đăng nhập hoặc mật khẩu.")

    # --- VIEW: USER INFO ---
    elif st.session_state.current_view == "user_info":
        st.subheader(f"Thông tin người tham gia (Chào {st.session_state.user})")
        with st.form("user_info_form"):
            full_name = st.text_input("Họ và tên:")
            gender = st.selectbox("Giới tính:", ["Nam", "Nữ", "Khác"])
            age_input = st.text_input("Tuổi (vui lòng nhập số):")
            
            occupation_options = [
                "Sinh viên", "Nhân viên văn phòng", "Doanh nhân",
                "Lao động tự do", "Nghề nghiệp khác"
            ]
            occupation = st.radio("Nghề nghiệp của bạn là gì?", occupation_options, index=None)
            
            frequency_options = [
                "6 lần/ tuần", "5 lần/ tuần", "4 lần/ tuần", "3 lần/ tuần",
                "2 lần/tuần", "1 lần/ tuần", "ít hơn 1 lần/ tuần"
            ]
            frequency = st.radio("Tần suất sử dụng nước tăng lực đóng lon của bạn?", frequency_options, index=None)

            submitted = st.form_submit_button("Tiếp tục")
            if submitted:
                age = None
                if age_input.isdigit() and int(age_input) > 0:
                    age = int(age_input)
                else:
                    st.warning("⚠️ Tuổi phải là một số nguyên dương.")

                if not all([full_name, occupation, frequency, age is not None]):
                    st.error("❌ Vui lòng điền đầy đủ tất cả thông tin trước khi tiếp tục.")
                else:
                    st.session_state.user_info = {
                        "full_name": full_name,
                        "gender": gender,
                        "age": age,
                        "occupation": occupation,
                        "frequency": frequency
                    }
                    st.session_state.current_view = "instructions"
                    st.rerun()

    # --- VIEW: INSTRUCTIONS ---
    elif st.session_state.current_view == "instructions":
        st.markdown("""
        <h2 style='text-align: center;'>Hướng dẫn cảm quan</h2>
        <p>Anh/Chị sẽ được nhận các mẫu nước tăng lực được gán mã số, vui lòng đánh giá lần lượt các mẫu từ trái sang phải theo thứ tự đã cung cấp. Anh/Chị vui lòng đánh giá mỗi mẫu theo trình tự sau:</p>
        <ol>
            <li>Dùng thử sản phẩm và đánh giá cường độ các tính chất <b>MÀU SẮC</b>, <b>MÙI</b> và <b>HƯƠNG VỊ</b>.</li>
            <li>Cho biết cường độ của mỗi tính chất mà anh/chị cho là lý tưởng.</li>
            <li>Nếu cường độ tính chất của mẫu phù hợp, chọn "lý tưởng = mẫu".</li>
            <li>Cho biết độ ưa thích chung đối với mẫu.</li>
        </ol>
        <p><b style='color:red;'>LƯU Ý:</b></p>
        <ul>
            <li>Thanh vị bằng nước và bánh trước/sau mỗi mẫu.</li>
            <li>Không trao đổi trong quá trình đánh giá.</li>
            <li>Liên hệ thực nghiệm viên nếu cần.</li>
        </ul>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col2:
            if st.button("Bắt đầu đánh giá", use_container_width=True, type="primary"):
                st.session_state.current_view = "evaluation"
                st.rerun()

    # --- VIEW: EVALUATION ---
    elif st.session_state.current_view == "evaluation":
        # Auto-scroll to top whenever this view is loaded.
        # We include the sample index in a comment to ensure the HTML is unique for each sample,
        # forcing the component to re-render and the script to re-execute.
        components.html(
            f"""
            <!-- Rerun counter: {st.session_state.current_sample_index} -->
            <script>
                window.parent.scrollTo({{ top: 0, behavior: 'smooth' }});
            </script>
            """,
            height=0,
        )

        user_row = user_df[user_df.username == st.session_state.user]
        if user_row.empty:
            st.error("⚠️ Không tìm thấy thông tin mẫu cho tài khoản này.")
            st.stop()
        
        # Standardize hyphen character to avoid errors
        user_order_str = user_row["order"].values[0].replace("–", "-")
        sample_codes = [code.strip() for code in user_order_str.split("-")]

        idx = st.session_state.current_sample_index
        if idx < len(sample_codes):
            sample = sample_codes[idx]
            st.subheader(f"Đánh giá mẫu: {sample} ({idx + 1}/{len(sample_codes)})")

            with st.form(key=f"form_{sample}"):
                rating = {}
                attributes = ["Màu sắc", "Hương sản phẩm", "Vị ngọt", "Vị chua", "Vị đắng", "Vị chát", "Hậu vị"]
                
                for attr in attributes:
                    st.markdown(f"<h5>🔸 {attr}</h5>", unsafe_allow_html=True)
                    col1, col2 = st.columns(2)
                    with col1:
                        rating[f"{attr} - Cường độ mẫu"] = st.slider("Cường độ trong mẫu", 1, 100, 50, key=f"{sample}_{attr}_sample")
                    with col2:
                        rating[f"{attr} - Cường độ lý tưởng"] = st.slider("Cường độ lý tưởng", 1, 100, 50, key=f"{sample}_{attr}_ideal")
                    st.markdown("<hr style='margin: 0.5rem 0;'>", unsafe_allow_html=True)
                
                preference = st.radio(
                    "Điểm ưa thích chung",
                    options=[
                        "1 - Cực kỳ không thích",
                        "2 - Rất không thích",
                        "3 - Không thích",
                        "4 - Tương đối không thích",
                        "5 - Không thích cũng không ghét",
                        "6 - Tương đối thích",
                        "7 - Thích",
                        "8 - Rất thích",
                        "9 - Cực kỳ thích"
                    ],
                    key=f"{sample}_pref", index=None
                )

                submitted = st.form_submit_button("Tiếp tục")
                if submitted:
                    if not preference:
                        st.error("❌ Vui lòng chọn mức độ ưa thích chung trước khi tiếp tục.")
                    else:
                        # Add all data to the record
                        full_record = {
                            "username": st.session_state.user,
                            "sample": sample,
                            **st.session_state.user_info,
                            "timestamp": datetime.now(timezone("Asia/Ho_Chi_Minh")).strftime("%Y-%m-%d %H:%M:%S"),
                            **rating,
                            "Ưa thích chung": int(preference.split(" ")[0])
                        }
                        st.session_state.partial_results.append(full_record)
                        st.session_state.current_sample_index += 1
                        st.rerun()
        else:
            # All samples are done, move to thank you page
            st.session_state.current_view = "thank_you"
            st.rerun()

    # --- VIEW: THANK YOU & SUBMIT ---
    elif st.session_state.current_view == "thank_you":
        st.success("✅ Bạn đã hoàn thành tất cả các mẫu!")
        st.balloons()
        
        df_results = pd.DataFrame(st.session_state.partial_results)

        st.subheader("Bảng kết quả của bạn")
        st.dataframe(df_results)
        
        # Connect to Google Sheets and append data
        gspread_client = connect_to_google_sheets()
        if gspread_client:
            # IMPORTANT: Replace with your actual Google Sheet ID
            sheet_id = "13XRlhwoQY-ErLy75l8B0fOv-KyIoO6p_VlzkoUnfUl0"
            st.info("Đang lưu kết quả vào Google Sheet...")
            append_to_google_sheet(df_results, sheet_id, gspread_client)
            st.success("✅ Đã lưu kết quả vào Google Sheet thành công!")

        # Provide a download button
        towrite = io.BytesIO()
        df_results.to_excel(towrite, index=False, engine='openpyxl')
        towrite.seek(0)
        st.download_button(
            label="📥 Tải kết quả về máy",
            data=towrite,
            file_name=f"ket_qua_{st.session_state.user}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.info("Cảm ơn bạn đã tham gia! Vui lòng đóng cửa sổ này.")


if __name__ == "__main__":
    main()
