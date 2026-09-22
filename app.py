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
# 2. KHỞI TẠO CẤU HÌNH GIAO DIỆN & GLOBAL CSS (TẠO TRỤC GIỮA 900PX & VIDEO NỀN)
# ==========================================
st.set_page_config(page_title="Trợ Lý Kịch Bản Video", page_icon="🎬", layout="centered")

CUSTOM_CSS = """
<style>
/* Video Nền Chạy Ngầm */
.bg-video-container {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    z-index: -2;
}
.bg-video-container video {
    min-width: 100%;
    min-height: 100%;
    width: auto;
    height: auto;
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    object-fit: cover;
    opacity: 0.35;
}
.bg-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(11, 15, 25, 0.78);
    z-index: -1;
}

/* Căn giữa & Thu hẹp trục hiển thị 900px */
.block-container {
    max-width: 900px !important;
    padding-top: 1.5rem !important;
    margin: 0 auto !important;
}

/* Ẩn Sidebar & Header mặc định */
[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Giao diện Nền Tối Tinh Tế */
.stApp {
    background-color: transparent !important;
    color: #F1F5F9 !important;
}

.stTextArea textarea, .stTextInput input {
    background-color: rgba(15, 23, 42, 0.85) !important;
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

/* TÓM TẮT TỔNG QUAN CARD */
.script-summary-card {
    background: rgba(30, 41, 59, 0.75);
    border-left: 5px solid #6366F1;
    border-radius: 8px;
    padding: 18px 22px;
    margin-bottom: 25px;
    backdrop-filter: blur(8px);
}
.script-summary-title { font-size: 1.1rem; font-weight: 700; color: #A5B4FC; margin-bottom: 10px; }
.script-summary-body { font-size: 0.95rem; line-height: 1.6; color: #E2E8F0; }

/* B-ROLL TAGS (LIỀN MẠCH NỘI DÒNG) */
.broll-wrapper { 
    margin-top: 6px; 
    margin-bottom: 16px; 
    display: inline-flex; 
    flex-wrap: wrap; 
    gap: 6px; 
    align-items: center; 
}
.broll-label { font-size: 0.78rem; color: #94A3B8; font-weight: 600; margin-right: 4px; }
.broll-tag {
    background-color: rgba(255,255,255,0.08) !important; color: #CBD5E1 !important;
    padding: 2px 8px !important; border-radius: 4px !important; font-size: 0.78rem !important;
    text-decoration: none !important; border: 1px solid rgba(255,255,255,0.12) !important;
    transition: all 0.2s ease;
}
.broll-tag:hover { background-color: rgba(255,255,255,0.2) !important; color: #FFFFFF !important; }

/* TEXT OVERLAY HIGHLIGHT & TOOLTIP BRIDGE */
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
/* Cầu nối ẩn giúp di chuyển chuột không bị mất Tooltip */
.editor-hl .hl-tooltip::after {
    content: "";
    position: absolute;
    top: 100%;
    left: 0;
    width: 100%;
    height: 15px;
}
.editor-hl:hover .hl-tooltip { visibility: visible; opacity: 1; transform: translateX(-50%) translateY(-10px); }
.editor-hl.copied { background-color: rgba(16, 185, 129, 0.3) !important; color: #34D399 !important; border-bottom-color: #34D399 !important; }

details summary::-webkit-details-marker { display: none; }
details summary { list-style: none; }
</style>

<!-- Chèn HTML Video Nền -->
<div class="bg-video-container">
    <video autoplay muted loop playsinline>
        <source src="https://raw.githubusercontent.com/minh66993318-collab/editor-ai-tool/main/bg-video.mp4" type="video/mp4">
    </video>
</div>
<div class="bg-overlay"></div>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ==========================================
# 3. HÀM XỬ LÝ HTML & JAVASCRIPT COPY MULTI-CLICK
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
            return f'<span class="editor-hl copy-trigger" data-copytext="{vi_text}"><span class="hl-tooltip"><span class="hl-tooltip-text">{orig_tooltip}</span></span>{vi_text}</span>'
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

    # Chuyển đổi Markdown Header ### thành HTML h3 để tránh vỡ giao diện Streamlit
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


def clean_script_for_download(text):
    cleaned = re.sub(r'(?:###\s*📌\s*\*\*Tóm tắt tổng quan\*\*\s*\n+|###\s*📌\s*Tóm tắt tổng quan\s*\n+|###\s*📌\s*\*\*Overview Summary\*\*\s*\n+).*?(?=\n\s*###\s*🎬|$)', '', text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'\[BROLL:\s*.*?\]', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'^\s*---\s*', '', cleaned.strip())
    cleaned = re.sub(r'["“]([^"”]+)::([^"”]+)["”]', r"\1 (\2)", cleaned)
    cleaned = re.sub(r'["“]([^"”]+)["”]', r"\1", cleaned)
    return cleaned.strip()

# ==========================================
# 4. DATABASE & BẢO MẬT (LƯU DUY NHẤT 1 KỊCH BẢN GẦN NHẤT)
# ==========================================
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users (email TEXT PRIMARY KEY, password_hash TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS script_history (email TEXT PRIMARY KEY, script_input TEXT, result_text TEXT, timestamp TEXT)")
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

def save_latest_history(email, script_input, result_text):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    timestamp = time.strftime('%d/%m/%Y %H:%M')
    c.execute("INSERT OR REPLACE INTO script_history (email, script_input, result_text, timestamp) VALUES (?, ?, ?, ?)", (email, script_input, result_text, timestamp))
    conn.commit(); conn.close()

def get_latest_history(email):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT script_input, result_text, timestamp FROM script_history WHERE email=?", (email,))
    row = c.fetchone()
    conn.close()
    return row

# ==========================================
# 5. GIAO DIỆN STREAMLIT CHÍNH (KHÔNG SIDEBAR)
# ==========================================
init_db()

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "final_result" not in st.session_state: st.session_state.final_result = None
if "is_processing" not in st.session_state: st.session_state.is_processing = False

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
    # --- THANH ĐIỀU HƯỚNG TRÊN CÙNG ---
    col_user, col_logout = st.columns([4, 1])
    with col_user:
        st.write(f"👤 Tài khoản: `{st.session_state.user_email}`")
    with col_logout:
        if st.button("🚪 Đăng xuất", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.final_result = None
            st.rerun()

    st.markdown("<h1 class='main-title'>🎬 TRỢ LÝ KỊCH BẢN VIDEO</h1>", unsafe_allow_html=True)

    # --- KHU VỰC LỊCH SỬ GẦN NHẤT (ĐẶT Ở ĐẦU TRANG) ---
    latest_hist = get_latest_history(st.session_state.user_email)
    if latest_hist:
        hist_col1, hist_col2 = st.columns([3, 1])
        with hist_col1:
            st.caption(f"📜 **Kịch bản gần nhất gần đây:** `{latest_hist[2][:30].replace('\n', ' ')}...` (Lúc {latest_hist[2]})")
        with hist_col2:
            if st.button("🔄 Tải lại kịch bản gần nhất", use_container_width=True):
                st.session_state.final_result = latest_hist[1]
                st.rerun()

    st.markdown("---")

    mode_option = st.radio("🌐 Chọn chế độ xử lý:", ["Dịch thuật sang Tiếng Việt", "Giữ nguyên ngôn ngữ gốc"], horizontal=True)

    with st.form("script_analysis_form"):
        script_input = st.text_area("Dán kịch bản video của bạn vào đây:", height=200, placeholder="Paste kịch bản gốc vào đây...")
        
        # Thống kê dung lượng kịch bản bên dưới
        char_count = len(script_input)
        word_count = len(script_input.split())
        est_minutes = round(word_count / 160, 1) if word_count > 0 else 0
        st.caption(f"📊 **Dung lượng kịch bản:** {char_count:,} ký tự | {word_count:,} từ | **Ước tính thời lượng video:** ~{est_minutes} phút")

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
                save_latest_history(st.session_state.user_email, script_input, response.text)
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

    # --- HIỂN THỊ KẾT QUẢ & NÚT XUẤT FILE .TXT ---
    if st.session_state.final_result:
        st.markdown("---")
        col_info, col_download = st.columns([3, 1])
        with col_info:
            st.caption("💡 **Mẹo:** Rê chuột vào các từ khóa để xem bản dịch. **Nhấp chuột 1 lần** để tự động Copy!")
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
        if summary_html: 
            st.markdown(summary_html, unsafe_allow_html=True)
        st.markdown(main_content_html, unsafe_allow_html=True)
        inject_copy_javascript()
