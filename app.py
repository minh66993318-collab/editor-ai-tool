import hashlib
import html
import random
import re
import smtplib
import sqlite3
import string
import time
from email.message import EmailMessage
import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory
import streamlit as st
import streamlit.components.v1 as components

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG & LÀM SẠCH API KEY
# ==========================================
RAW_KEY = st.secrets.get("GEMINI_API_KEY", "")
GEMINI_API_KEY = str(RAW_KEY).strip(" \"'\t\r\n")

SENDER_GMAIL = str(st.secrets.get("SENDER_GMAIL", "")).strip(" \"'\t\r\n")
SENDER_APP_PASSWORD = str(st.secrets.get("SENDER_APP_PASSWORD", "")).strip(" \"'\t\r\n")

# --- CÔNG THỨC DỊCH TIẾNG VIỆT ---
FORMULA_VIETNAMESE = """
CÔNG THỨC XỬ LÝ KỊCH BẢN VIDEO (TIẾNG VIỆT)
Vai trò của bạn: Bạn là một Trợ lý Biên tập Video chuyên nghiệp. Nhiệm vụ của bạn là tiếp nhận kịch bản gốc và chuyển sang bản kịch bản tiếng Việt chuẩn chỉnh, trích xuất từ khóa/Text Overlay cho Editor.

I. QUY TẮC TÓM TẮT & PHÂN ĐOẠN (TUÂN THỦ TUYỆT ĐỐI)
- Phần Tóm tắt tổng quan: Ở ngay đầu kết quả, BẮT BUỘC phải có 1 đoạn tóm tắt ngắn gọn 2-3 câu khái quát chủ đề chính và mạch nội dung của video, trình bày dạng: ### 📌 **Tóm tắt tổng quan** (Sau đó chèn dòng phân cách `---`).
- Phân đoạn chi tiết: Nối tiếp và giữ nguyên các phân đoạn của kịch bản gốc.
- Định dạng Đề mục: Tất cả các đề mục/phân đoạn BẮT BUỘC trình bày dạng: ### 🎬 **X. [Tên Phân Đoạn]** (VD: ### 🎬 **1. Hook & Mở đầu**).
- Xuống dòng & Khoảng cách: Sau khi viết xong tiêu đề đề mục, BẮT BUỘC phải xuống dòng và chèn 1 dòng trống trước khi bắt đầu nội dung.
- KHÔNG sử dụng cụm từ hoặc thẻ "ON SCREEN:" hay ghi chú kỹ thuật thừa mứa.

II. QUY TẮC DỊCH THUẬT VÀ TRÍCH XUẤT TEXT OVERLAY
- Dịch toàn bộ nội dung sang tiếng Việt văn phong tự nhiên. KHÔNG viết nối câu tiếng Anh ngay bên cạnh câu tiếng Việt.
- Định dạng Trích xuất: Với những từ khóa, thuật ngữ hoặc câu chốt muốn trích xuất cho Editor làm Text Overlay, BẮT BUỘC viết trong ngoặc kép theo chuẩn: “Nội dung hiển thị tiếng Việt :: Text tiếng Anh gốc” (Ví dụ: “Tăng trưởng đột phá :: Breakthrough growth”).
- Nếu kịch bản gốc là tiếng Việt hoặc không có text tiếng Anh tương ứng, chỉ cần viết dạng: “Nội dung nhấn mạnh”.
"""

# --- CÔNG THỨC GIỮ NGUYÊN NGÔN NGỮ GỐC ---
FORMULA_ORIGINAL = """
CÔNG THỨC XỬ LÝ KỊCH BẢN VIDEO (GIỮ NGUYÊN NGÔN NGỮ GỐC)
Vai trò của bạn: Bạn là một Trợ lý Biên tập Video chuyên nghiệp. Nhiệm vụ của bạn là giữ nguyên ngôn ngữ gốc của kịch bản và trích xuất các đoạn Text Overlay/Graphic theo chuẩn Editor.

I. QUY TẮC TÓM TẮT & PHÂN ĐOẠN:
- Overview Summary: At the very top, MUST include a brief summary section (2-3 sentences) formatted as: ### 📌 **Overview Summary** followed by a separator `---`.
- Section Headings format: ### 🎬 **X. [Section Name]**
- Xuống dòng & Khoảng cách: Sau khi viết xong tiêu đề đề mục, BẮT BUỘC phải xuống dòng và chèn 1 dòng trống trước khi bắt đầu nội dung.

II. QUY TẮC TRÍCH XUẤT TEXT OVERLAY:
- Giữ nguyên ngôn ngữ gốc của kịch bản.
- Tất cả các từ khóa quan trọng, thuật ngữ, câu chốt trích xuất cho Editor hiển thị trên màn hình BẮT BUỘC phải nằm trong ngoặc kép dạng: “Text Overlay”.
"""

# ==========================================
# 2. HÀM CHUYỂN ĐỔI TEXT SANG HTML & JAVASCRIPT COPY
# ==========================================
def convert_quotes_to_copyable_html(text):
    custom_css = """
    <style>
    .editor-hl {
        color: #818CF8 !important;
        font-weight: 600;
        border-bottom: 2px dashed #818CF8;
        cursor: pointer;
        position: relative;
        display: inline-block;
        padding: 2px 6px;
        margin: 0 2px;
        border-radius: 4px;
        transition: background-color 0.2s ease, color 0.2s ease;
        user-select: text;
    }
    .editor-hl:hover {
        background-color: rgba(99, 102, 241, 0.2);
        color: #A5B4FC !important;
        border-bottom-style: solid;
    }
    .editor-hl .hl-tooltip {
        visibility: hidden;
        opacity: 0;
        width: max-content;
        max-width: 320px;
        background-color: #0F172A;
        color: #F8FAFC;
        text-align: center;
        border-radius: 8px;
        padding: 8px 12px;
        position: absolute;
        z-index: 99999;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%) translateY(-8px);
        transition: opacity 0.2s ease, transform 0.2s ease, visibility 0.2s;
        font-size: 0.83rem;
        font-weight: 500;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.15);
        pointer-events: auto;
        line-height: 1.4;
        white-space: normal;
    }
    .editor-hl .hl-tooltip::after {
        content: "";
        position: absolute;
        top: 100%;
        left: 0;
        width: 100%;
        height: 15px;
    }
    .editor-hl:hover .hl-tooltip {
        visibility: visible;
        opacity: 1;
        transform: translateX(-50%) translateY(-10px);
    }
    @keyframes copyPulse {
        0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.8); }
        50% { transform: scale(1.06); box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
        100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    .editor-hl.copied {
        animation: copyPulse 0.4s ease-out;
        background-color: rgba(16, 185, 129, 0.3) !important;
        color: #34D399 !important;
        border-bottom-color: #34D399 !important;
    }
    </style>
    """

    pattern = r'["“]([^"”]+)["”]'

    def replace_match(match):
        content = match.group(1).strip()
        if "::" in content:
            parts = content.split("::", 1)
            vi_text = parts[0].strip()
            en_text = parts[1].strip()
            clean_copy = html.escape(vi_text)
            orig_tooltip = html.escape(f"{en_text} (Nhấp để copy)")
            display_text = vi_text
        else:
            clean_copy = html.escape(content)
            orig_tooltip = "Nhấp để copy"
            display_text = content

        return f'''<span class="editor-hl copy-trigger" data-copytext="{clean_copy}"><span class="hl-tooltip"><span class="hl-tooltip-text">{orig_tooltip}</span></span>{display_text}</span>'''

    rendered_html = re.sub(pattern, replace_match, text)
    return custom_css + rendered_html


def inject_copy_javascript():
    js_script = """
    <script>
    function setupCopyListeners() {
        try {
            const parentDoc = window.parent.document;
            const copyElements = parentDoc.querySelectorAll('.copy-trigger:not([data-listener-attached])');
            
            copyElements.forEach(function(el) {
                el.setAttribute('data-listener-attached', 'true');
                el.addEventListener('click', function(e) {
                    e.stopPropagation();
                    const textToCopy = this.getAttribute('data-copytext');
                    
                    function handleSuccess() {
                        const tip = el.querySelector('.hl-tooltip-text');
                        if (tip) {
                            if (!tip.hasAttribute('data-orig')) {
                                tip.setAttribute('data-orig', tip.innerText);
                            }
                            tip.innerText = 'Đã copy vào Clipboard!';
                            el.classList.remove('copied');
                            void el.offsetWidth;
                            el.classList.add('copied');
                            setTimeout(function() {
                                tip.innerText = tip.getAttribute('data-orig');
                                el.classList.remove('copied');
                            }, 1200);
                        }
                    }

                    if (parentDoc.defaultView && parentDoc.defaultView.navigator.clipboard) {
                        parentDoc.defaultView.navigator.clipboard.writeText(textToCopy)
                            .then(handleSuccess)
                            .catch(function() {
                                fallbackCopy(parentDoc, textToCopy);
                                handleSuccess();
                            });
                    } else {
                        fallbackCopy(parentDoc, textToCopy);
                        handleSuccess();
                    }
                });
            });
        } catch(err) {
            console.error("Lỗi gán Copy listener:", err);
        }
    }

    function fallbackCopy(parentDoc, text) {
        const textArea = parentDoc.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.top = "-9999px";
        textArea.style.left = "-9999px";
        parentDoc.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
            parentDoc.execCommand('copy');
        } catch (e) {}
        parentDoc.body.removeChild(textArea);
    }

    setInterval(setupCopyListeners, 500);
    </script>
    """
    components.html(js_script, height=0, width=0)


def clean_script_for_download(text):
    cleaned = re.sub(r'["“]([^"”]+)::([^"”]+)["”]', r"\1 (\2)", text)
    cleaned = re.sub(r'["“]([^"”]+)["”]', r"\1", text)
    return cleaned

# ==========================================
# 3. XỬ LÝ DATABASE & BẢO MẬT (SQLITE)
# ==========================================
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users 
                 (email TEXT PRIMARY KEY, password_hash TEXT, reset_otp TEXT)""")
    try:
        c.execute("ALTER TABLE users ADD COLUMN reset_otp TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(email, password):
    try:
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, hash_password(password)))
        conn.commit(); conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def verify_user(email, password):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE email=?", (email,))
    result = c.fetchone()
    conn.close()
    return result and result[0] == hash_password(password)

def save_otp(email, otp):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT email FROM users WHERE email=?", (email,))
    if not c.fetchone():
        conn.close(); return False
    c.execute("UPDATE users SET reset_otp=? WHERE email=?", (otp, email))
    conn.commit(); conn.close()
    return True

def verify_otp_and_update_password(email, otp, new_password):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT reset_otp FROM users WHERE email=?", (email,))
    result = c.fetchone()
    if result and result[0] and str(result[0]).strip() == str(otp).strip():
        c.execute("UPDATE users SET password_hash=?, reset_otp=NULL WHERE email=?", (hash_password(new_password), email))
        conn.commit(); conn.close()
        return True
    conn.close()
    return False

def update_password(email, new_password):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("UPDATE users SET password_hash=? WHERE email=?", (hash_password(new_password), email))
    conn.commit(); conn.close()

def send_otp_email(receiver_email, otp):
    try:
        msg = EmailMessage()
        msg["Subject"] = "Ma OTP Dat Lai Mat Khau - Tro Ly Kich Ban Video"
        msg["From"] = SENDER_GMAIL
        msg["To"] = receiver_email
        msg.set_content(f"Chào bạn,\n\nMã xác minh OTP để đặt lại tài khoản là: {otp}")
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_GMAIL, SENDER_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Lỗi gửi email: {e}")
        return False

# ==========================================
# 4. GIAO DIỆN STREAMLIT
# ==========================================
st.set_page_config(page_title="Trợ Lý Kịch Bản Video", page_icon="🎬", layout="wide")

hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stHeader"] {display: none;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

init_db()

# KHỞI TẠO SESSION STATE
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "final_result" not in st.session_state: st.session_state.final_result = None
if "is_processing" not in st.session_state: st.session_state.is_processing = False
if "chat_messages" not in st.session_state: st.session_state.chat_messages = []

if not st.session_state.logged_in:
    st.title("🎬 Trợ Lý Biên Tập Kịch Bản Video")
    tab_login, tab_register, tab_forgot = st.tabs(["🔑 Đăng Nhập", "📝 Đăng Ký", "❓ Quên Mật Khẩu"])

    with tab_login:
        login_email = st.text_input("Gmail đăng nhập:", key="login_email").strip().lower()
        login_password = st.text_input("Mật khẩu:", type="password", key="login_pass")
        if st.button("Đăng Nhập", type="primary", use_container_width=True):
            if verify_user(login_email, login_password):
                st.session_state.logged_in = True
                st.session_state.user_email = login_email
                st.rerun()
            else:
                st.error("Gmail hoặc Mật khẩu không chính xác!")

    with tab_register:
        reg_email = st.text_input("Nhập Gmail đăng ký:", key="reg_email").strip().lower()
        reg_password = st.text_input("Tạo mật khẩu:", type="password", key="reg_pass")
        reg_confirm = st.text_input("Nhập lại mật khẩu:", type="password", key="reg_conf")
        if st.button("Tạo Tài Khoản", type="primary", use_container_width=True):
            if reg_password != reg_confirm:
                st.error("Mật khẩu không trùng khớp!")
            elif register_user(reg_email, reg_password):
                st.success("🎉 Đăng ký thành công! Vui lòng chuyển sang tab Đăng Nhập.")
            else:
                st.error("Gmail đã tồn tại!")

    with tab_forgot:
        forgot_email = st.text_input("Nhập Gmail đã đăng ký:", key="forgot_email").strip().lower()
        if st.button("📩 Gửi Mã OTP"):
            otp_code = "".join(random.choices(string.digits, k=6))
            if save_otp(forgot_email, otp_code) and send_otp_email(forgot_email, otp_code):
                st.success("Đã gửi mã OTP qua email!")
        otp_input = st.text_input("Nhập Mã OTP:", key="otp_in").strip()
        new_pass_input = st.text_input("Mật khẩu mới:", type="password", key="new_p_in")
        if st.button("🔄 Đặt Lại Mật Khẩu", type="primary", use_container_width=True):
            if verify_otp_and_update_password(forgot_email, otp_input, new_pass_input):
                st.success("Đổi mật khẩu thành công!")

else:
    with st.sidebar:
        st.write(f"👤 **Tài khoản:** `{st.session_state.user_email}`")
        if st.button("🚪 Đăng Xuất", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.session_state.final_result = None
            st.rerun()

    st.title("🎬 Trợ Lý Kịch Bản Video")

    # BỐ CỤC 2 CỘT CHUẨN MÔ HÌNH DỰNG PHIM (TRÁI: KỊCH BẢN, PHẢI: CHAT AI)
    col_main, col_chat = st.columns([7, 3], gap="large")

    with col_main:
        mode_option = st.radio(
            "🌐 **Chọn chế độ xử lý kịch bản:**",
            options=[
                "🇻🇳 Dịch thuật sang Tiếng Việt + Trích xuất Text",
                "🌐 Giữ nguyên ngôn ngữ gốc + Trích xuất Text",
            ],
            horizontal=True,
        )

        with st.form("script_analysis_form"):
            script_input = st.text_area("Dán kịch bản video của bạn vào đây:", height=250)
            submit_btn = st.form_submit_button("✨ Tối Ưu Kịch Bản", type="primary", use_container_width=True, disabled=st.session_state.is_processing)

        if submit_btn and script_input.strip():
            if not GEMINI_API_KEY:
                st.error("Chưa cấu hình API Key!")
            else:
                st.session_state.is_processing = True
                status_box = st.empty()
                status_box.info("⏳ Đang xử lý kịch bản với AI...")
                try:
                    genai.configure(api_key=GEMINI_API_KEY)
                    model = genai.GenerativeModel("gemini-3.6-flash")
                    instruction = FORMULA_VIETNAMESE if "Tiếng Việt" in mode_option else FORMULA_ORIGINAL
                    response = model.generate_content(f"{instruction}\n\n--- KỊCH BẢN ---\n{script_input}")
                    st.session_state.final_result = response.text
                except Exception as e:
                    st.error(f"Lỗi: {e}")
                st.session_state.is_processing = False
                st.rerun()

        if st.session_state.final_result:
            st.success("✨ Kịch bản đã sẵn sàng!")
            if st.button("📥 Tải Kịch Bản (.txt)"):
                st.download_button("Tải xuống", clean_script_for_download(st.session_state.final_result), file_name="Kich_Ban.txt")
            html_output = convert_quotes_to_copyable_html(st.session_state.final_result)
            st.markdown(html_output, unsafe_allow_html=True)
            inject_copy_javascript()

    # --- CỘT PHẢI: KHUNG CHAT AI TRỢ LÝ ---
    with col_chat:
        st.markdown("""<div style="padding: 8px; background: #1E293B; border-radius: 8px; text-align: center; font-weight: bold; margin-bottom: 10px;">💬 Trợ lý Chat AI</div>""", unsafe_allow_html=True)
        
        chat_container = st.container(height=520)
        with chat_container:
            if not st.session_state.chat_messages:
                st.caption("Tra cứu thuật ngữ, hỏi đáp mẹo edit hoặc tìm kiếm thông tin nhanh tại đây...")
            for msg in st.session_state.chat_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        if chat_input := st.chat_input("Nhắn gì đó cho AI..."):
            st.session_state.chat_messages.append({"role": "user", "content": chat_input})
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(chat_input)
                with st.chat_message("assistant"):
                    try:
                        genai.configure(api_key=GEMINI_API_KEY)
                        chat_model = genai.GenerativeModel("gemini-1.5-flash")
                        history = [{"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]} for m in st.session_state.chat_messages[:-1]]
                        chat_session = chat_model.start_chat(history=history)
                        response = chat_session.send_message(chat_input)
                        st.markdown(response.text)
                        st.session_state.chat_messages.append({"role": "assistant", "content": response.text})
                    except Exception as e:
                        err = f"Lỗi phản hồi: {e}"
                        st.error(err)
                        st.session_state.chat_messages.append({"role": "assistant", "content": err})
