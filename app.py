def convert_quotes_to_copyable_html(text):
    custom_css = """
    <style>
    /* Wrapper chứa cả cụm */
    .hl-wrapper {
        position: relative;
        display: inline-block;
    }

    /* =========================================
       1. TEXT TIẾNG VIỆT (Nút Copy VN)
       ========================================= */
    .hl-vi {
        color: #818CF8 !important;
        font-weight: 600;
        border-bottom: 2px dashed #818CF8;
        cursor: pointer;
        padding: 2px 6px;
        margin: 0 2px;
        border-radius: 4px;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        display: inline-block;
    }
    
    /* MOTION 1: Rê chuột vào Tiếng Việt -> Nảy nhẹ lên */
    .hl-vi:hover {
        background-color: rgba(99, 102, 241, 0.15);
        color: #A5B4FC !important;
        border-bottom-style: solid;
        transform: translateY(-2px); 
        box-shadow: 0 4px 6px -1px rgba(99, 102, 241, 0.2);
    }

    /* Vùng cầu nối chứa Tooltip */
    .hl-wrapper .hl-tooltip-container {
        visibility: hidden;
        opacity: 0;
        position: absolute;
        z-index: 99999;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%) translateY(5px);
        transition: opacity 0.3s ease, transform 0.3s ease, visibility 0.3s;
        padding-bottom: 12px; 
        pointer-events: none; 
    }

    /* Hiển thị tooltip khi trỏ vào Wrapper */
    .hl-wrapper:hover .hl-tooltip-container {
        visibility: visible;
        opacity: 1;
        transform: translateX(-50%) translateY(0);
        pointer-events: auto;
    }

    /* =========================================
       2. TEXT TIẾNG ANH (Nút Copy EN)
       ========================================= */
    .hl-en {
        display: block;
        background-color: #0F172A;
        color: #F8FAFC;
        text-align: center;
        border-radius: 8px;
        padding: 8px 14px;
        font-size: 0.85rem;
        font-weight: 500;
        cursor: pointer;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.15);
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        white-space: nowrap;
    }

    /* MOTION 2: Rê chuột vào Tiếng Anh -> Phóng to & Sáng viền */
    .hl-en:hover {
        background-color: #1E293B;
        transform: scale(1.08); 
        color: #E0E7FF;
        box-shadow: 0 15px 30px -5px rgba(0, 0, 0, 0.9), 0 0 0 2px rgba(129, 140, 248, 0.6);
    }

    /* --- ANIMATION COPY THÀNH CÔNG --- */
    @keyframes copySuccessVi {
        0% { transform: translateY(-2px) scale(1); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6); }
        50% { transform: translateY(-2px) scale(1.05); box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
        100% { transform: translateY(-2px) scale(1); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    
    @keyframes copySuccessEn {
        0% { transform: scale(1.08); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.8); }
        50% { transform: scale(1.15); box-shadow: 0 0 0 12px rgba(16, 185, 129, 0); }
        100% { transform: scale(1.08); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

    .hl-vi.copied {
        animation: copySuccessVi 0.4s ease-out;
        background-color: rgba(16, 185, 129, 0.2) !important;
        color: #10B981 !important;
        border-bottom-color: #10B981 !important;
    }

    .hl-en.copied {
        animation: copySuccessEn 0.4s ease-out;
        background-color: #064E3B !important;
        color: #34D399 !important;
        border: 1px solid #10B981;
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
            
            clean_vi = html.escape(vi_text)
            clean_en = html.escape(en_text)
            
            return f'''
            <span class="hl-wrapper">
                <span class="hl-vi copy-trigger" data-copytext="{clean_vi}" title="Copy Tiếng Việt">
                    {vi_text}
                </span>
                <span class="hl-tooltip-container">
                    <span class="hl-en copy-trigger" data-copytext="{clean_en}" title="Copy Tiếng Anh">
                        🇬🇧 {en_text}
                    </span>
                </span>
            </span>
            '''
        else:
            clean_text = html.escape(content)
            return f'''
            <span class="hl-wrapper">
                <span class="hl-vi copy-trigger" data-copytext="{clean_text}" title="Nhấp để copy">
                    {content}
                </span>
            </span>
            '''

    rendered_html = re.sub(pattern, replace_match, text)
    return custom_css + rendered_html
