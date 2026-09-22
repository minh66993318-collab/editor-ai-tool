def call_gemini_api_native(script_text, system_instruction, api_key):
    # Ưu tiên gemini-3.6-flash đầu tiên
    models_to_try = ["gemini-3.6-flash", "gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
    headers = {"Content-Type": "application/json; charset=utf-8"}
    
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": f"{system_instruction}\n\n--- KỊCH BẢN CẦN PHÂN TÍCH ---\n{script_text}"}
                ]
            }
        ],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    
    last_error = ""
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            if response.status_code == 200:
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            elif response.status_code == 404:
                last_error = f"Model {model_name} trả về lỗi 404"
                continue
            else:
                raise Exception(f"Lỗi API Google ({response.status_code}): {response.text}")
        except Exception as e:
            if "404" in str(e):
                last_error = str(e)
                continue
            raise e

    raise Exception(f"Không thể kết nối đến các model Gemini ({last_error}).")
