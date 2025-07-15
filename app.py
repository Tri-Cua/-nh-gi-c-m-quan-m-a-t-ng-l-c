import dash
from dash import dcc, html, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
import pandas as pd
from datetime import datetime
import gspread
from gspread_dataframe import set_with_dataframe
import io
import os
from pytz import timezone
import base64

# --- INITIALIZE THE DASH APP ---
# Using a Bootstrap theme for a clean look
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server # Expose server for deployment

# --- DATA LOADING ---
# This function is the same as before, but without the Streamlit cache decorator
def load_user_data():
    """
    Loads user login data from an Excel file.
    """
    try:
        df = pd.read_excel("Thứ tự câu hỏi Mía tăng lực.xlsx")
        df.columns = ["username", "password", "order"]
        df['password'] = df['password'].astype(str)
        return df
    except FileNotFoundError:
        # In a Dash app, we handle the error directly in the layout
        return None

# --- GOOGLE SHEETS CONNECTION ---
def connect_to_google_sheets():
    """
    Connects to Google Sheets using a local credentials.json file.
    NOTE: For production, use environment variables instead of a file.
    """
    try:
        # For this version, we read a local file named 'credentials.json'
        # This file should be in the same directory as your app.py
        client = gspread.service_account(filename="credentials.json")
        return client
    except Exception as e:
        print(f"Lỗi kết nối Google Sheets: {e}")
        return None

def append_to_google_sheet(dataframe, sheet_id, client):
    """
    Appends a DataFrame to a specified Google Sheet.
    """
    if client is None: return
    try:
        sheet = client.open_by_key(sheet_id)
        worksheet = sheet.get_worksheet(0)
        existing_headers = worksheet.row_values(1)
        
        if not existing_headers:
            set_with_dataframe(worksheet, dataframe)
            return

        new_headers = [h for h in dataframe.columns if h not in existing_headers]
        if new_headers:
            last_col = len(existing_headers)
            worksheet.update(range_name=gspread.utils.rowcol_to_a1(1, last_col + 1), values=[new_headers])
            existing_headers.extend(new_headers)

        for header in existing_headers:
            if header not in dataframe.columns:
                dataframe[header] = None

        ordered_df = dataframe[existing_headers]
        values_to_append = ordered_df.values.tolist()
        worksheet.append_rows(values_to_append, value_input_option='USER_ENTERED')
        print("Đã lưu kết quả vào Google Sheet thành công!")
    except Exception as e:
        print(f"Lỗi khi ghi vào Google Sheet: {e}")

# --- APP LAYOUT ---
# The layout is the structure of your web page.
# We use dcc.Store to keep track of the app's state between callbacks (like st.session_state)
app.layout = dbc.Container([
    # Hidden stores to hold session data
    dcc.Store(id='session-store', storage_type='session'), # Stores user, view, etc.
    dcc.Store(id='results-store', storage_type='session'), # Stores evaluation results

    # Div to act as a trigger for scrolling
    html.Div(id='scroll-trigger', style={'display': 'none'}),

    # Main content area
    html.Div([
        html.H1("🔍 Đánh giá cảm quan sản phẩm", className="text-center my-4"),
        html.Div(id='page-content') # The content will change based on the current view
    ])
], fluid=True)


# --- CALLBACKS TO MANAGE VIEWS AND LOGIC ---
# Callbacks are functions that are automatically called by Dash whenever a
# component's property changes, like a button being clicked.

@callback(
    Output('page-content', 'children'),
    Output('session-store', 'data'),
    Output('scroll-trigger', 'children'),
    Input('session-store', 'data'),
)
def render_page_content(session_data):
    """
    This is the main "router" of the app. It decides which view to show
    based on the 'current_view' value in the session data.
    """
    # Initialize session data if it's empty
    if not session_data:
        session_data = {
            'current_view': 'login',
            'user': None,
            'user_info': None,
            'sample_index': 0
        }

    view = session_data.get('current_view')
    user_df = load_user_data()

    if user_df is None:
        return dbc.Alert("Lỗi: Không tìm thấy file 'Thứ tự câu hỏi Mía tăng lực.xlsx'. Vui lòng đảm bảo file này tồn tại trong cùng thư mục với ứng dụng.", color="danger"), no_update, no_update

    # --- RENDER LOGIN VIEW ---
    if view == 'login':
        login_layout = dbc.Row(dbc.Col(dbc.Card([
            dbc.CardHeader("Đăng nhập"),
            dbc.CardBody([
                dbc.Input(id='login-username', placeholder='Tên đăng nhập', type='text', className="mb-3"),
                dbc.Input(id='login-password', placeholder='Mật khẩu', type='password', className="mb-3"),
                dbc.Button("Đăng nhập", id='login-button', color='primary', n_clicks=0, className="w-100"),
                html.Div(id='login-error', className="mt-3")
            ])
        ]), width=12, md=6, lg=4), justify="center")
        return login_layout, session_data, no_update

    # --- RENDER USER INFO VIEW ---
    elif view == 'user_info':
        info_layout = dbc.Card([
            dbc.CardHeader(f"Thông tin người tham gia (Chào {session_data.get('user')})"),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col(dbc.Input(id='info-name', placeholder='Họ và tên', className="mb-3"), width=12),
                    dbc.Col(dbc.Select(id='info-gender', options=["Nam", "Nữ", "Khác"], placeholder="Giới tính", className="mb-3"), width=6),
                    dbc.Col(dbc.Input(id='info-age', placeholder='Tuổi', type='number', min=1, step=1, className="mb-3"), width=6),
                ]),
                html.P("Nghề nghiệp của bạn là gì?"),
                dbc.RadioItems(id='info-occupation', options=["Sinh viên", "Nhân viên văn phòng", "Doanh nhân", "Lao động tự do", "Nghề nghiệp khác"], inline=True, className="mb-3"),
                html.P("Tần suất sử dụng nước tăng lực đóng lon của bạn?"),
                dbc.RadioItems(id='info-frequency', options=["6 lần/ tuần", "5 lần/ tuần", "4 lần/ tuần", "3 lần/ tuần", "2 lần/tuần", "1 lần/ tuần", "ít hơn 1 lần/ tuần"], inline=True, className="mb-3"),
                dbc.Button("Tiếp tục", id='info-button', color='primary', n_clicks=0, className="w-100"),
                html.Div(id='info-error', className="mt-3")
            ])
        ])
        return info_layout, session_data, datetime.now().isoformat() # Trigger scroll

    # --- RENDER INSTRUCTIONS VIEW ---
    elif view == 'instructions':
        instructions_layout = dbc.Card([
            dbc.CardHeader("Hướng dẫn cảm quan"),
            dbc.CardBody([
                html.P("Anh/Chị sẽ được nhận các mẫu nước tăng lực được gán mã số, vui lòng đánh giá lần lượt các mẫu từ trái sang phải theo thứ tự đã cung cấp. Anh/Chị vui lòng đánh giá mỗi mẫu theo trình tự sau:"),
                html.Ol([
                    html.Li("Dùng thử sản phẩm và đánh giá cường độ các tính chất MÀU SẮC, MÙI và HƯƠNG VỊ."),
                    html.Li("Cho biết cường độ của mỗi tính chất mà anh/chị cho là lý tưởng (cường độ mà anh/chị mong muốn cho sản phẩm nước tăng lực này)."),
                    html.Li("Nếu cường độ tính chất của mẫu phù hợp với mong muốn của anh/chị, vui lòng chọn cường độ lý tưởng bằng với cường độ tính chất của mẫu."),
                    html.Li("Cho biết độ ưa thích chung đối với mẫu sản phẩm này."),
                ]),
                html.P(html.B("LƯU Ý:", style={'color': 'red'})),
                html.Ul([
                    html.Li("Anh/chị lưu ý sử dụng nước và bánh để thanh vị trước và sau mỗi mẫu thử."),
                    html.Li("Anh/chị vui lòng không trao đổi trong quá trình đánh giá mẫu."),
                    html.Li("Anh/chị vui lòng liên hệ với thực nghiệm viên nếu có bất kì thắc mắc nào trong quá trình đánh giá."),
                ]),
                dbc.Button("Bắt đầu đánh giá", id='start-eval-button', color='primary', n_clicks=0, className="mt-3 w-100"),
            ])
        ])
        return instructions_layout, session_data, datetime.now().isoformat() # Trigger scroll

    # --- RENDER EVALUATION VIEW ---
    elif view == 'evaluation':
        user_row = user_df[user_df.username == session_data['user']]
        user_order_str = user_row["order"].values[0].replace("–", "-")
        sample_codes = [code.strip() for code in user_order_str.split("-")]
        idx = session_data['sample_index']

        # This view should only render if there are samples left to evaluate.
        # The logic to switch to the 'ranking' view is now in the handle_evaluation callback.
        sample = sample_codes[idx]
        attributes = ["Màu sắc", "Hương sản phẩm", "Vị ngọt", "Vị chua", "Vị đắng", "Vị chát", "Hậu vị"]
        
        eval_form = [html.H4(f"Đánh giá mẫu: {sample} ({idx + 1}/{len(sample_codes)})")]
        for attr in attributes:
            eval_form.extend([
                html.H5(f"🔸 {attr}", className="mt-4"),
                dbc.Row([
                    dbc.Col([html.Label("Cường độ trong mẫu"), dcc.Slider(1, 100, 1, value=50, id={'type': 'slider-sample', 'index': attr}, marks=None, tooltip={"placement": "bottom", "always_visible": True})]),
                    dbc.Col([html.Label("Cường độ lý tưởng"), dcc.Slider(1, 100, 1, value=50, id={'type': 'slider-ideal', 'index': attr}, marks=None, tooltip={"placement": "bottom", "always_visible": True})]),
                ]),
                html.Hr()
            ])
        
        preference_options = [
            "1 - Cực kỳ không thích", "2 - Rất không thích", "3 - Không thích",
            "4 - Tương đối không thích", "5 - Không thích cũng không ghét", "6 - Tương đối thích",
            "7 - Thích", "8 - Rất thích", "9 - Cực kỳ thích"
        ]
        eval_form.append(html.Div([
            html.P("Điểm ưa thích chung"),
            dbc.RadioItems(id='eval-preference', options=preference_options, className="mb-3")
        ]))
        eval_form.append(dbc.Button("Tiếp tục", id='eval-button', color='primary', n_clicks=0, className="w-100"))
        eval_form.append(html.Div(id='eval-error', className="mt-3"))

        return html.Div(eval_form), session_data, datetime.now().isoformat() # Trigger scroll

    # --- RENDER RANKING VIEW ---
    elif view == 'ranking':
        user_row = user_df[user_df.username == session_data['user']]
        user_order_str = user_row["order"].values[0].replace("–", "-")
        sample_codes = sorted([code.strip() for code in user_order_str.split("-")])
        rank_titles = ["Ngon nhất", "Thứ hai", "Thứ ba", "Thứ 4", "Thứ 5"]
        
        cols = []
        for i, title in enumerate(rank_titles[:len(sample_codes)]):
            cols.append(dbc.Col(
                dbc.Card([
                    dbc.CardHeader(title),
                    dbc.CardBody(dcc.Dropdown(sample_codes, id={'type': 'rank-dropdown', 'index': i}))
                ]),
                width=12, md=6, lg=2
            ))
        
        ranking_layout = html.Div([
            html.H4("Thứ hạng các sản phẩm"),
            html.P("Hãy sắp xếp các sản phẩm theo thứ tự ngon nhất đến kém ngon nhất", className="text-muted"),
            dbc.Row(cols, className="g-3"),
            dbc.Button("Xác nhận và Hoàn thành", id='rank-button', color='success', n_clicks=0, className="mt-4 w-100"),
            html.Div(id='rank-error', className="mt-3")
        ])
        return ranking_layout, session_data, datetime.now().isoformat() # Trigger scroll
    
    # --- RENDER THANK YOU VIEW ---
    elif view == 'thank_you':
        thank_you_layout = dbc.Alert([
            html.H4("✅ Bạn đã hoàn thành tất cả các mẫu!", className="alert-heading"),
            html.P("Cảm ơn bạn đã tham gia! Kết quả của bạn đã được ghi nhận."),
            html.Hr(),
            dbc.Button("Tải kết quả về máy", id="download-button", color="info"),
            dcc.Download(id="download-dataframe-xlsx")
        ], color="success")
        return thank_you_layout, session_data, datetime.now().isoformat() # Trigger scroll

    return html.Div("Lỗi: Chế độ xem không xác định."), session_data, no_update


# --- Specific Callbacks for Button Clicks and Logic ---

@callback(
    Output('session-store', 'data', allow_duplicate=True),
    Output('login-error', 'children'),
    Input('login-button', 'n_clicks'),
    State('login-username', 'value'),
    State('login-password', 'value'),
    State('session-store', 'data'),
    prevent_initial_call=True
)
def handle_login(n_clicks, username, password, session_data):
    user_df = load_user_data()
    if user_df is None: return no_update, dbc.Alert("Lỗi file dữ liệu người dùng.", color="danger")
    
    user_match = user_df[(user_df.username == username) & (user_df.password == str(password))]
    if not user_match.empty:
        session_data['current_view'] = 'user_info'
        session_data['user'] = username
        return session_data, dbc.Alert("Đăng nhập thành công!", color="success")
    else:
        return no_update, dbc.Alert("Sai tên đăng nhập hoặc mật khẩu.", color="danger")

@callback(
    Output('session-store', 'data', allow_duplicate=True),
    Output('info-error', 'children'),
    Input('info-button', 'n_clicks'),
    State('info-name', 'value'),
    State('info-gender', 'value'),
    State('info-age', 'value'),
    State('info-occupation', 'value'),
    State('info-frequency', 'value'),
    State('session-store', 'data'),
    prevent_initial_call=True
)
def handle_user_info(n_clicks, name, gender, age, occ, freq, session_data):
    if not all([name, gender, age, occ, freq]):
        return no_update, dbc.Alert("❌ Vui lòng điền đầy đủ tất cả thông tin.", color="warning")
    
    session_data['user_info'] = {
        "full_name": name, "gender": gender, "age": age,
        "occupation": occ, "frequency": freq
    }
    session_data['current_view'] = 'instructions'
    return session_data, None

@callback(
    Output('session-store', 'data', allow_duplicate=True),
    Input('start-eval-button', 'n_clicks'),
    State('session-store', 'data'),
    prevent_initial_call=True
)
def start_evaluation(n_clicks, session_data):
    session_data['current_view'] = 'evaluation'
    return session_data

@callback(
    Output('session-store', 'data', allow_duplicate=True),
    Output('results-store', 'data'),
    Output('eval-error', 'children'),
    Input('eval-button', 'n_clicks'),
    State({'type': 'slider-sample', 'index': dash.ALL}, 'value'),
    State({'type': 'slider-ideal', 'index': dash.ALL}, 'value'),
    State({'type': 'slider-sample', 'index': dash.ALL}, 'id'),
    State('eval-preference', 'value'),
    State('session-store', 'data'),
    State('results-store', 'data'),
    prevent_initial_call=True
)
def handle_evaluation(n_clicks, sample_vals, ideal_vals, attr_ids, preference, session_data, results_data):
    if not preference:
        return no_update, no_update, dbc.Alert("❌ Vui lòng chọn mức độ ưa thích chung.", color="warning")
    
    user_df = load_user_data()
    user_row = user_df[user_df.username == session_data['user']]
    user_order_str = user_row["order"].values[0].replace("–", "-")
    sample_codes = [code.strip() for code in user_order_str.split("-")]
    sample_code = sample_codes[session_data['sample_index']]

    rating = {}
    for i, attr_id in enumerate(attr_ids):
        attr_name = attr_id['index']
        rating[f"{attr_name} - Cường độ mẫu"] = sample_vals[i]
        rating[f"{attr_name} - Cường độ lý tưởng"] = ideal_vals[i]

    full_record = {
        "username": session_data['user'],
        "sample": sample_code,
        **session_data['user_info'],
        "timestamp": datetime.now(timezone("Asia/Ho_Chi_Minh")).strftime("%Y-%m-%d %H:%M:%S"),
        **rating,
        "Ưa thích chung": int(preference.split(" ")[0])
    }
    
    if results_data is None: results_data = []
    results_data.append(full_record)
    
    session_data['sample_index'] += 1
    
    # **FIX**: Check if all samples have been evaluated and change the view.
    if session_data['sample_index'] >= len(sample_codes):
        session_data['current_view'] = 'ranking'

    return session_data, results_data, None

@callback(
    Output('session-store', 'data', allow_duplicate=True),
    Output('results-store', 'data', allow_duplicate=True),
    Output('rank-error', 'children'),
    Input('rank-button', 'n_clicks'),
    State({'type': 'rank-dropdown', 'index': dash.ALL}, 'value'),
    State('session-store', 'data'),
    State('results-store', 'data'),
    prevent_initial_call=True
)
def handle_ranking(n_clicks, ranks, session_data, results_data):
    if not all(ranks):
        return no_update, no_update, dbc.Alert("❌ Vui lòng xếp hạng cho tất cả các mục.", color="warning")
    if len(set(ranks)) != len(ranks):
        return no_update, no_update, dbc.Alert("❌ Mỗi sản phẩm chỉ được chọn một lần.", color="warning")

    rank_titles = ["Ngon nhất", "Thứ hai", "Thứ ba", "Thứ 4", "Thứ 5"]
    ranking_data = {f"Thứ hạng - {rank_titles[i]}": rank for i, rank in enumerate(ranks)}
    
    # Add ranking data to the first record
    if results_data:
        results_data[0].update(ranking_data)
        
    # Save to Google Sheet now
    client = connect_to_google_sheets()
    if client:
        df_results = pd.DataFrame(results_data)
        sheet_id = "13XRlhwoQY-ErLy75l8B0fOv-KyIoO6p_VlzkoUnfUl0"
        append_to_google_sheet(df_results, sheet_id, client)
        
    session_data['current_view'] = 'thank_you'
    return session_data, results_data, None

@callback(
    Output("download-dataframe-xlsx", "data"),
    Input("download-button", "n_clicks"),
    State('results-store', 'data'),
    State('session-store', 'data'),
    prevent_initial_call=True,
)
def download_results(n_clicks, results_data, session_data):
    df = pd.DataFrame(results_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='results')
    data = output.getvalue()
    return dcc.send_bytes(data, f"ket_qua_{session_data.get('user', 'user')}.xlsx")


# --- CLIENT-SIDE CALLBACK FOR SCROLLING ---
# This JavaScript callback runs in the browser. It listens for changes
# on the 'scroll-trigger' div and scrolls the window to the top.
app.clientside_callback(
    """
    function(trigger) {
        if (trigger) {
            setTimeout(function() {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }, 200);
        }
        return null;
    }
    """,
    Output('scroll-trigger', 'className'), # Dummy output
    Input('scroll-trigger', 'children')
)


# --- RUN THE APP ---
if __name__ == '__main__':
    app.run(debug=True)
