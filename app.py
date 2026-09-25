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

FORMULA_VIETNAMESE = """
VIDEO SCRIPT PROCESSING FORMULA (VIETNAMESE TRANSLATION MODE)
Role: You are a professional Video Editor assistant. Your task is to translate and process the original script into a bilingual editing script.

I. DATA PROCESSING WORKFLOW
1. OVERVIEW SUMMARY: At the very top, write a bulleted summary paragraph under the exact title: ### 📌 **Tóm tắt tổng quan**
2. SECTION STRUCTURE: Format each section header as: ### 🎬 **X. [Section Title]**
3. MAIN SCRIPT CONTENT (A-ROLL / VOICEOVER):
   - Translate voiceover into natural, modern Vietnamese. Maintain continuous line breaks between key thoughts or speaking rhythms.
   - EMBED TEXT OVERLAYS DIRECTLY WITHIN SENTENCES: Enclose important terms directly inside the script text using double quotes formatted as: "Vietnamese Content :: Original English Text".
   
   - TEXT OVERLAY SELECTION CRITERIA (Apply conditionally based on actual content; DO NOT force):
     + [ALWAYS REQUIRED]: High-value keywords, punchlines, core message of the section.
     + [ACTIVATE IF PRESENT]: Enumerated lists (short words/phrases appearing after colons ':', separated by commas).
     + [ACTIVATE IF PRESENT]: Proper nouns, personal names, brand names, specific entities/objects, specialized terms/concepts.

   * CRITICAL RULE: If the script section lacks enumerated lists or proper nouns, ONLY wrap core keywords/punchlines. Absolutely DO NOT fabricate, stretch, or force unneeded words.

4. HIDDEN BILINGUAL TOGGLE & B-ROLL:
   - Directly below the Vietnamese content of EACH section, insert the complete original English script between: [TOGGLE_START] and [TOGGLE_END].
   - At the end of each section, append exactly 5 English B-roll keywords formatted as: `[BROLL: kw1 | kw2 | kw3 | kw4 | kw5]`

---
EXACT OUTPUT FORMAT PATTERN FOR EACH SECTION (MANDATORY TO FOLLOW 100%):

### 🎬 **1. [Tên Phân Đoạn Mẫu]**
Chào mừng bạn đến với "Tên chủ đề chính :: Main Topic Name".
Nhiều người thường gặp rắc rối với "vấn đề cốt lõi :: core issue" và "thử thách phổ biến :: common challenge".
Hôm nay chúng ta sẽ khám phá giải pháp cùng "Tên chuyên gia :: Expert Name" từ "Tên thương hiệu :: Brand Name".

[TOGGLE_START]
Welcome to Main Topic Name. Many people struggle with core issue and common challenge. Today we will explore solutions with Expert Name from Brand Name.
[TOGGLE_END]

[BROLL: topic visual | main subject | concept visual | professional environment | modern background]
---
"""

FORMULA_ORIGINAL = """
VIDEO SCRIPT PROCESSING FORMULA (ORIGINAL LANGUAGE MODE)
Role: You are a professional Video Editor assistant. Your task is to process the original script into a structured editing script while maintaining its original language.

I. DATA PROCESSING WORKFLOW
1. OVERVIEW SUMMARY: At the very top, include a bulleted summary under: ### 📌 **Overview Summary**
2. SECTION HEADINGS: Format each section header as: ### 🎬 **X. [Section Name]**
3. MAIN SCRIPT CONTENT:
   - Present original script text clearly with continuous line breaks between key thoughts or speaking rhythms.
   - EMBED TEXT OVERLAYS DIRECTLY WITHIN SENTENCES using double quotes: "Text Overlay".
   
   - TEXT OVERLAY SELECTION CRITERIA (Apply conditionally based on actual content; DO NOT force):
     + [ALWAYS REQUIRED]: Core key phrases, punchlines, and main takeaways of the section.
     + [ACTIVATE IF PRESENT]: Enumerated lists (short phrases after colons ':', comma-separated items).
     + [ACTIVATE IF PRESENT]: Proper nouns, personal/brand names, specific entities, and technical terminology.

   * CRITICAL RULE: If a section lacks lists or proper nouns, ONLY double-quote the primary key phrases/punchlines. Absolutely DO NOT force or over-extract unnecessary words.

4. HIDDEN TOGGLE & B-ROLL:
   - Directly below the original script of EACH section, insert the corresponding full Vietnamese translation between: [TOGGLE_START] and [TOGGLE_END].
   - At the end of each section, include exactly 5 English B-roll keywords formatted as: `[BROLL: kw1 | kw2 | kw3 | kw4 | kw5]`

---
EXACT OUTPUT FORMAT PATTERN FOR EACH SECTION (MANDATORY TO FOLLOW 100%):

### 🎬 **1. [Sample Section Title]**
Welcome to "Main Topic Name".
Many people struggle with "core issue" and "common challenge".
Today we will explore solutions with "Expert Name" from "Brand Name".

[TOGGLE_START]
Chào mừng bạn đến với Tên chủ đề chính. Nhiều người thường gặp rắc rối với vấn đề cốt lõi và thử thách phổ biến. Hôm nay chúng ta sẽ khám phá giải pháp cùng Tên chuyên gia từ Tên thương hiệu.
[TOGGLE_END]

[BROLL: topic visual | main subject | concept visual | professional environment | modern background]
---
"""

# ==========================================
# 2. KHỞI TẠO CẤU HÌNH GIAO DIỆN & GLOBAL CSS 
# ==========================================
st.set_page_config(page_title="Trợ Lý Kịch Bản Video", page_icon="🎬", layout="centered")

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

/* TRỤC GIỮA 900PX */
.block-container { max-width: 900px !important; padding-top: 1.5rem !important; margin: 0 auto !important; }

/* ẨN HEADER/FOOTER MẶC ĐỊNH */
[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
#MainMenu, footer, header { visibility: hidden; }

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
.stTextArea textarea, .stTextInput input, .stNumberInput input {
    background-color: rgba(15, 23, 42, 0.8) !important; backdrop-filter: blur(12px);
    color: #F8FAFC !important; border: 1px solid rgba(96, 165, 250, 0.4) !important; border-radius: 8px !important;
}
.stTextArea textarea:focus, .stTextInput input:focus, .stNumberInput input:focus {
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
.editor-hl { position: relative; display: inline; margin: 0 2px; }
.vi-click {
    color: #60a5fa !important; font-weight: 600; border-bottom: 1.5px dashed rgba(96, 165, 250, 0.6);
    cursor: pointer; padding: 2px 6px; border-radius: 4px; transition: background-color 0.2s ease, color 0.2s ease;
    user-select: text; display: inline;
    box-decoration-break: clone; -webkit-box-decoration-break: clone;
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

details summary::-webkit-details-marker { display: none; }
details summary { list-style: none; }
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
def parse_and_render_script(text, toggle_label=None):
    toggle_label = toggle_label or "Xem thêm nội dung gốc"

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

    stashed_toggles = []

    def _stash_toggle(m):
        stashed_toggles.append(m.group(1).strip())
        return f"@@TOGGLE_PLACEHOLDER_{len(stashed_toggles) - 1}@@"

    main_content = re.sub(r'\[TOGGLE_START\](.*?)\[TOGGLE_END\]', _stash_toggle, main_content, flags=re.DOTALL | re.IGNORECASE)

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

    main_content = re.sub(r'`?\[BROLL:\s*(.*?)\]`?', render_broll, main_content, flags=re.IGNORECASE)
    
    main_content = re.sub(r'^###\s*🎬\s*\*\*(.*?)\*\*', r'<h3 style="color:#A5B4FC; font-weight:700; margin-top:24px; margin-bottom:12px;">🎬 \1</h3>', main_content, flags=re.MULTILINE)
    main_content = re.sub(r'^###\s*(.*?)$', r'<h3 style="color:#A5B4FC; font-weight:700; margin-top:24px; margin-bottom:12px;">\1</h3>', main_content, flags=re.MULTILINE)

    for idx, raw_content in enumerate(stashed_toggles):
        escaped = html.escape(raw_content).replace("\n", "<br>")
        toggle_html = (
            '<details style="margin-top: 10px; margin-bottom: 15px; padding: 10px; '
            'background: rgba(255,255,255,0.05); border-radius: 8px; cursor: pointer;">'
            f'<summary style="font-weight: 600; color: #94A3B8;">➕ {html.escape(toggle_label)}</summary>'
            f'<p style="margin-top: 10px; color: #CBD5E1;">{escaped}</p>'
            '</details>'
        )
        main_content = main_content.replace(f"@@TOGGLE_PLACEHOLDER_{idx}@@", toggle_html)

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
    cleaned = re.sub(r'\[TOGGLE_START\].*?\[TOGGLE_END\]', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
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
    c.execute("""CREATE TABLE IF NOT EXISTS script_history (
        email TEXT PRIMARY KEY,
        script_input TEXT,
        result_text TEXT,
        mode_label TEXT,
        timestamp TEXT
    )""")
    c.execute("PRAGMA table_info(script_history)")
    existing_cols = [row[1] for row in c.fetchall()]
    if "mode_label" not in existing_cols:
        c.execute("ALTER TABLE script_history ADD COLUMN mode_label TEXT")
    conn.commit()
    conn.close()

def hash_password(password): return hashlib.sha256(password.encode()).hexdigest()

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

def save_latest_history(email, script_input, result_text, mode_label):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    timestamp = time.strftime('%d/%m/%Y %H:%M')
    c.execute(
        "INSERT OR REPLACE INTO script_history (email, script_input, result_text, mode_label, timestamp) VALUES (?, ?, ?, ?, ?)",
        (email, script_input, result_text, mode_label, timestamp)
    )
    conn.commit()
    conn.close()

def get_latest_history(email):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT script_input, result_text, mode_label, timestamp FROM script_history WHERE email=?", (email,))
    row = c.fetchone()
    conn.close()
    return row

# ==========================================
# 5. GIAO DIỆN STREAMLIT CHÍNH
# ==========================================
init_db()

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "final_result" not in st.session_state: st.session_state.final_result = None
if "final_result_mode" not in st.session_state: st.session_state.final_result_mode = None
if "is_processing" not in st.session_state: st.session_state.is_processing = False

if not st.session_state.logged_in:
    st.markdown("<h1 class='light-sweep-title' style='margin-top: 30px;'>TRỢ LÝ KỊCH BẢN VIDEO</h1>", unsafe_allow_html=True)
    tab_login, tab_register = st.tabs(["🔑 Đăng Nhập", "📝 Đăng Ký"])

    with tab_login:
        login_email = st.text_input("Gmail đăng nhập:").strip().lower()
        login_password = st.text_input("Mật khẩu:", type="password")
        if st.button("Đăng Nhập", type="primary", use_container_width=True):
            if verify_user(login_email, login_password):
                st.session_state.logged_in = True
                st.session_state.user_email = login_email
                st.rerun()
            else: 
                st.error("Gmail hoặc Mật khẩu không chính xác!")

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
    st.markdown("<h1 class='light-sweep-title' style='margin-top: 20px;'>TRỢ LÝ KỊCH BẢN VIDEO</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94a3b8; margin-bottom: 25px;'>Công cụ phân tích, tối ưu kịch bản & trích xuất Text Overlay chuyên nghiệp.</p>", unsafe_allow_html=True)

    mode_option = st.radio("🌐 Chọn chế độ xử lý:", ["Dịch thuật sang Tiếng Việt", "Giữ nguyên ngôn ngữ gốc"], horizontal=True)

    with st.form("script_analysis_form"):
        script_input = st.text_area("Dán kịch bản video của bạn vào đây:", height=200, placeholder="Paste kịch bản gốc vào đây...")
        
        char_count = len(script_input)
        word_count = len(script_input.split())
        est_minutes = round(word_count / 160, 1) if word_count > 0 else 0
        st.caption(f"📊 **Dung lượng kịch bản:** {char_count:,} ký tự | {word_count:,} từ | **Ước tính thời lượng video:** ~{est_minutes} phút")

        # THÊM BỘ NHẬP THỜI LƯỢNG TÙY CHỌN (OPTIONAL)
        st.markdown("<p style='font-size: 0.9rem; font-weight: 600; color: #93c5fd; margin-top: 10px; margin-bottom: 2px;'>⏱️ Thời lượng video thực tế (Tùy chọn - Để 0 nếu chưa có video):</p>", unsafe_allow_html=True)
        col_dur1, col_dur2, col_dur3 = st.columns(3)
        with col_dur1:
            dur_h = st.number_input("Giờ", min_value=0, max_value=23, value=0, step=1)
        with col_dur2:
            dur_m = st.number_input("Phút", min_value=0, max_value=59, value=0, step=1)
        with col_dur3:
            dur_s = st.number_input("Giây", min_value=0, max_value=59, value=0, step=1)

        submit_btn = st.form_submit_button("✨ Tối Ưu Kịch Bản", type="primary", use_container_width=True, disabled=st.session_state.is_processing)

    latest_hist = get_latest_history(st.session_state.user_email)
    if latest_hist:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        hist_col1, hist_col2 = st.columns([3, 1])
        with hist_col1:
            snippet = latest_hist[0][:35].replace(chr(10), ' ') + "..."
            st.caption(f"📜 **Kịch bản gần nhất:** `{snippet}` (Lúc {latest_hist[3]})")
        with hist_col2:
            if st.button("🔄 Tải lại kịch bản", use_container_width=True):
                st.session_state.final_result = latest_hist[1]
                st.session_state.final_result_mode = latest_hist[2] or "Xem thêm nội dung gốc"
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
                
                model = genai.GenerativeModel("gemini-3.1-pro-preview", safety_settings=safety_settings)
                is_vi_mode = "Tiếng Việt" in mode_option
                instruction = FORMULA_VIETNAMESE if is_vi_mode else FORMULA_ORIGINAL
                
                # KIỂM TRA TÍNH NĂNG TÍNH THỜI LƯỢNG TIMELINE
                total_seconds = dur_h * 3600 + dur_m * 60 + dur_s
                if total_seconds > 0:
                    time_str = f"{dur_h:02d}:{dur_m:02d}:{dur_s:02d}" if dur_h > 0 else f"{dur_m:02d}:{dur_s:02d}"
                    duration_prompt_addon = f"""

[OPTIONAL TIMELINE STAMP RULE ACTIVATED]:
The user has provided the total duration of the actual video as {time_str} ({total_seconds} seconds).
You MUST calculate and estimate the starting and ending timestamp for EVERY section header based on the proportion of text in each section relative to the total script length.
Format each section header EXACTLY as: ### 🎬 **X. [Section Title] (start_time - end_time)**
Example: ### 🎬 **1. [Section Title] (00:00 - 01:25)**
Ensure the timeline starts at 00:00 and finishes close to {time_str}.
"""
                    instruction += duration_prompt_addon

                toggle_label = "Xem bản gốc tiếng Anh (Original Script)" if is_vi_mode else "Xem bản dịch tiếng Việt"

                response = model.generate_content(
                    f"{instruction}\n\n--- KỊCH BẢN CẦN XỬ LÝ ---\n{script_input}",
                    stream=False,
                )
                
                st.session_state.final_result = response.text
                st.session_state.final_result_mode = toggle_label
                save_latest_history(st.session_state.user_email, script_input, response.text, toggle_label)
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

        summary_html, main_content_html = parse_and_render_script(
            st.session_state.final_result,
            st.session_state.final_result_mode,
        )
        full_render_html = (summary_html or "") + main_content_html
        st.markdown(full_render_html, unsafe_allow_html=True)
        inject_copy_javascript()
