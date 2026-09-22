import hashlib
import html
import random
import re
import smtplib
import sqlite3
import string
import time
import urllib.parse
from email.message import EmailMessage

import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory
import streamlit as st
import streamlit.components.v1 as components

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG & API KEY
# ==========================================
RAW_KEY = st.secrets.get("GEMINI_API_KEY", "")
GEMINI_API_KEY = str(RAW_KEY).strip(" \"'\t\r\n")

SENDER_GMAIL = str(st.secrets.get("SENDER_GMAIL", "")).strip(" \"'\t\r\n")
SENDER_APP_PASSWORD = str(st.secrets.get("SENDER_APP_PASSWORD", "")).strip(" \"'\t\r\n")

# --- CÔNG THỨC DỊCH TIẾNG VIỆT (TÍCH HỢP BẢN DỊCH ẨN) ---
FORMULA_VIETNAMESE = """
CÔNG THỨC XỬ LÝ KỊCH BẢN VIDEO (TIẾNG VIỆT)
Vai trò của bạn: Bạn là một Trợ lý Biên tập Video chuyên nghiệp. 

I. QUY TẮC TÓM TẮT & PHÂN ĐOẠN
- Phần Tóm tắt tổng quan: Ở ngay đầu kết quả, BẮT BUỘC viết một đoạn tóm tắt tổng thể dạng gạch đầu dòng dưới tiêu đề: ### 📌 **Tóm tắt tổng quan**
- Định dạng Đề mục: BẮT BUỘC trình bày dạng: ### 🎬 **X. [Tên Phân Đoạn]**
- B-roll Gợi ý: Ở cuối mỗi phân đoạn, BẮT BUỘC đính kèm thẻ: `[BROLL: keyword1 | keyword2 | keyword3 | keyword4 | keyword5]` (5 từ khóa tiếng Anh).

II. QUY TẮC DỊCH THUẬT & TRÍCH XUẤT TEXT OVERLAY & BẢN SONG NGỮ ẨN
- Dịch nội dung chính sang tiếng Việt văn phong tự nhiên.
- Định dạng Text Overlay: Từ khóa/câu chốt muốn hiển thị BẮT BUỘC viết dạng: “Nội dung tiếng Việt :: Text tiếng Anh gốc”.
- NGAY BÊN DƯỚI nội dung tiếng Việt của mỗi phân đoạn (trước phần B-roll), bạn BẮT BUỘC tạo một phần ẩn chứa bản gốc tiếng Anh của phân đoạn đó theo ĐÚNG định dạng HTML sau:
<details style="margin-top: 10px; margin-bottom: 15px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px; cursor: pointer;">
<summary style="font-weight: 600; color: #94A3B8;">➕ Xem bản gốc tiếng Anh (Original Script)</summary>
<p style="margin-top: 10px; color: #CBD5E1;">[Chèn toàn bộ nội dung tiếng Anh của phân đoạn này vào đây]</p>
</details>
"""

# --- CÔNG THỨC GIỮ NGUYÊN NGÔN NGỮ GỐC (TÍCH HỢP BẢN DỊCH ẨN) ---
FORMULA_ORIGINAL = """
CÔNG THỨC XỬ LÝ KỊCH BẢN VIDEO (GIỮ NGUYÊN NGÔN NGỮ GỐC)
Vai trò của bạn: Bạn là một Trợ lý Biên tập Video chuyên nghiệp. 

I. QUY TẮC TÓM TẮT & PHÂN ĐOẠN:
- Overview Summary: At the top, include a summary under: ### 📌 **Overview Summary**
- Section Headings format: ### 🎬 **X. [Section Name]**
- B-roll Gợi ý: At the end of each section, include: `[BROLL: keyword1 | keyword2 | keyword3 | keyword4 | keyword5]`

II. QUY TẮC TRÍCH XUẤT TEXT OVERLAY & BẢN SONG NGỮ ẨN:
- Giữ nguyên ngôn ngữ gốc của kịch bản làm nội dung chính.
- Từ khóa hiển thị màn hình nằm trong ngoặc kép dạng: “Text Overlay”.
- NGAY BÊN DƯỚI nội dung gốc của mỗi phân đoạn (trước phần B-roll), bạn BẮT BUỘC tạo một phần ẩn chứa bản dịch tiếng Việt của phân đoạn đó theo ĐÚNG định dạng HTML sau:
<details style="margin-top: 10px; margin-bottom: 15px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px; cursor: pointer;">
<summary style="font-weight: 600; color: #94A3B8;">➕ Xem bản dịch tiếng Việt</summary>
<p style="margin-top: 10px; color: #CBD5E1;">[Chèn toàn bộ nội dung dịch tiếng Việt của phân đoạn này vào đây]</p>
</details>
"""

# ==========================================
# 2. KHỞI TẠO CẤU HÌNH GIAO DIỆN & GLOBAL CSS
# ==========================================
st.set_page_config(page_title="Trợ Lý Kịch Bản Video", page_icon="🎬", layout="centered")

CUSTOM_CSS = """
<style>
/* Căn giữa & Thu hẹp trục hiển thị */
.block-container {
    max-width: 900px !important;
    padding-top: 2rem !important;
    margin: 0 auto !important;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.stApp {
    background-color: #0B0F19 !important;
    color: #F1F5F9 !important;
}

.stTextArea textarea, .stTextInput input {
    background-color: rgba(15, 23, 42, 0.9) !important;
    color: #F8FAFC !important;
    border: 1px solid rgba(129, 140, 248, 0.3) !important;
    border-radius: 8px !important;
}

.main-title {
    font-size: 2.25rem;
    font-weight: 800;
    color: #F8FAFC;
    text-align: center;
    margin-bottom: 4px;
    text-transform: uppercase;
}

/* SUMMARY CARD */
.script-summary-card {
    background: rgba(30, 41, 59, 0.6);
    border-left: 5px solid #6366F1;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 30px;
}
.script-summary-title { font-size: 1.15rem; font-weight: 700; color: #A5B4FC; margin-bottom: 12px; }
.script-summary-body { font-size: 0.95rem; line-height: 1.7; color: #E2E8F0; }

/* B-ROLL TAGS */
.broll-wrapper { margin-top: 6px; margin-bottom: 20px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.broll-label { font-size: 0.78rem; color: #94A3B8; font-weight: 600; margin-right: 4px; }
.broll-tag {
    background-color: rgba(255,255,255,0.08) !important; color: #CBD5E1 !important;
    padding: 2px 8px !important; border-radius: 4px !important; font-size: 0.78rem !important;
    text-decoration: none !important; border: 1px solid rgba(255,255,255,0.12) !important;
}

/* TEXT OVERLAY HIGHLIGHT */
.editor-hl {
    color: #818CF8 !important; font-weight: 600; border-bottom: 2px dashed #818CF8;
    cursor: pointer; position: relative; display: inline-block; padding: 2px 6px; margin: 0 2px;
    user-select: text;
}
.editor-hl:hover { background-color: rgba(99, 102, 241, 0.2); }
.editor-hl .hl-tooltip {
    visibility: hidden; opacity: 0; width: max-content; max-width: 320px;
    background-color: #0F172A; color: #F8FAFC; text-align: center; border-radius: 8px;
    padding: 8px 12px; position: absolute; z-index: 99999; bottom: 100%; left: 50%;
    transform: translateX(-50%) translateY(-8px); font-size: 0.83rem;
    pointer-events: auto; white-space: normal;
}
.editor-hl:hover .hl-tooltip { visibility: visible; opacity: 1; transform: translateX(-50%) translateY(-10px); }
.editor-hl.copied { background-color: rgba(16, 185, 129, 0.3) !important; color: #34D399 !important; border-bottom-color: #34D399 !important; }

details summary::-webkit-details-marker { display: none; }
details summary { list-style: none; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ==========================================
# 3. HÀM XỬ LÝ HTML & JAVASCRIPT COPY
# ==========================================
def parse_and_render_script(text):
    summary_regex = r'(?:###\s*📌\s*\*\*Tóm tắt tổng quan\*\*\s*\n+|###\s*📌\s*Tóm tắt tổng quan\s*\n+|###\s*📌\s*\*\*Overview Summary\*\*\s*\n+)(.*?)(?=\n\s*---\s*|\n\s*###\s*🎬|$)'
    match = re.search(summary_regex, text, re.DOTALL | re.IGNORECASE)
    summary_card_html, main_content = "", text

    if match:
        raw_summary = match.group(1).strip()
        lines = raw_summary.split('\n')
        parsed_lines = []
        for l in lines:
            stripped = l.strip()
            if not stripped:
                continue
            if stripped.startswith(('-', '*')):
                content_clean = re.sub(r'^[-*]\s*', '', stripped)
                escaped_text = html.escape(content_clean)
                bolded = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', escaped_text)
                parsed_lines.append(f"<li>{bolded}</li>")
            else:
                escaped_text = html.escape(stripped)
                bolded = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', escaped_text)
                parsed_lines.append(f"<p style='margin-bottom: 6px;'>{bolded}</p>")

        body_content = "".join(parsed_lines)
        if "<li>" in body_content:
            body_content = f"<ul>{body_content}</ul>"

        summary_card_html = f'<div class="script-summary-card"><div class="script-summary-title">📌 Tóm tắt tổng quan</div><div class="script-summary-body">{body_content}</div></div>'
        main_content = re.sub(summary_regex, '', text, flags=re.DOTALL | re.IGNORECASE)
        main_content = re.sub(r'^\s*---\s*', '', main_content.strip())

    # Replace quotes for Text Overlay (Safe HTML Escaping)
    def replace_match(m):
        content = m.group(1).strip()
        if "::" in content:
            parts = content.split("::", 1)
            vi_text = html.escape(parts[0].strip())
            en_text = html.escape(parts[1].strip())
            orig_tooltip = f"{en_text} (Nhấp để copy)"
            return f'<span class="editor-hl copy-trigger" data-copytext="{en_text}"><span class="hl-tooltip"><span class="hl-tooltip-text">{orig_tooltip}</span></span>{vi_text}</span>'
        else:
            clean_text = html.escape(content)
            return f'<span class="editor-hl copy-trigger" data-copytext="{clean_text}"><span class="hl-tooltip"><span class="hl-tooltip-text">Nhấp để copy</span></span>{clean_text}</span>'

    parts = re.split(r'(<[^>]+>)', main_content)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r'["“]([^"”<]+)["”]', replace_match, parts[i])
    main_content = "".join(parts)

    # Render B-roll tags
    def render_broll(m):
        kws = re.split(r'[|,]', m.group(1))
        tags = []
        for kw in kws:
            clean_kw = kw.strip()
            if clean_kw:
                encoded_kw = urllib.parse.quote(clean_kw)
                escaped_kw = html.escape(clean_kw)
                tags.append(f'<a href="https://www.pexels.com/vi-vn/tim-kiem/videos/{encoded_kw}/" target="_blank" class="broll-tag">{escaped_kw}</a>')
        return f'<div class="broll-wrapper"><span class="broll-label">B-roll:</span>{"".join(tags)}</div>'

    main_content = re.sub(r'\[BROLL:\s*(.*?)\]', render_broll, main_content, flags=re.IGNORECASE)

    # Convert markdown headers (###) to explicit HTML tags to avoid Markdown parser breaking
    main_content = re.sub(r'^###\s*🎬\s*\*\*(.*?)\*\*', r'<h3 style="color:#A5B4FC; font-weight:700; margin-top:24px; margin-bottom:12px;">🎬 \1</h3>', main_content, flags=re.MULTILINE)
    main_content = re.sub(r'^###\s*(.*?)$', r'<h3 style="color:#A5B4FC; font-weight:700; margin-top:24px; margin-bottom:12px;">\1</h3>', main_content, flags=re.MULTILINE)

    return summary_card_html, main_content


def inject_copy_javascript():
    js_script = """
    <script>
    document.addEventListener("DOMContentLoaded", function() {
        const parentDoc = window.parent.document;
        if (!parentDoc.body.dataset.copyInjected) {
            parentDoc.body.dataset.copyInjected = "true";
            parentDoc.body.addEventListener('click', function(e) {
                const el = e.target.closest('.copy-trigger');
                if (el) {
                    e.preventDefault();
                    e.stopPropagation();
                    const textToCopy = el.getAttribute('data-copytext');
                    const tip = el.querySelector('.hl-tooltip-text');
                    
                    function handleSuccess() {
                        if (tip) {
                            if (!tip.hasAttribute('data-orig')) { tip.setAttribute('data-orig', tip.innerText); }
                            tip.innerText = 'Đã copy!';
                            el.classList.remove('copied');
                            void el.offsetWidth; 
                            el.classList.add('copied');
                            setTimeout(() => { tip.innerText = tip.getAttribute('data-orig'); el.classList.remove('copied'); }, 1200);
                        }
                    }
                    
                    if (parentDoc.defaultView && parentDoc.defaultView.navigator.clipboard) {
                        parentDoc.defaultView.navigator.clipboard.writeText(textToCopy).then(handleSuccess).catch(() => {
                            fallbackCopy(parentDoc, textToCopy); handleSuccess();
                        });
                    } else {
                        fallbackCopy(parentDoc, textToCopy); handleSuccess();
                    }
                }
            });
        }
        
        function fallbackCopy(doc, text) {
            const ta = doc.createElement("textarea");
            ta.value = text; ta.style.position = "fixed"; ta.style.opacity = 0;
            doc.body.appendChild(ta); ta.focus(); ta.select();
            try { doc.execCommand('copy'); } catch(err) {}
            doc.body.removeChild(ta);
        }
    });
    </script>
    """
    components.html(js_script, height=0, width=0)

# ==========================================
# 4. DATABASE & BẢO MẬT
# ==========================================
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password_hash TEXT, reset_otp TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS script_history (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, script_input TEXT, result_text TEXT, timestamp TEXT)")
    conn.commit()
    conn.close()

def hash_password(password): return hashlib.sha256(password.encode()).hexdigest()

def register_user(email, password):
    try:
        conn = sqlite3.connect("users.db")
        c = conn.cursor()
        c.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, hash_password(password)))
        conn.commit(); conn.close()
        return True
    except sqlite3.IntegrityError: return False

def verify_user(email, password):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE email=?", (email,))
    result = c.fetchone()
    conn.close()
    return result and result[0] == hash_password(password)

def save_script_history(email, script_input, result_text):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    timestamp = time.strftime('%d/%m/%Y %H:%M')
    c.execute("INSERT INTO script_history (email, script_input, result_text, timestamp) VALUES (?, ?, ?, ?)", (email, script_input, result_text, timestamp))
    conn.commit(); conn.close()

def get_user_history(email, limit=5):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT id, script_input, result_text, timestamp FROM script_history WHERE email=? ORDER BY id DESC LIMIT ?", (email, limit))
    rows = c.fetchall()
    conn.close()
    return rows

def update_password(email, new_password):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("UPDATE users SET password_hash=? WHERE email=?", (hash_password(new_password), email))
    conn.commit(); conn.close()

# ==========================================
# 5. GIAO DIỆN CHÍNH
# ==========================================
init_db()

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "final_result" not in st.session_state: st.session_state.final_result = None
if "is_processing" not in st.session_state: st.session_state.is_processing = False

if not GEMINI_API_KEY:
    st.warning("⚠️ Chưa phát hiện GEMINI_API_KEY trong cấu hình Streamlit Secrets!")

if not st.session_state.logged_in:
    st.markdown("<h1 class='main-title'>TRỢ LÝ KỊCH BẢN VIDEO</h1>", unsafe_allow_html=True)
    
    tab_login, tab_register = st.tabs(["🔑 Đăng Nhập", "📝 Đăng Ký"])

    with tab_login:
        login_email = st.text_input("Gmail đăng nhập:").strip().lower()
        login_password = st.text_input("Mật khẩu:", type="password")
        if st.button("Đăng Nhập", type="primary", use_container_width=True):
            if verify_user(login_email, login_password):
                st.session_state.logged_in = True; st.session_state.user_email = login_email; st.rerun()
            else: st.error("Gmail hoặc Mật khẩu không chính xác!")

    with tab_register:
        reg_email = st.text_input("Nhập Gmail đăng ký:").strip().lower()
        reg_password = st.text_input("Tạo mật khẩu (≥ 6 ký tự):", type="password", key="r1")
        if st.button("Tạo Tài Khoản", type="primary", use_container_width=True):
            if not reg_email or "@" not in reg_email:
                st.warning("Vui lòng nhập email đúng định dạng!")
            elif len(reg_password) < 6:
                st.warning("Mật khẩu phải chứa ít nhất 6 ký tự!")
            elif register_user(reg_email, reg_password):
                st.success("🎉 Đăng ký thành công! Vui lòng chuyển sang tab **Đăng Nhập**.")
            else:
                st.error("Gmail này đã được đăng ký!")

else:
    # --- SIDEBAR (Lịch sử & Cài đặt) ---
    with st.sidebar:
        st.write(f"👤 **Tài khoản:** `{st.session_state.user_email}`")
        st.markdown("---")
        
        # Danh sách Lịch sử đa bản ghi (Nâng cấp)
        st.subheader("📜 Lịch sử phân tích")
        history_items = get_user_history(st.session_state.user_email, limit=5)
        if history_items:
            hist_options = {f"{item[3]} - {item[1][:20].replace('\n', ' ')}...": item[2] for item in history_items}
            selected_label = st.selectbox("Chọn bản ghi cũ:", list(hist_options.keys()))
            if st.button("🔄 Tải lại kịch bản này", use_container_width=True):
                st.session_state.final_result = hist_options[selected_label]
                st.rerun()
        else:
            st.caption("Chưa có lịch sử phân tích.")
            
        st.markdown("---")
        with st.expander("🔑 Đổi mật khẩu"):
            new_pass = st.text_input("Mật khẩu mới:", type="password")
            confirm_pass = st.text_input("Xác nhận:", type="password")
            if st.button("Lưu mật khẩu"):
                if len(new_pass) >= 6 and new_pass == confirm_pass:
                    update_password(st.session_state.user_email, new_pass)
                    st.success("✅ Đã cập nhật mật khẩu!")
                else:
                    st.error("Mật khẩu không trùng khớp hoặc dưới 6 ký tự!")

        if st.button("🚪 Đăng Xuất", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.final_result = None
            st.rerun()

    # --- NỘI DUNG CHÍNH ---
    st.markdown("<h1 class='main-title'>🎬 TRỢ LÝ KỊCH BẢN VIDEO</h1>", unsafe_allow_html=True)
    
    mode_option = st.radio("🌐 Chọn chế độ xử lý:", ["Dịch thuật sang Tiếng Việt", "Giữ nguyên ngôn ngữ gốc"], horizontal=True)

    with st.form("script_analysis_form"):
        script_input = st.text_area("Dán kịch bản video của bạn vào đây:", height=220, placeholder="Paste kịch bản gốc vào đây...")
        submit_btn = st.form_submit_button("✨ Tối Ưu Kịch Bản", type="primary", use_container_width=True, disabled=st.session_state.is_processing)

    if submit_btn and script_input:
        if not GEMINI_API_KEY:
            st.error("❌ Chưa cấu hình GEMINI_API_KEY trong Secrets!")
        else:
            st.session_state.is_processing = True
            status_box = st.info("⏳ Đang kết nối máy chủ & xử lý kịch bản...")
            
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                safety_settings = {
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                }
                model = genai.GenerativeModel("gemini-3.6-flash", safety_settings=safety_settings)
                instruction = FORMULA_VIETNAMESE if "Tiếng Việt" in mode_option else FORMULA_ORIGINAL
                
                response = model.generate_content(f"{instruction}\n\n--- KỊCH BẢN CẦN XỬ LÝ ---\n{script_input}")
                
                st.session_state.final_result = response.text
                save_script_history(st.session_state.user_email, script_input, response.text)
                st.session_state.is_processing = False
                st.rerun()
                
            except Exception as e:
                status_box.empty()
                st.session_state.is_processing = False
                err_msg = str(e)
                if "429" in err_msg or "ResourceExhausted" in err_msg:
                    st.warning("⏳ API đang bận do chạm hạn mức request. Vui lòng thử lại sau 15-30 giây!")
                else:
                    st.error(f"❌ Lỗi xử lý: {err_msg}")

    # --- HIỂN THỊ KẾT QUẢ ---
    if st.session_state.final_result:
        summary_html, main_content_html = parse_and_render_script(st.session_state.final_result)
        if summary_html: 
            st.markdown(summary_html, unsafe_allow_html=True)
        st.markdown(main_content_html, unsafe_allow_html=True)
        inject_copy_javascript()
