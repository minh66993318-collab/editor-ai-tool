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

# --- CÔNG THỨC DỊCH TIẾNG VIỆT (TÓM TẮT CHI TIẾT - FIX 9.3) ---
FORMULA_VIETNAMESE = """
CÔNG THỨC XỬ LÝ KỊCH BẢN VIDEO (TIẾNG VIỆT)
Vai trò của bạn: Bạn là một Trợ lý Biên tập Video chuyên nghiệp. Nhiệm vụ của bạn là tiếp nhận kịch bản gốc và chuyển sang bản kịch bản tiếng Việt chuẩn chỉnh, trích xuất từ khóa/Text Overlay cho Editor.

I. QUY TẮC TÓM TẮT & PHÂN ĐOẠN (TUÂN THỦ TUYỆT ĐỐI)
- Phần Tóm tắt tổng quan: Ở ngay đầu kết quả, BẮT BUỘC phải viết tóm tắt kỹ lưỡng bao gồm các ý sau dưới dạng gạch đầu dòng:
  - 🎯 **Chủ đề cốt lõi:** Nội dung trọng tâm của video.
  - 💡 **Thông điệp chính:** Giá trị cốt lõi truyền tải đến người xem.
  - 🎬 **Nhịp điệu & Phong cách dựng:** Gợi ý cách nhịp dựng, âm bản hoặc không khí video.
  Trình bày tiêu đề chính xác dạng: ### 📌 **Tóm tắt tổng quan** (Sau đó xuống dòng viết các ý chi tiết, kết thúc bằng một dòng phân cách `---`).
- Phân đoạn chi tiết: Nối tiếp và giữ nguyên các phân đoạn của kịch bản gốc.
- Định dạng Đề mục: Tất cả các đề mục/phân đoạn tiếp theo BẮT BUỘC trình bày dạng: ### 🎬 **X. [Tên Phân Đoạn]** (VD: ### 🎬 **1. Hook & Mở đầu**).
- Xuống dòng & Khoảng cách: Sau khi viết xong tiêu đề đề mục, BẮT BUỘC phải xuống dòng và chèn 1 dòng trống trước khi bắt đầu nội dung.
- KHÔNG sử dụng cụm từ hoặc thẻ "ON SCREEN:" hay ghi chú kỹ thuật thừa mứa.

II. QUY TẮC DỊCH THUẬT VÀ TRÍCH XUẤT TEXT OVERLAY
- Dịch toàn bộ nội dung sang tiếng Việt văn phong tự nhiên. KHÔNG viết nối câu tiếng Anh ngay bên cạnh câu tiếng Việt.
- Định dạng Trích xuất: Với những từ khóa, thuật ngữ hoặc câu chốt muốn trích xuất cho Editor làm Text Overlay, BẮT BUỘC viết trong ngoặc kép theo chuẩn: “Nội dung hiển thị tiếng Việt :: Text tiếng Anh gốc” (Ví dụ: “Tăng trưởng đột phá :: Breakthrough growth”).
- Nếu kịch bản gốc là tiếng Việt hoặc không có text tiếng Anh tương ứng, chỉ cần viết dạng: “Nội dung nhấn mạnh”.
- Phân bổ Độ dài: Đoạn liệt kê/khái niệm dùng từ khóa ngắn (1-3 từ). Câu chốt/tóm tắt trích xuất trọn vẹn cả câu.

III. ĐỊNH DẠNG ĐẦU RA MẪU:

### 📌 **Tóm tắt tổng quan**
- 🎯 **Chủ đề cốt lõi:** Khám phá phương pháp giải mã bộ bài Hoàng gia Tarot.
- 💡 **Thông điệp chính:** Nắm bắt chi tiết tính năng và cách đặt câu hỏi tương tác.
- 🎬 **Nhịp điệu & Phong cách dựng:** Dựng mạch lạc, trực quan, lôi cuốn.

---

### 🎬 **1. Mở đầu ấn tượng**

Chào mừng các bạn đến với video hôm nay. Chúng ta sẽ cùng khám phá bí quyết “Tăng trưởng doanh thu :: Revenue growth” trong ngành sáng tạo nội dung.
"""

# --- CÔNG THỨC GIỮ NGUYÊN NGÔN NGỮ GỐC (TÓM TẮT CHI TIẾT - FIX 9.3) ---
FORMULA_ORIGINAL = """
CÔNG THỨC XỬ LÝ KỊCH BẢN VIDEO (GIỮ NGUYÊN NGÔN NGỮ GỐC)
Vai trò của bạn: Bạn là một Trợ lý Biên tập Video chuyên nghiệp. Nhiệm vụ của bạn là giữ nguyên ngôn ngữ gốc của kịch bản và trích xuất các đoạn Text Overlay/Graphic theo chuẩn Editor.

I. QUY TẮC TÓM TẮT & PHÂN ĐOẠN:
- Overview Summary: At the very top, MUST include a detailed summary structured as bullet points:
  - 🎯 **Core Theme**
  - 💡 **Main Message**
  - 🎬 **Pacing & Editing Style**
  Formatted precisely as: ### 📌 **Overview Summary** followed by a separator `---`.
- Section Headings format: ### 🎬 **X. [Section Name]**
- Xuống dòng & Khoảng cách: Sau khi viết xong tiêu đề đề mục, BẮT BUỘC phải xuống dòng và chèn 1 dòng trống trước khi bắt đầu nội dung.
- KHÔNG sử dụng cụm từ hoặc thẻ "ON SCREEN:".

II. QUY TẮC TRÍCH XUẤT TEXT OVERLAY:
- Giữ nguyên ngôn ngữ gốc của kịch bản.
- Tất cả các từ khóa quan trọng, thuật ngữ, câu chốt trích xuất cho Editor hiển thị trên màn hình BẮT BUỘC phải nằm trong ngoặc kép dạng: “Text Overlay”.

III. ĐỊNH DẠNG ĐẦU RA MẪU:

### 📌 **Overview Summary**
- 🎯 **Core Theme:** Core growth strategies and content optimization.
- 💡 **Main Message:** Maximize creator performance.
- 🎬 **Pacing & Editing Style:** Dynamic and engaging pacing.

---

### 🎬 **1. Hook & Introduction**

Welcome to today's video. We will explore “Breakthrough growth” in content creation.
"""

# ==========================================
# 2. HÀM XỬ LÝ TÓM TẮT TÁCH BIỆT & HTML CLICK-TO-COPY (FIX 9.3)
# ==========================================
def parse_and_render_script(text):
    """
    Hàm này giờ sẽ trả về 2 phần riêng biệt:
    1. Chuỗi HTML chứa giao diện Tóm tắt (hoặc rỗng nếu không có)
    2. Chuỗi chứa Kịch bản chính (đã gắn mã HTML cho tooltip)
    """
    custom_css = """
    <style>
    .script-summary-card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border-left: 5px solid #6366F1;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 30px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
        color: #F8FAFC;
    }
    .script-summary-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #A5B4FC;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
        letter-spacing: 0.3px;
    }
    .script-summary-body {
        font-size: 0.95rem;
        line-height: 1.7;
        color: #E2E8F0;
    }
    .script-summary-body ul {
        margin: 6px 0 0 18px;
        padding: 0;
    }
    .script-summary-body li {
        margin-bottom: 8px;
    }

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

    summary_regex = r'(?:###\s*📌\s*\*\*Tóm tắt tổng quan\*\*\s*\n+|###\s*📌\s*Tóm tắt tổng quan\s*\n+|###\s*📌\s*\*\*Overview Summary\*\*\s*\n+)(.*?)(?=\n\s*---\s*|\n\s*###\s*🎬|$)'
    match = re.search(summary_regex, text, re.DOTALL | re.IGNORECASE)

    summary_card_html = ""
    main_content = text

    if match:
        raw_summary = match.group(1).strip()
        lines = raw_summary.split('\n')
        parsed_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith('- ') or line.startswith('* '):
                content_line = line[2:].strip()
                content_line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content_line)
                parsed_lines.append(f"<li>{content_line}</li>")
            elif line:
                parsed_lines.append(f"<p style='margin-bottom: 6px;'>{html.escape(line)}</p>")

        body_content = "".join(parsed_lines)
        if "<li>" in body_content:
            body_content = f"<ul>{body_content}</ul>"

        # Định dạng chuẩn HTML với tag đầy đủ, tách biệt rõ ràng
        summary_card_html = f"""
        <div class="script-summary-card">
            <div class="script-summary-title">📌 Tóm tắt tổng quan kịch bản</div>
            <div class="script-summary-body">{body_content}</div>
        </div>
        """

        # Cắt bỏ phần tóm tắt khỏi chuỗi chính
        main_content = re.sub(summary_regex, '', text, flags=re.DOTALL | re.IGNORECASE)
        main_content = re.sub(r'^\s*---\s*', '', main_content.strip())

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

    rendered_main_content = custom_css + re.sub(pattern, replace_match, main_content)
    
    return summary_card_html, rendered_main_content


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
        } catch (e) {
            console.error('Fallback copy error:', e);
        }
        parentDoc.body.removeChild(textArea);
    }

    setInterval(setupCopyListeners, 500);
    </script>
    """
    components.html(js_script, height=0, width=0)


def clean_script_for_download(text):
    cleaned = re.sub(r'(?:###\s*📌\s*\*\*Tóm tắt tổng quan\*\*\s*\n+|###\s*📌\s*Tóm tắt tổng quan\s*\n+|###\s*📌\s*\*\*Overview Summary\*\*\s*\n+).*?(?=\n\s*###\s*🎬|$)', '', text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'^\s*---\s*', '', cleaned.strip())
    cleaned = re.sub(r'["“]([^"”]+)::([^"”]+)["”]', r"\1 (\2)", cleaned)
    cleaned = re.sub(r'["“]([^"”]+)["”]', r"\1", cleaned)
    return cleaned.strip()

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
        c.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, hash_password(password)),
        )
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
        c.execute(
            "UPDATE users SET password_hash=?, reset_otp=NULL WHERE email=?",
            (hash_password(new_password), email),
        )
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False


def update_password(email, new_password):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute(
        "UPDATE users SET password_hash=? WHERE email=?",
        (hash_password(new_password), email),
    )
    conn.commit()
    conn.close()


def send_otp_email(receiver_email, otp):
    try:
        msg = EmailMessage()
        msg["Subject"] = "Ma OTP Dat Lai Mat Khau - Tro Ly Kich Ban Video"
        msg["From"] = SENDER_GMAIL
        msg["To"] = receiver_email
        msg.set_content(
            f"Chào bạn,\n\n"
            f"Mã xác minh OTP để đặt lại mật khẩu cho tài khoản {receiver_email} là: {otp}\n\n"
            f"Vui lòng không chia sẻ mã này cho bất kỳ ai."
        )

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
st.set_page_config(
    page_title="Trợ Lý Kịch Bản Video", page_icon="🎬", layout="wide"
)

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

# QUẢN LÝ TRẠNG THÁI SESSION STATE
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "final_result" not in st.session_state:
    st.session_state.final_result = None
if "is_processing" not in st.session_state:
    st.session_state.is_processing = False

if not st.session_state.logged_in:
    st.title("🎬 Trợ Lý Biên Tập Kịch Bản Video")
    st.caption("Công cụ phân tích, tối ưu kịch bản & trích xuất Text Overlay chuyên nghiệp cho Video Editor.")

    tab_login, tab_register, tab_forgot = st.tabs(
        ["🔑 Đăng Nhập", "📝 Đăng Ký", "❓ Quên Mật Khẩu"]
    )

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
                    otp_code = "".join(random.choices(string.digits, k=6))
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
            st.session_state.final_result = None
            st.rerun()

    st.title("🎬 Trợ Lý Kịch Bản Video")

    mode_option = st.radio(
        "🌐 **Chọn chế độ xử lý kịch bản:**",
        options=[
            "🇻🇳 Dịch thuật sang Tiếng Việt + Trích xuất Text",
            "🌐 Giữ nguyên ngôn ngữ gốc + Trích xuất Text",
        ],
        horizontal=True,
    )

    # --- KHUNG NHẬP LIỆU BỌC TRONG FORM ĐỂ CÁCH LY THAO TÁC RE-RUN ---
    with st.form("script_analysis_form"):
        script_input = st.text_area(
            "Dán kịch bản video của bạn vào đây:",
            height=280,
            placeholder="Paste kịch bản gốc vào đây...",
        )

        char_count = len(script_input)
        word_count = len(script_input.split())
        est_minutes = round(word_count / 160, 1) if word_count > 0 else 0
        st.caption(
            f"📊 **Dung lượng kịch bản:** {char_count:,} ký tự | {word_count:,} từ |"
            f" **Ước tính thời lượng video:** ~{est_minutes} phút"
        )

        submit_btn = st.form_submit_button(
            "✨ Tối Ưu Kịch Bản",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.is_processing,
        )

    # --- THỰC THI PHÂN TÍCH KHI BẤM SUBMIT ---
    if submit_btn:
        if not script_input.strip():
            st.warning("⚠️ Vui lòng nhập nội dung kịch bản!")
        elif not GEMINI_API_KEY:
            st.error("❌ Chưa tìm thấy GEMINI_API_KEY trong Secrets của cấu hình!")
        else:
            st.session_state.is_processing = True
            st.session_state.final_result = None  # Xóa kết quả cũ

            try:
                selected_instruction = (
                    FORMULA_VIETNAMESE
                    if "Tiếng Việt" in mode_option
                    else FORMULA_ORIGINAL
                )

                if char_count < 1000:
                    est_sec, est_desc = 30, "~30 giây"
                elif char_count < 2000:
                    est_sec, est_desc = 60, "~1 phút"
                elif char_count < 3000:
                    est_sec, est_desc = 90, "~1.5 phút"
                else:
                    est_sec, est_desc = 120, "~2 phút"

                status_box = st.empty()
                progress_bar = st.progress(0)
                live_output_area = st.empty()

                spinner_style = """
                <style>
                .loading-spinner {
                    display: inline-block; width: 16px; height: 16px;
                    border: 2.5px solid #C7D2FE; border-radius: 50%;
                    border-top-color: #4F46E5; animation: spin 0.8s linear infinite;
                    margin-right: 8px; vertical-align: middle;
                }
                @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                </style>
                """

                status_box.markdown(
                    f"{spinner_style}<span style='display:inline-flex; align-items:center;'><b><span class='loading-spinner'></span>⏳ Đang kết nối máy chủ & xử lý kịch bản...</b> (Dự kiến: {est_desc})</span>",
                    unsafe_allow_html=True,
                )
                progress_bar.progress(10)

                # Gọi Gemini API với Stream = True
                genai.configure(api_key=GEMINI_API_KEY)
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }

                model = genai.GenerativeModel(
                    model_name="gemini-3.6-flash", safety_settings=safety_settings
                )

                prompt_payload = (
                    f"{selected_instruction}\n\n--- KỊCH BẢN CẦN XỬ LÝ ---\n{script_input}"
                )

                # STREAMING RESPONSE RENDERING
                response_stream = model.generate_content(prompt_payload, stream=True)
                accumulated_text = ""
                chunk_count = 0

                for chunk in response_stream:
                    if chunk.text:
                        accumulated_text += chunk.text
                        chunk_count += 1
                        current_p = min(15 + chunk_count * 5, 95)
                        progress_bar.progress(current_p)
                        status_box.markdown(
                            f"{spinner_style}<span style='display:inline-flex; align-items:center;'><b><span class='loading-spinner'></span>✨ Đang xuất kết quả kịch bản theo thời gian thực...</b></span>",
                            unsafe_allow_html=True,
                        )
                        
                        summary_html, main_content_html = parse_and_render_script(accumulated_text)
                        
                        # Hiển thị Tóm tắt tổng quan tách biệt
                        output = ""
                        if summary_html:
                            output += summary_html + "\n\n"
                        output += main_content_html
                        
                        live_output_area.markdown(output, unsafe_allow_html=True)
                        inject_copy_javascript()

                progress_bar.progress(100)
                status_box.empty()
                progress_bar.empty()

                st.session_state.final_result = accumulated_text
                st.session_state.is_processing = False
                st.rerun()

            except Exception as e:
                status_box.empty()
                progress_bar.empty()
                st.session_state.is_processing = False
                err_msg = str(e)
                if "429" in err_msg or "ResourceExhausted" in err_msg or "Quota exceeded" in err_msg:
                    st.warning("⏳ Máy chủ API Gemini đang bận do chạm hạn mức tần suất gửi request. Vui lòng chờ khoảng 15 - 30 giây rồi bấm **Tối Ưu Kịch Bản** lại nhé!")
                else:
                    st.error(f"❌ Đã xảy ra lỗi trong quá trình xử lý: {err_msg}")

    # --- HIỂN THỊ KẾT QUẢ TỪ SESSION STATE ---
    if st.session_state.final_result:
        st.success("✨ Kịch bản của bạn đã sẵn sàng!")

        col_info, col_download = st.columns([3, 1])
        with col_info:
            st.caption(
                "💡 **Mẹo:** Rê chuột vào các <span style='color:#818CF8; font-weight:bold;'>từ khóa đổi màu</span> để xem bản dịch. **Nhấp chuột 1 lần** để tự động Copy!",
                unsafe_allow_html=True,
            )
        with col_download:
            clean_txt = clean_script_for_download(st.session_state.final_result)
            st.download_button(
                label="📥 Tải Kịch Bản (.txt)",
                data=clean_txt,
                file_name=f"Kich_Ban_Editor_{time.strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        summary_html, main_content_html = parse_and_render_script(st.session_state.final_result)
        
        # Render phần Tóm Tắt bằng một lệnh tách biệt nếu có
        if summary_html:
            st.markdown(summary_html, unsafe_allow_html=True)
            
        # Render phần Nội dung chính bằng một lệnh khác
        st.markdown(main_content_html, unsafe_allow_html=True)
        inject_copy_javascript()
