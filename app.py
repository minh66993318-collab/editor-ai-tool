import streamlit as st
import google.generativeai as genai
import sqlite3
import hashlib
import smtplib
import random
import string
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header  # Thêm thư viện hỗ trợ Tiếng Việt cho tiêu đề email

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG
# ==========================================
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-1.5-flash"

SENDER_GMAIL = st.secrets.get("SENDER_GMAIL", "")
SENDER_APP_PASSWORD = st.secrets.get("SENDER_APP_PASSWORD", "")

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
                 (email TEXT PRIMARY KEY, password_hash TEXT)''')
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(email, password):
    try:
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("INSERT INTO users VALUES (?, ?)", (email, hash_password(password)))
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

def update_password(email, new_password):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("UPDATE users SET password_hash=? WHERE email=?", (hash_password(new_password), email))
    conn.commit()
    conn.close()

def send_password_email(receiver_email, generated_password):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_GMAIL
        msg['To'] = receiver_email
        # Mã hóa Tiêu đề tiếng Việt hỗ trợ UTF-8
        msg['Subject'] = Header("Mat Khau Truy Cap AI Script Analyzer", 'utf-8')

        body = f"Chào bạn,\n\nTài khoản truy cập Web AI Script Analyzer của bạn:\n- Gmail: {receiver_email}\n- Mật khẩu: {generated_password}\n\nBạn có thể đổi lại mật khẩu sau khi đăng nhập."
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

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
init_db()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""

if not st.session_state.logged_in:
    st.title("🎬 AI Script Analyzer for Editors")
    st.caption("Công cụ phân tích & trích xuất Text Overlay chuyên nghiệp cho Video Editor.")

    tab_login, tab_register = st.tabs(["🔑 Đăng Nhập", "📝 Đăng Ký Tài Khoản"])

    with tab_login:
        login_email = st.text_input("Gmail đăng nhập:", key="login_email").strip().lower()
        login_password = st.text_input("Mật khẩu:", type="password", key="login_pass")
        if st.button("Đăng Nhập", type="primary"):
            if verify_user(login_email, login_password):
                st.session_state.logged_in = True
                st.session_state.user_email = login_email
                st.rerun()
            else:
                st.error("Email hoặc Mật khẩu không chính xác!")

    with tab_register:
        reg_email = st.text_input("Nhập Gmail nhận mật khẩu:", key="reg_email").strip().lower()
        if st.button("Tạo Tài Khoản & Gửi Mật Khẩu"):
            if not reg_email or "@" not in reg_email:
                st.warning("Vui lòng nhập đúng định dạng Gmail!")
            else:
                random_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                with st.spinner("Đang gửi mật khẩu về Gmail..."):
                    if register_user(reg_email, random_pass):
                        if send_password_email(reg_email, random_pass):
                            st.success(f"✅ Mật khẩu đã được gửi về Gmail **{reg_email}**. Vui lòng kiểm tra hộp thư (hoặc mục Spam)!")
                        else:
                            st.error("Lỗi gửi email. Vui lòng kiểm tra lại thông tin Gmail tổng đài!")
                    else:
                        st.error("Gmail này đã được đăng ký từ trước!")

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
                with st.spinner("🤖 AI đang phân tích và trích xuất Text Overlay..."):
                    genai.configure(api_key=GEMINI_API_KEY)
                    
                    selected_instruction = FORMULA_VIETNAMESE if "Tiếng Việt" in mode_option else FORMULA_ORIGINAL
                    
                    model = genai.GenerativeModel(
                        model_name=MODEL_NAME,
                        system_instruction=selected_instruction
                    )
                    
                    response = model.generate_content(script_input)
                    raw_text = response.text
                    
                    st.success("✅ Phân tích hoàn tất!")
                    st.caption("💡 **Mẹo Editor:** Nhấp chuột trực tiếp vào các thẻ màu xanh `📋 “ Text ”` bên dưới để tự động Copy!")
                    
                    html_output = convert_quotes_to_copyable_html(raw_text)
                    st.markdown(html_output, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"❌ Lỗi xử lý AI: {e}")
