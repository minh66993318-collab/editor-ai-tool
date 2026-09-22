import streamlit as st
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import sqlite3
import hashlib
import smtplib
import random
import string
import re
from email.message import EmailMessage

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG
# ==========================================
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "").strip()
MODEL_NAME = "gemini-1.5-flash"

SENDER_GMAIL = st.secrets.get("SENDER_GMAIL", "").strip()
SENDER_APP_PASSWORD = st.secrets.get("SENDER_APP_PASSWORD", "").strip()

FORMULA_VIETNAMESE = """
🤖 CÔNG THỨC MỞ XỬ LÝ KỊCH BẢN EDIT VIDEO (ĐA THỂ LOẠI)
Vai trò của bạn: Bạn là một Trợ lý Biên tập Video chuyên nghiệp. Nhiệm vụ của bạn là tiếp nhận kịch bản gốc và xử lý thành bản dịch tiếng Việt chuẩn chỉnh, đi kèm các đoạn Text Overlay/Graphic trích xuất sẵn theo chuẩn Editor để copy/paste trực tiếp lên phần mềm dựng phim.

I. QUY TẮC PHÂN ĐOẠN & NGUYÊN TẮC TRÌNH BÀY (TUÂN THỦ TUYỆT ĐỐI)
- Linh hoạt theo Kịch bản gốc: Nối tiếp và giữ nguyên các phân đoạn/tiêu đề phân đoạn của kịch bản gốc. Nếu chưa chia, tự động chia thành các phần logic.
- Định dạng Đánh số Phân đoạn: Tất cả phân đoạn bắt buộc đánh số thứ tự dạng: **X. [Tên Phân Đoạn]** (VD: **1. Hook & Mở đầu**). KHÔNG viết cách khoảng trước dấu chấm.
- Giữ nguyên ghi chú kỹ thuật: Dữ liệu về góc máy, SFX, VFX, B-roll được dịch/giữ nguyên định dạng và đặt đúng vị trí.

II. QUY TẮC DỊCH THUẬT VÀ XỬ LÝ THẺ ON-SCREEN / TEXT OVERLAY
- Dịch sát nghĩa & Đúng ngữ cảnh 100%: Dịch toàn bộ nội dung sang tiếng Việt văn phong tự nhiên.
- Xử lý Thẻ Đồ hoạ (ON SCREEN / LOWER THIRD / PULL QUOTE): Dịch tiêu đề/mô tả sang tiếng Việt. Phần Text tiếng Anh gốc trích xuất hiển thị trên màn hình phải viết hoa chữ cái đầu và nằm trong ngoặc kép “ ”.
Cấu trúc: ON SCREEN: [Nội dung dịch tiếng Việt] “ [Text tiếng Anh gốc viết hoa chữ cái đầu] ”

III. QUY TẮC TRÍCH XUẤT TEXT TIẾNG ANH CHO EDITOR
- Định dạng Chuẩn Copy: Mọi cụm text tiếng Anh trích xuất ĐỀU PHẢI nằm trong ngoặc kép “ ” và chỉ viết hoa chữ cái đầu tiên của chuỗi text đó.
- Vị trí Đặt Text: Đặt cụm text tiếng Anh trích xuất ngay bên cạnh hoặc sau từ/cụm từ tiếng Việt tương ứng.
- Phân bổ Độ dài: Đoạn liệt kê/khái niệm dùng từ khóa ngắn (1-3 từ). Câu chốt/tóm tắt trích xuất trọn vẹn cả câu.

IV. ĐỊNH DẠNG ĐẦU RA MẪU:
**1. [Tên phân đoạn 1]**
ON SCREEN: [Nội dung tiếng Việt] “ [Text tiếng Anh gốc] ”
[Toàn bộ lời thoại/bản dịch tiếng Việt đầy đủ, có chèn các cụm “ Text ” cần trích xuất]
"""

FORMULA_ORIGINAL = """
🤖 CÔNG THỨC XỬ LÝ KỊCH BẢN EDIT VIDEO (GIỮ NGUYÊN NGÔN NGỮ GỐC)
Vai trò của bạn: Bạn là một Trợ lý Biên tập Video chuyên nghiệp. Nhiệm vụ của bạn là giữ nguyên ngôn ngữ gốc của kịch bản và trích xuất các đoạn Text Overlay/Graphic theo chuẩn Editor để copy/paste trực tiếp.

I. QUY TẮC PHÂN ĐOẠN:
- Đánh số thứ tự dạng: **X. [Tên Phân Đoạn]** (VD: **1. Hook & Introduction**).

II. QUY TẮC TRÍCH XUẤT TEXT OVERLAY:
- Giữ nguyên ngôn ngữ gốc của kịch bản.
- Tất cả các từ khóa quan trọng, thuật ngữ, câu chốt trích xuất cho Editor hiển thị trên màn hình BẮT BUỘC phải nằm trong ngoặc kép “ ”.
- Chỉ viết hoa chữ cái đầu tiên của chuỗi text đó.

III. ĐỊNH DẠNG ĐẦU RA MẪU:
**1. [Tên phân đoạn 1]**
ON SCREEN: [Mô tả] “ [Text Overlay] ”
[Nội dung kịch bản gốc kèm các cụm “ Text ” trích xuất]
"""

# ==========================================
# 2. HÀM TẠO NÚT BẤM CLICK-TO-COPY
# ==========================================
def convert_quotes_to_copyable_html(text):
    pattern = r'["“]([^"”]+)["”]'
    def replace_with_button(match):
        extracted = match.group(1).strip()
        return f'''<span title="Bấm để copy" onclick="navigator.clipboard.writeText('{extracted}'); this.style.backgroundColor='#10B981'; this.style.color='#ffffff'; setTimeout(() => {{ this.style.backgroundColor='#e0e7ff'; this.style.color='#3730a3'; }}, 1000);" style="cursor: pointer; background-color: #e0e7ff; color: #3730a3; padding: 3px 10px; border-radius: 6px; font-weight: 600; font-family: monospace; border: 1px solid #c7d2fe; display: inline-block; margin: 2px 4px; user-select: none;">📋 “ {extracted} ”</span>'''

    return re.sub(pattern, replace_with_button, text)

# ==========================================
# 3. XỬ LÝ DATABASE & BẢO MẬT (SQLITE)
# ==========================================
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (email TEXT PRIMARY KEY, password_hash TEXT, reset_otp TEXT)''')
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
        conn.commit()
        conn.close()
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
        conn.close()
        return False
    c.execute("UPDATE users SET reset_otp=? WHERE email=?", (otp, email))
    conn.commit()
    conn.close()
    return True

def verify_otp_and_update_password(email, otp, new_password):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT reset_otp FROM users WHERE email=?", (email,))
    result = c.fetchone()
    if result and result[0] and str(result[0]).strip() == str(otp).strip():
        c.execute("UPDATE users SET password_hash=?, reset_otp=NULL WHERE email=?", (hash_password(new_password), email))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def update_password(email, new_password):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("UPDATE users SET password_hash=? WHERE email=?", (hash_password(new_password), email))
    conn.commit()
    conn.close()

def send_otp_email(receiver_email, otp):
    try:
        msg = EmailMessage()
        msg['Subject'] = "Ma OTP Dat Lai Mat Khau - AI Script Analyzer"
        msg['From'] = SENDER_GMAIL
        msg['To'] = receiver_email
        msg.set_content(
            f"Chào bạn,\n\n"
            f"Mã xác minh OTP để đặt lại mật khẩu cho tài khoản {receiver_email} là: {otp}\n\n"
            f"Vui lòng không chia sẻ mã này cho bất kỳ ai."
        )

        server = smtplib.SMTP('smtp.gmail.com', 587)
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
st.set_page_config(page_title="AI Script Analyzer", page_icon="🎬", layout="wide")

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

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""

if not st.session_state.logged_in:
    st.title("🎬 AI Script Analyzer for Editors")
    st.caption("Công cụ phân tích & trích xuất Text Overlay chuyên nghiệp cho Video Editor.")

    tab_login, tab_register, tab_forgot = st.tabs(["🔑 Đăng Nhập", "📝 Đăng Ký", "❓ Quên Mật Khẩu"])

    with tab_login:
        login_email = st.text_input("Gmail đăng nhập:", key="login_email").strip().lower()
        login_password = st.text_input("Mật khẩu:", type="password", key="login_pass")
        if st.button("Đăng Nhập", type="primary", use_container_width=True):
            if verify_user(login_email, login_password):
                st.session_state.logged_in = True
                st.session_state.user_email = login_email
                st.success("Đăng nhập thành công!")
                st.rerun()
            else:
                st.error("Gmail hoặc Mật khẩu không chính xác!")

    with tab_register:
        reg_email = st.text_input("Nhập Gmail đăng ký:", key="reg_email").strip().lower()
        reg_password = st.text_input("Tạo mật khẩu:", type="password", key="reg_pass")
        reg_confirm = st.text_input("Nhập lại mật khẩu:", type="password", key="reg_conf")
        
        if st.button("Tạo Tài Khoản", type="primary", use_container_width=True):
            if not reg_email or "@" not in reg_email:
                st.warning("Vui lòng nhập đúng định dạng Gmail!")
            elif len(reg_password) < 6:
                st.warning("Mật khẩu phải có ít nhất 6 ký tự!")
            elif reg_password != reg_confirm:
                st.error("Mật khẩu nhập lại không trùng khớp!")
            else:
                if register_user(reg_email, reg_password):
                    st.success("🎉 Đăng ký tài khoản thành công! Vui lòng chuyển sang tab **Đăng Nhập**.")
                else:
                    st.error("Gmail này đã được đăng ký từ trước!")

    with tab_forgot:
        st.subheader("🔑 Khôi phục mật khẩu qua Mã OTP")
        forgot_email = st.text_input("Nhập Gmail đã đăng ký:", key="forgot_email").strip().lower()
        
        col_send, _ = st.columns([1, 1])
        with col_send:
            if st.button("📩 Gửi Mã OTP về Gmail"):
                if not forgot_email or "@" not in forgot_email:
                    st.warning("Vui lòng nhập đúng địa chỉ Gmail!")
                else:
                    otp_code = ''.join(random.choices(string.digits, k=6))
                    if save_otp(forgot_email, otp_code):
                        if send_otp_email(forgot_email, otp_code):
                            st.success(f"✅ Mã OTP (6 chữ số) đã được gửi đến **{forgot_email}**. Vui lòng kiểm tra hộp thư!")
                        else:
                            st.error("Không thể gửi email OTP. Vui lòng kiểm tra cấu hình Gmail trong Secrets.")
                    else:
                        st.error("Gmail này chưa tồn tại trong hệ thống! Vui lòng đăng ký trước.")

        st.markdown("---")
        otp_input = st.text_input("Nhập Mã OTP (6 chữ số):", key="otp_in").strip()
        new_pass_input = st.text_input("Mật khẩu mới:", type="password", key="new_p_in")
        new_pass_confirm = st.text_input("Nhập lại mật khẩu mới:", type="password", key="new_p_conf")

        if st.button("🔄 Đặt Lại Mật Khẩu", type="primary", use_container_width=True):
            if not otp_input or not new_pass_input:
                st.warning("Vui lòng nhập đầy đủ Mã OTP và Mật khẩu mới!")
            elif len(new_pass_input) < 6:
                st.warning("Mật khẩu mới phải có ít nhất 6 ký tự!")
            elif new_pass_input != new_pass_confirm:
                st.error("Mật khẩu mới nhập lại không trùng khớp!")
            else:
                if verify_otp_and_update_password(forgot_email, otp_input, new_pass_input):
                    st.success("🎉 Đổi mật khẩu thành công! Bạn có thể đăng nhập ngay bằng mật khẩu mới.")
                else:
                    st.error("Mã OTP không chính xác!")

else:
    with st.sidebar:
        st.write(f"👤 **Tài khoản:** `{st.session_state.user_email}`")
        st.markdown("---")
        with st.expander("🔑 Đổi mật khẩu"):
            new_pass = st.text_input("Mật khẩu mới:", type="password")
            confirm_pass = st.text_input("Xác nhận mật khẩu:", type="password")
            if st.button("Lưu mật khẩu mới"):
                if new_pass and new_pass == confirm_pass:
                    update_password(st.session_state.user_email, new_pass)
                    st.success("✅ Đã đổi mật khẩu thành công!")
                else:
                    st.error("Mật khẩu không trùng khớp!")
        
        if st.button("🚪 Đăng Xuất", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            st.rerun()

    st.title("🎬 AI Phân Tích Kịch Bản Video")
    
    mode_option = st.radio(
        "🌐 **Chọn chế độ xử lý kịch bản:**",
        options=["🇻🇳 Dịch thuật sang Tiếng Việt + Trích xuất Text", "🌐 Giữ nguyên ngôn ngữ gốc + Trích xuất Text"],
        horizontal=True
    )

    script_input = st.text_area(
        "Dán kịch bản video của bạn vào đây:",
        height=280,
        placeholder="Paste kịch bản gốc vào đây..."
    )

    if st.button("🚀 Phân Tích Kịch Bản", type="primary", use_container_width=True):
        if not script_input.strip():
            st.warning("⚠️ Vui lòng nhập nội dung kịch bản!")
        else:
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                selected_instruction = FORMULA_VIETNAMESE if "Tiếng Việt" in mode_option else FORMULA_ORIGINAL
                
                # MỞ KHÓA BỘ LỌC AN TOÀN TRÁNH BỊ CHẶN VÔ LÝ
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }

                model = genai.GenerativeModel(
                    model_name=MODEL_NAME,
                    system_instruction=selected_instruction,
                    safety_settings=safety_settings
                )

                st.subheader("📝 Kết Quả Phân Tích (Thời Gian Thực):")
                
                # HÀM LỌC CHUNK CỦA STREAM AN TOÀN (100% KHÔNG LỖI)
                def safe_stream_generator():
                    response = model.generate_content(script_input, stream=True)
                    for chunk in response:
                        try:
                            if hasattr(chunk, 'text') and chunk.text:
                                yield chunk.text
                        except (ValueError, AttributeError):
                            continue

                # 🎯 STREAM CHỮ CHẠY TRỰC TIẾP RA MÀN HÌNH BẰNG TÍNH NĂNG NATIVE CỦA STREAMLIT
                full_text = st.write_stream(safe_stream_generator())

                if full_text and full_text.strip():
                    st.success("✅ Phân tích hoàn tất!")
                    st.caption("💡 **Mẹo Editor:** Dưới đây là bản tổng hợp kèm các nút `📋 “ Text ”` đã được tạo sẵn để bấm Copy nhanh!")
                    
                    # 🎯 TẠO NÚT CLICK-TO-COPY SAU KHI AI VIẾT XONG
                    html_output = convert_quotes_to_copyable_html(full_text)
                    st.markdown(html_output, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"❌ Lỗi xử lý AI: {e}")
