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

# ĐÃ XÓA PHẦN HTML <details> KHỎI PROMPT ĐỂ TRÁNH LỖI VỠ GIAO DIỆN TEXT HIGHLIGHT
FORMULA_VIETNAMESE = """
CÔNG THỨC XỬ LÝ KỊCH BẢN VIDEO (TIẾNG VIỆT)
Vai trò của bạn: Bạn là một Trợ lý Biên tập Video chuyên nghiệp. 

I. QUY TẮC TÓM TẮT & PHÂN ĐOẠN
- Phần Tóm tắt tổng quan: Ở ngay đầu kết quả, BẮT BUỘC viết một đoạn tóm tắt tổng thể dạng gạch đầu dòng dưới tiêu đề: ### 📌 **Tóm tắt tổng quan**
- Định dạng Đề mục: BẮT BUỘC trình bày dạng: ### 🎬 **X. [Tên Phân Đoạn]**
- B-roll Gợi ý: Ở cuối mỗi phân đoạn, BẮT BUỘC đính kèm thẻ: `[BROLL: keyword1 | keyword2 | keyword3 | keyword4 | keyword5]` (5 từ khóa tiếng Anh).

II. QUY TẮC DỊCH THUẬT & TRÍCH XUẤT TEXT OVERLAY
- Dịch nội dung chính sang tiếng Việt văn phong tự nhiên.
- Định dạng Text Overlay: Từ khóa/câu chốt muốn hiển thị BẮT BUỘC viết dạng: “Nội dung tiếng Việt :: Text tiếng Anh gốc”.
"""

FORMULA_ORIGINAL = """
CÔNG THỨC XỬ LÝ KỊCH BẢN VIDEO (GIỮ NGUYÊN NGÔN NGỮ GỐC)
Vai trò của bạn: Bạn là một Trợ lý Biên tập Video chuyên nghiệp. 

I. QUY TẮC TÓM TẮT & PHÂN ĐOẠN:
- Overview Summary: At the top, include a summary under: ### 📌 **Overview Summary**
- Section Headings format: ### 🎬 **X. [Section Name]**
- B-roll Gợi ý: At the end of each section, include: `[BROLL: keyword1 | keyword2 | keyword3 | keyword4 | keyword5]`

II. QUY TẮC TRÍCH XUẤT TEXT OVERLAY:
- Giữ nguyên ngôn ngữ gốc của kịch bản làm nội dung chính.
- Từ khóa hiển thị màn hình nằm trong ngoặc kép dạng: “Text Overlay”.
"""

# ==========================================
# 2. KHỞI TẠO CẤU HÌNH GIAO DIỆN & GLOBAL CSS 
# ==========================================
st.set_page_config(page_title="Trợ Lý Kịch Bản Video", page_icon="🎬", layout="wide")

CUSTOM_CSS = """
<style>
.stApp { background: transparent !important; color: #F1F5F9 !important; }

/* KHUNG CHỨA VIDEO BACKGROUND */
.bg-video-container {
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    overflow: hidden; z-index: -999; pointer-events: none;
}
.bg-video-container video {
    width: 100%; height: 100%; object-fit: cover; opacity: 0.8;
}
.bg-overlay {
    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
    background: linear-gradient(135deg, rgba(5, 5, 8, 0.25) 0%, rgba(12, 16, 23, 0.4) 100%);
    z-index: -998; pointer-events: none;
}

/* ẨN HEADER/FOOTER MẶC ĐỊNH */
#MainMenu, footer, header, [data-testid="stHeader"] { visibility: hidden; display: none !important; }

/* TIÊU ĐỀ LIGHT SWEEP */
@keyframes lightSweepAnim {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
.light-sweep-title {
    font-size: 2.25rem; font-weight: 800; letter-spacing: -0.5px;
    background: linear-gradient(90deg, #e2e8f0 0%, #ffffff 30%, #3b82f6 50%, #ffffff 70%, #e2e8f0 100%);
    background-size: 200% auto; color: transparent; -webkit-background-clip: text; background-clip: text;
    animation: lightSweepAnim 5s linear infinite; text-shadow: 0 0 25px rgba(59, 130, 246, 0.25);
    text-align: center; margin-bottom: 4px; text-transform: uppercase;
}

/* FORM NHẬP LIỆU */
.stTextArea textarea, .stTextInput input {
    background-color: rgba(15, 23, 42, 0.8) !important; backdrop-filter: blur(12px);
    color: #F8FAFC !important; border: 1px solid rgba(96, 165, 250, 0.4) !important; border-radius: 8px !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
    border-color: #60a5fa !important; box-shadow: 0 0 12px rgba(96, 165, 250, 0.3) !important;
}

/* SUMMARY CARD */
.script-summary-card {
    background: rgba(13, 17, 23, 0.85); border: 1px solid rgba(255, 255, 255, 0.12);
    border-left: 5px solid #6366F1; border-radius: 12px; padding: 22px 26px; margin-bottom: 30px;
    box-shadow: inset 0 -30px 40px -20px rgba(59, 130, 246, 0.15), 0 15px 35px -10px rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(16px); color: #F8FAFC;
}
.script-summary-title { font-size: 1.1rem; font-weight: 700; color: #93c5fd; margin-bottom: 12px; display: flex; align-items: center; }
.script-summary-body { font-size: 0.95rem; line-height: 1.7; color: #cbd5e1; }
.script-summary-body ul { margin: 6px 0 0 18px; padding: 0; }
.script-summary-body li { margin-bottom: 8px; }

/* B-ROLL TAGS */
.broll-wrapper { margin-top: 8px; margin-bottom: 24px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.broll-label { font-size: 0.78rem; color: #94a3b8; font-weight: 600; margin-right: 4px; text-transform: uppercase; }
.broll-tag {
    background-color: rgba(255, 255, 255, 0.06) !important; color: #cbd5e1 !important; padding: 3px 10px !important;
    border-radius: 6px !important; font-size: 0.78rem !important; text-decoration: none !important; font-weight: 500 !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important; display: inline-block !important; transition: all 0.2s ease !important;
}
.broll-tag:hover {
    background-color: rgba(59, 130, 246, 0.25) !important; color: #ffffff !important;
    border-color: rgba(59, 130, 246, 0.5) !important; box-shadow: 0 0 12px rgba(59, 130, 246, 0.3);
}

/* TEXT OVERLAY & TOOLTIP */
.editor-hl { position: relative; display: inline-block; margin: 0 2px; }
.vi-click {
    color: #60a5fa !important; font-weight: 600; border-bottom: 1.5px dashed rgba(96, 165, 250, 0.6);
    cursor: pointer; padding: 2px 6px; border-radius: 4px; transition: background-color 0.2s ease, color 0.2s ease;
    user-select: text; display: inline-block;
}
.vi-click:hover { background-color: rgba(59, 130, 246, 0.2); color: #93c5fd !important; border-bottom-style: solid; box-shadow: 0 0 10px rgba(59, 130, 246, 0.25); }
.editor-hl.copied .vi-click { animation: copyPulse 0.4s ease-out; background-color: rgba(16, 185, 129, 0.25) !important; color: #34d399 !important; border-bottom-color: #34d399 !important; }
.en-click { cursor: pointer; color: #f8fafc; padding: 3px 6px; border-radius: 4px; display: inline-block; transition: all 0.2s; }
.en-click:hover { background-color: rgba(255, 255, 255, 0.15); color: #93c5fd; }
.editor-hl .hl-tooltip {
    visibility: hidden; opacity: 0; width: max-content; max-width: 320px;
    background-color: #090d16; color: #f8fafc; text-align: center; border-radius: 8px;
    padding: 8px 12px; position: absolute; z-index: 99999; bottom: 100%; left: 50%;
    transform: translateX(-50%) translateY(-8px); transition: opacity 0.2s ease, transform 0.2s ease, visibility 0.2s;
    font-size: 0.85rem; font-weight: 500; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(255, 255, 255, 0.15);
    pointer-events: auto; line-height: 1.4; white-space: normal;
}
.editor-hl .hl-tooltip::after { content: ""; position: absolute; top: 100%; left: 0; width: 100%; height: 15px; }
.editor-hl:hover .hl-tooltip { visibility: visible; opacity: 1; transform: translateX(-50%) translateY(-10px); }

@keyframes copyPulse {
    0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.8); }
    50% { transform: scale(1.06); box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
    100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}
</style>

<div class="bg-video-container">
    <video autoplay muted loop playsinline>
        <source src="https://raw.githubusercontent.com/minh66993318-collab/editor-ai-tool/main/bg-video.mp4" type="video/mp4">
    </video>
</div>
<div class="bg-overlay"></div>
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
            if not stripped: continue
            if stripped.startswith(('-', '*')):
                content_clean = re.sub(r'^[-*]\s*', '', stripped)
                escaped_text = html.escape(content_clean)
                bolded = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', escaped_text)
                parsed_lines.append(f"<li>{bolded}</li>")
            else:
                escaped_text = html.escape(stripped)
                bolded = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', escaped_text)
                parsed_lines.append(f"<p style='margin-bottom: 6px;'>{bolded}</p>")

        body_content = f"<ul>{''.join(parsed_lines)}</ul>" if "<li>" in "".join(parsed_lines) else "".join(parsed_lines)
        summary_card_html = f'<div class="script-summary-card"><div class="script-summary-title">📌 Tóm tắt tổng quan</div><div class="script-summary-body">{body_content}</div></div>'
        main_content = re.sub(summary_regex, '', text, flags=re.DOTALL | re.IGNORECASE)
        main_content = re.sub(r'^\s*---\s*', '', main_content.strip())

    def replace_match(m):
        content = m.group(1).strip()
        if "::" in content:
            parts = content.split("::", 1)
            vi_text = html.escape(parts[0].strip())
            en_text = html.escape(parts[1].strip())
            return (f'<span class="editor-hl">'
                    f'<span class="hl-tooltip">'
                    f'<span class="copy-trigger en-click" data-copytext="{en_text}">{en_text}</span><br>'
                    f'<span class="copy-hint" style="font-style: italic; opacity: 0.5; font-size: 0.85em; display: inline-block; margin-top: 4px;">(Nhấp để copy)</span>'
                    f'</span>'
                    f'<span class="copy-trigger vi-click" data-copytext="{vi_text}">{vi_text}</span>'
                    f'</span>')
        else:
            clean_text = html.escape(content)
            return (f'<span class="editor-hl">'
                    f'<span class="hl-tooltip">'
                    f'<span class="copy-hint" style="font-style: italic; opacity: 0.5; font-size: 0.85em;">(Nhấp để copy)</span>'
                    f'</span>'
                    f'<span class="copy-trigger vi-click" data-copytext="{clean_text}">{clean_text}</span>'
                    f'</span>')

    parts = re.split(r'(<[^>]+>)', main_content)
    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r'["“]([^"”<]+)["”]', replace_match, parts[i])
    main_content = "".join(parts)

    def render_broll(m):
        tags = [f'<a href="https://www.pexels.com/vi-vn/tim-kiem/videos/{urllib.parse.quote(kw.strip())}/" target="_blank" class="broll-tag">{html.escape(kw.strip())}</a>' for kw in re.split(r'[|,]', m.group(1)) if kw.strip()]
        return f'<div class="broll-wrapper"><span class="broll-label">B-roll:</span>{"".join(tags)}</div>'

    main_content = re.sub(r'\[BROLL:\s*(.*?)\]', render_broll, main_content, flags=re.IGNORECASE)
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
                    e.preventDefault(); e.stopPropagation();
                    const textToCopy = el.getAttribute('data-copytext');
                    const parentHl = el.closest('.editor-hl');
                    const hint = parentHl ? parentHl.querySelector('.copy-hint') : null;
                    
                    function handleSuccess() {
                        if (hint && parentHl) {
                            if (!hint.hasAttribute('data-orig')) { hint.setAttribute('data-orig', hint.innerText); }
                            hint.innerText = 'Đã copy!';
                            parentHl.classList.remove('copied'); void parentHl.offsetWidth; parentHl.classList.add('copied');
                            setTimeout(() => { hint.innerText = hint.getAttribute('data-orig'); parentHl.classList.remove('copied'); }, 1200);
                        }
                    }
                    
                    if (parentDoc.defaultView && parentDoc.defaultView.navigator.clipboard) {
                        parentDoc.defaultView.navigator.clipboard.writeText(textToCopy).then(handleSuccess).catch(() => {
                            fallbackCopy(parentDoc, textToCopy); handleSuccess();
                        });
                    } else { fallbackCopy(parentDoc, textToCopy); handleSuccess(); }
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
# 4. DATABASE & BẢO MẬT 
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
# 5. GIAO DIỆN STREAMLIT CHÍNH
# ==========================================
init_db()

# KHỞI TẠO SESSION
for k in ["logged_in", "user_email", "final_result", "is_processing", "chat_messages"]:
    if k not in st.session_state: 
        st.session_state[k] = False if k in ["logged_in", "is_processing"] else [] if k == "chat_messages" else "" if k == "user_email" else None

if not st.session_state.logged_in:
    # CHỈ CĂN GIỮA TRANG ĐĂNG NHẬP
    st.markdown("<style>.block-container { max-width: 600px !important; margin: 0 auto !important; }</style>", unsafe_allow_html=True)
    st.markdown("<h1 class='light-sweep-title' style='margin-top: 30px;'>TRỢ LÝ KỊCH BẢN VIDEO</h1>", unsafe_allow_html=True)
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
    # CĂN MỞ RỘNG CHO TRANG LÀM VIỆC CHÍNH
    st.markdown("<style>.block-container { max-width: 1400px !important; padding-top: 1rem !important; margin: 0 auto !important; }</style>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.write(f"👤 **Tài khoản:** `{st.session_state.user_email}`")
        if st.button("🚪 Đăng Xuất", use_container_width=True):
            st.session_state.logged_in = False; st.rerun()

    st.markdown("<h1 class='light-sweep-title'>TRỢ LÝ KỊCH BẢN VIDEO</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94a3b8; margin-bottom: 25px;'>Công cụ phân tích, tối ưu kịch bản & trích xuất Text Overlay chuyên nghiệp.</p>", unsafe_allow_html=True)

    # CHIA BỐ CỤC: TRÁI 70% (KỊCH BẢN) - PHẢI 30% (CHAT AI)
    col_main, col_chat = st.columns([7, 3], gap="large")

    with col_main:
        mode_option = st.radio("🌐 Chọn chế độ xử lý:", ["Dịch thuật sang Tiếng Việt", "Giữ nguyên ngôn ngữ gốc"], horizontal=True)

        with st.form("script_analysis_form"):
            script_input = st.text_area("Dán kịch bản video của bạn vào đây:", height=200, placeholder="Paste kịch bản gốc vào đây...")
            
            char_count = len(script_input)
            word_count = len(script_input.split())
            est_minutes = round(word_count / 160, 1) if word_count > 0 else 0
            st.caption(f"📊 **Dung lượng kịch bản:** {char_count:,} ký tự | {word_count:,} từ | **Ước tính thời lượng video:** ~{est_minutes} phút")

            submit_btn = st.form_submit_button("✨ Tối Ưu Kịch Bản", type="primary", use_container_width=True, disabled=st.session_state.is_processing)

        latest_hist = get_latest_history(st.session_state.user_email)
        if latest_hist:
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            hist_col1, hist_col2 = st.columns([3, 1])
            with hist_col1:
                snippet = latest_hist[0][:35].replace(chr(10), ' ') + "..."
                st.caption(f"📜 **Kịch bản gần nhất:** `{snippet}` (Lúc {latest_hist[2]})")
            with hist_col2:
                if st.button("🔄 Tải lại kịch bản", use_container_width=True):
                    st.session_state.final_result = latest_hist[1]
                    st.rerun()

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

        # HIỂN THỊ KẾT QUẢ ĐÃ TÁCH TAB
        if st.session_state.final_result:
            st.markdown("---")
            
            # TÁCH 2 TAB: KẾT QUẢ TỐI ƯU VÀ KỊCH BẢN GỐC
            tab_result, tab_original = st.tabs(["✨ Kết quả Tối ưu", "📜 Kịch bản Gốc"])
            
            with tab_result:
                col_info, col_download = st.columns([3, 1])
                with col_info:
                    st.caption("💡 **Mẹo:** Rê chuột vào các từ khóa để xem bản dịch. **Nhấp chuột 1 lần** để tự động Copy!")
                with col_download:
                    clean_txt = clean_script_for_download(st.session_state.final_result)
                    st.download_button(
                        label="📥 Tải (.txt)",
                        data=clean_txt,
                        file_name=f"Kich_Ban_Editor_{time.strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )

                summary_html, main_content_html = parse_and_render_script(st.session_state.final_result)
                if summary_html: st.markdown(summary_html, unsafe_allow_html=True)
                st.markdown(main_content_html, unsafe_allow_html=True)
                inject_copy_javascript()
                
            with tab_original:
                st.text_area("Nội dung kịch bản gốc bạn đã nhập:", value=latest_hist[0] if latest_hist else script_input, height=400, disabled=True)

    # KHU VỰC TAY PHẢI: CHAT AI TÍCH HỢP
    with col_chat:
        st.markdown("""<div style="padding: 10px; background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; text-align: center; font-weight: bold; margin-bottom: 15px; color: #f8fafc;">💬 Trợ lý Chat AI</div>""", unsafe_allow_html=True)
        
        chat_container = st.container(height=550)
        with chat_container:
            if not st.session_state.chat_messages:
                st.caption("Tra cứu thuật ngữ, hỏi mẹo Edit, hoặc nhờ AI phân tích ý tưởng...")
            for msg in st.session_state.chat_messages:
                with st.chat_message(msg["role"]): st.markdown(msg["content"])

        if chat_input := st.chat_input("Nhắn gì đó cho AI..."):
            st.session_state.chat_messages.append({"role": "user", "content": chat_input})
            with chat_container:
                with st.chat_message("user"): st.markdown(chat_input)
                with st.chat_message("assistant"):
                    try:
                        genai.configure(api_key=GEMINI_API_KEY)
                        chat_model = genai.GenerativeModel("gemini-1.5-flash")
                        history = [{"role": "user" if m["role"]=="user" else "model", "parts": [m["content"]]} for m in st.session_state.chat_messages[:-1]]
                        chat_session = chat_model.start_chat(history=history)
                        response = chat_session.send_message(chat_input)
                        st.markdown(response.text)
                        st.session_state.chat_messages.append({"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error(f"Lỗi phản hồi: {e}")
