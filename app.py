import hashlib
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

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG & LÀM SẠCH API KEY
# ==========================================
RAW_KEY = st.secrets.get("GEMINI_API_KEY", "")
GEMINI_API_KEY = str(RAW_KEY).strip(" \"'\t\r\n")

SENDER_GMAIL = str(st.secrets.get("SENDER_GMAIL", "")).strip(" \"'\t\r\n")
SENDER_APP_PASSWORD = str(st.secrets.get("SENDER_APP_PASSWORD", "")).strip(
    " \"'\t\r\n"
)

# --- CÔNG THỨC DỊCH TIẾNG VIỆT ---
FORMULA_VIETNAMESE = """
CÔNG THỨC XỬ LÝ KỊCH BẢN VIDEO (TIẾNG VIỆT)
Vai trò của bạn: Bạn là một Trợ lý Biên tập Video chuyên nghiệp. Nhiệm vụ của bạn là tiếp nhận kịch bản gốc và chuyển sang bản kịch bản tiếng Việt chuẩn chỉnh, trích xuất từ khóa/Text Overlay cho Editor.

I. QUY TẮC PHÂN ĐOẠN & TRÌNH BÀY ĐỀ MỤC (TUÂN THỦ TUYỆT ĐỐI)
- Linh hoạt theo Kịch bản gốc: Nối tiếp và giữ nguyên các phân đoạn của kịch bản gốc. Nếu chưa chia, tự động chia thành các phần logic.
- Định dạng Đề mục: Tất cả các đề mục/phân đoạn BẮT BUỘC trình bày dạng: ### 🎬 **X. [Tên Phân Đoạn]** (VD: ### 🎬 **1. Hook & Mở đầu**).
- Xuống dòng & Khoảng cách: Sau khi viết xong tiêu đề đề mục, BẮT BUỘC phải xuống dòng và chèn 1 dòng trống trước khi bắt đầu nội dung.
- KHÔNG sử dụng cụm từ hoặc thẻ "ON SCREEN:" hay ghi chú kỹ thuật thừa mứa.

II. QUY TẮC DỊCH THUẬT VÀ TRÍCH XUẤT TEXT OVERLAY
- Dịch toàn bộ nội dung sang tiếng Việt văn phong tự nhiên. KHÔNG viết nối câu tiếng Anh ngay bên cạnh câu tiếng Việt.
- Định dạng Trích xuất: Với những từ khóa, thuật ngữ hoặc câu chốt muốn trích xuất cho Editor làm Text Overlay, BẮT BUỘC viết trong ngoặc kép theo chuẩn: “Nội dung hiển thị tiếng Việt :: Text tiếng Anh gốc” (Ví dụ: “Tăng trưởng đột phá :: Breakthrough growth”).
- Nếu kịch bản gốc là tiếng Việt hoặc không có text tiếng Anh tương ứng, chỉ cần viết dạng: “Nội dung nhấn mạnh”.
- Phân bổ Độ dài: Đoạn liệt kê/khái niệm dùng từ khóa ngắn (1-3 từ). Câu chốt/tóm tắt trích xuất trọn vẹn cả câu.

III. ĐỊNH DẠNG ĐẦU RA MẪU:

### 🎬 **1. Mở đầu ấn tượng**

Chào mừng các bạn đến với video hôm nay. Chúng ta sẽ cùng khám phá bí quyết “Tăng trưởng doanh thu :: Revenue growth” trong ngành sáng tạo nội dung.

### 🎬 **2. Nội dung chính**

Tiếp theo, hãy cùng tìm hiểu về quy trình “Tối ưu kịch bản :: Script optimization” để nâng cao chất lượng dựng phim.
"""

# --- CÔNG THỨC GIỮ NGUYÊN NGÔN NGỮ GỐC ---
FORMULA_ORIGINAL = """
CÔNG THỨC XỬ LÝ KỊCH BẢN VIDEO (GIỮ NGUYÊN NGÔN NGỮ GỐC)
Vai trò của bạn: Bạn là một Trợ lý Biên tập Video chuyên nghiệp. Nhiệm vụ của bạn là giữ nguyên ngôn ngữ gốc của kịch bản và trích xuất các đoạn Text Overlay/Graphic theo chuẩn Editor.

I. QUY TẮC PHÂN ĐOẠN & TRÌNH BÀY ĐỀ MỤC:
- Định dạng Đề mục: BẮT BUỘC trình bày dạng: ### 🎬 **X. [Tên Phân Đoạn]** (VD: ### 🎬 **1. Hook & Introduction**).
- Xuống dòng & Khoảng cách: Sau khi viết xong tiêu đề đề mục, BẮT BUỘC phải xuống dòng và chèn 1 dòng trống trước khi bắt đầu nội dung.
- KHÔNG sử dụng cụm từ hoặc thẻ "ON SCREEN:".

II. QUY TẮC TRÍCH XUẤT TEXT OVERLAY:
- Giữ nguyên ngôn ngữ gốc của kịch bản.
- Tất cả các từ khóa quan trọng, thuật ngữ, câu chốt trích xuất cho Editor hiển thị trên màn hình BẮT BUỘC phải nằm trong ngoặc kép dạng: “Text Overlay”.

III. ĐỊNH DẠNG ĐẦU RA MẪU:

### 🎬 **1. Hook & Introduction**

Welcome to today's video. We will explore “Breakthrough growth” in content creation.
"""


# ==========================================
# 2. HÀM CHUYỂN ĐỔI TEXT SANG HTML CLICK-TO-COPY & TOOLTIP
# ==========================================
def convert_quotes_to_copyable_html(text):
  custom_css = """
    <style>
    .editor-hl {
        color: #4F46E5 !important;
        font-weight: 600;
        border-bottom: 2px dashed #818CF8;
        cursor: pointer;
        position: relative;
        display: inline-block;
        padding: 0 4px;
        margin: 0 2px;
        border-radius: 4px;
        transition: all 0.2s ease;
        user-select: none;
    }
    .editor-hl:hover {
        background-color: #EEF2FF;
        color: #312E81 !important;
    }
    .editor-hl .hl-tooltip {
        visibility: hidden;
        opacity: 0;
        width: max-content;
        max-width: 280px;
        background-color: #0F172A;
        color: #F8FAFC;
        text-align: center;
        border-radius: 6px;
        padding: 6px 12px;
        position: absolute;
        z-index: 999;
        bottom: 125%;
        left: 50%;
        transform: translateX(-50%) translateY(4px);
        transition: opacity 0.2s ease, transform 0.2s ease;
        font-size: 0.82rem;
        font-weight: 500;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        pointer-events: none;
        line-height: 1.4;
        border: 1px solid #334155;
    }
    .editor-hl:hover .hl-tooltip {
        visibility: visible;
        opacity: 1;
        transform: translateX(-50%) translateY(0);
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
      copy_val = en_text.replace("'", "\\'").replace('"', "&quot;")
      tooltip_val = f"🇬🇧 {en_text} (Nhấp để copy)"
      display_text = vi_text
    else:
      copy_val = content.replace("'", "\\'").replace('"', "&quot;")
      tooltip_val = "📋 Nhấp để copy"
      display_text = content

    return f"""<span class="editor-hl" onclick="navigator.clipboard.writeText('{copy_val}'); const orig = this.style.color; this.style.color='#10B981'; this.style.borderBottomColor='#10B981'; setTimeout(() => {{ this.style.color=orig; this.style.borderBottomColor='#818CF8'; }}, 800);"><span class="hl-tooltip">{tooltip_val}</span>{display_text}</span>"""

  rendered_html = re.sub(pattern, replace_match, text)
  return custom_css + rendered_html


def clean_script_for_download(text):
  """Hàm làm sạch kịch bản để xuất file .txt"""
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
        f"Mã xác minh OTP để đặt lại mật khẩu cho tài khoản {receiver_email}"
        f" là: {otp}\n\n"
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

# QUẢN LÝ TRẠNG THÁI SESSION STATE (CHỐNG GỬI TRÙNG KHI CHUYỂN TAB)
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
  st.caption(
      "Công cụ phân tích, tối ưu kịch bản & trích xuất Text Overlay chuyên"
      " nghiệp cho Video Editor."
  )

  tab_login, tab_register, tab_forgot = st.tabs(
      ["🔑 Đăng Nhập", "📝 Đăng Ký", "❓ Quên Mật Khẩu"]
  )

  with tab_login:
    login_email = (
        st.text_input("Gmail đăng nhập:", key="login_email").strip().lower()
    )
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
    reg_email = (
        st.text_input("Nhập Gmail đăng ký:", key="reg_email").strip().lower()
    )
    reg_password = st.text_input("Tạo mật khẩu:", type="password", key="reg_pass")
    reg_confirm = st.text_input(
        "Nhập lại mật khẩu:", type="password", key="reg_conf"
    )

    if st.button("Tạo Tài Khoản", type="primary", use_container_width=True):
      if not reg_email or "@" not in reg_email:
        st.warning("Vui lòng nhập đúng định dạng Gmail!")
      elif len(reg_password) < 6:
        st.warning("Mật khẩu phải có ít nhất 6 ký tự!")
      elif reg_password != reg_confirm:
        st.error("Mật khẩu nhập lại không trùng khớp!")
      else:
        if register_user(reg_email, reg_password):
          st.success(
              "🎉 Đăng ký tài khoản thành công! Vui lòng chuyển sang tab **Đăng"
              " Nhập**."
          )
        else:
          st.error("Gmail này đã được đăng ký từ trước!")

  with tab_forgot:
    st.subheader("🔑 Khôi phục mật khẩu qua Mã OTP")
    forgot_email = (
        st.text_input("Nhập Gmail đã đăng ký:", key="forgot_email")
        .strip()
        .lower()
    )

    col_send, _ = st.columns([1, 1])
    with col_send:
      if st.button("📩 Gửi Mã OTP về Gmail"):
        if not forgot_email or "@" not in forgot_email:
          st.warning("Vui lòng nhập đúng địa chỉ Gmail!")
        else:
          otp_code = "".join(random.choices(string.digits, k=6))
          if save_otp(forgot_email, otp_code):
            if send_otp_email(forgot_email, otp_code):
              st.success(
                  f"✅ Mã OTP (6 chữ số) đã được gửi đến **{forgot_email}**."
                  " Vui lòng kiểm tra hộp thư!"
              )
            else:
              st.error(
                  "Không thể gửi email OTP. Vui lòng kiểm tra cấu hình Gmail"
                  " trong Secrets."
              )
          else:
            st.error(
                "Gmail này chưa tồn tại trong hệ thống! Vui lòng đăng ký trước."
            )

    st.markdown("---")
    otp_input = st.text_input("Nhập Mã OTP (6 chữ số):", key="otp_in").strip()
    new_pass_input = st.text_input(
        "Mật khẩu mới:", type="password", key="new_p_in"
    )
    new_pass_confirm = st.text_input(
        "Nhập lại mật khẩu mới:", type="password", key="new_p_conf"
    )

    if st.button(
        "🔄 Đặt Lại Mật Khẩu", type="primary", use_container_width=True
    ):
      if not otp_input or not new_pass_input:
        st.warning("Vui lòng nhập đầy đủ Mã OTP và Mật khẩu mới!")
      elif len(new_pass_input) < 6:
        st.warning("Mật khẩu mới phải có ít nhất 6 ký tự!")
      elif new_pass_input != new_pass_confirm:
        st.error("Mật khẩu mới nhập lại không trùng khớp!")
      else:
        if verify_otp_and_update_password(
            forgot_email, otp_input, new_pass_input
        ):
          st.success(
              "🎉 Đổi mật khẩu thành công! Bạn có thể đăng nhập ngay bằng mật"
              " khẩu mới."
          )
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

    # Thống kê ký tự thời gian thực
    char_count = len(script_input)
    word_count = len(script_input.split())
    est_minutes = round(word_count / 160, 1) if word_count > 0 else 0
    st.caption(
        f"📊 **Dung lượng kịch bản:** {char_count:,} ký tự | {word_count:,} từ |"
        f" **Ước tính thời lượng video:** ~{est_minutes} phút"
    )

    # Nút bấm tự động khóa khi đang xử lý để chống gửi trùng
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

        # Mốc thời gian dự kiến theo độ dài
        if char_count < 1000:
          est_sec, est_desc = 60, "~1 phút"
        elif char_count < 2000:
          est_sec, est_desc = 120, "~2 phút"
        elif char_count < 3000:
          est_sec, est_desc = 180, "~3 phút"
        else:
          est_sec, est_desc = 240, "~4 phút"

        status_box = st.empty()
        progress_bar = st.progress(0)

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

        statuses = [
            "1/3 Đang đọc và phân tích cấu trúc kịch bản...",
            "2/3 Đang trích xuất Text Overlay & tạo điểm nhấn...",
            "3/3 Đang hoàn thiện định dạng tối ưu cho Editor...",
        ]

        # Animation tiến trình mượt mà
        for i in range(1, 85):
          time.sleep(est_sec / 100)
          progress_bar.progress(i)
          msg = (
              statuses[0]
              if i < 30
              else (statuses[1] if i < 65 else statuses[2])
          )
          status_box.markdown(
              f"{spinner_style}<span style='display:inline-flex;"
              " align-items:center;'><b><span"
              f" class='loading-spinner'></span>⏳ {msg}</b> (Dự kiến:"
              f" {est_desc})</span>",
              unsafe_allow_html=True,
          )

        # Gọi Gemini API Model 3.6-flash
        genai.configure(api_key=GEMINI_API_KEY)
        safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: (
                HarmBlockThreshold.BLOCK_NONE
            ),
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: (
                HarmBlockThreshold.BLOCK_NONE
            ),
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: (
                HarmBlockThreshold.BLOCK_NONE
            ),
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: (
                HarmBlockThreshold.BLOCK_NONE
            ),
        }

        model = genai.GenerativeModel(
            model_name="gemini-3.6-flash", safety_settings=safety_settings
        )

        prompt_payload = (
            f"{selected_instruction}\n\n--- KỊCH BẢN CẦN XỬ LÝ"
            f" ---\n{script_input}"
        )
        response = model.generate_content(prompt_payload)

        progress_bar.progress(100)
        status_box.empty()
        progress_bar.empty()

        # Lưu kết quả vào Session State và mở khóa
        st.session_state.final_result = response.text
        st.session_state.is_processing = False
        st.rerun()

      except Exception as e:
        status_box.empty()
        progress_bar.empty()
        st.session_state.is_processing = False
        st.error("❌ Đã xảy ra lỗi trong quá trình xử lý:")
        st.exception(e)

  # --- HIỂN THỊ KẾT QUẢ TỪ SESSION STATE (KHÔNG CẦN GỌI LẠI API KHI CHUYỂN TAB) ---
  if st.session_state.final_result:
    st.success("✨ Kịch bản của bạn đã sẵn sàng!")

    col_info, col_download = st.columns([3, 1])
    with col_info:
      st.caption(
          "💡 **Mẹo:** Rê chuột vào các <span style='color:#4F46E5;"
          " font-weight:bold;'>từ khóa đổi màu</span> để xem bản dịch. **Nhấp"
          " chuột 1 lần** để tự động Copy!",
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

    html_output = convert_quotes_to_copyable_html(st.session_state.final_result)
    st.markdown(html_output, unsafe_allow_html=True)
