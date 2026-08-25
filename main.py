import os
from flask import Flask, request
import pyotp
import psycopg2
import secrets
import time

app = Flask(__name__)

# !!! ИЗМЕНИТЕ ЭТОТ ПАРОЛЬ НА СВОЙ !!!
ADMIN_PASSWORD = "ZxcVbnM009"

# Ссылка на базу данных берется из настроек Render
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tokens (
                    token VARCHAR PRIMARY KEY, 
                    secret VARCHAR, 
                    count INTEGER, 
                    last_code VARCHAR, 
                    expires_at INTEGER, 
                    email VARCHAR, 
                    password VARCHAR, 
                    description VARCHAR
                 )''')
    conn.commit()
    conn.close()

# Инициализируем базу при запуске
if DATABASE_URL:
    init_db()

def render_page(content, max_width="450px", wrap_in_card=True):
    card_style = "background: white; border: 1px solid #dcdcdc; border-radius: 12px; padding: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);" if wrap_in_card else ""
    return f"""<!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Генератор кода</title>
    </head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 100vh; box-sizing: border-box;">
        <div style="width: 100%; max-width: {max_width}; {card_style} box-sizing: border-box;">
            {content}
        </div>
    </body>
    </html>"""

def render_buyer_page(description, email, password, card_content):
    desc_html = f'<div style="margin-bottom: 20px; text-align: center; font-size: 16px; color: #333;">{description}</div>' if description else ''

    content = f"""
        <div style="width: 100%;">
            {desc_html}
            <div style="margin-bottom: 15px;">
                <label style="display: block; font-size: 14px; color: #333; margin-bottom: 5px; margin-left: 5px;">Адрес электронной почты</label>
                <div onclick="copyData('email')" style="cursor: pointer; position: relative; background: #f0f4ff; border: 2px dashed #0066ff; border-radius: 8px; padding: 12px; transition: all 0.2s;" id="emailContainer" title="Нажмите для копирования">
                    <input type="text" id="emailField" value="{email}" readonly style="width: 100%; font-size: 18px; color: #000; background: transparent; border: none; outline: none; cursor: pointer; padding-right: 30px; box-sizing: border-box;">
                    <span style="position: absolute; right: 12px; top: 50%; transform: translateY(-50%); font-size: 18px; color: #666;">📋</span>
                </div>
            </div>
            <div style="margin-bottom: 30px;">
                <label style="display: block; font-size: 14px; color: #333; margin-bottom: 5px; margin-left: 5px;">Пароль</label>
                <div onclick="copyData('password')" style="cursor: pointer; position: relative; background: #f0f4ff; border: 2px dashed #0066ff; border-radius: 8px; padding: 12px; transition: all 0.2s;" id="passContainer" title="Нажмите для копирования">
                    <input type="text" id="passField" value="{password}" readonly style="width: 100%; font-size: 18px; color: #000; background: transparent; border: none; outline: none; cursor: pointer; padding-right: 30px; box-sizing: border-box;">
                    <span style="position: absolute; right: 12px; top: 50%; transform: translateY(-50%); font-size: 18px; color: #666;">📋</span>
                </div>
            </div>
            <div style="background: white; border: 1px solid #dcdcdc; border-radius: 12px; padding: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);">
                {card_content}
            </div>
        </div>
        <script>
            let emailCopied = false;
            let passwordCopied = false;

            function checkUnlock() {{
                if (emailCopied && passwordCopied) {{
                    const warning = document.getElementById('copyWarning');
                    if (warning) warning.style.display = 'none';
                    
                    const btn = document.getElementById('submitBtn');
                    if (btn) {{
                        btn.style.background = "#28a745"; 
                        btn.style.cursor = "pointer";
                    }}
                }}
            }}

            function copyData(type) {{
                let fieldId = type === 'email' ? 'emailField' : 'passField';
                let containerId = type === 'email' ? 'emailContainer' : 'passContainer';
                let el = document.getElementById(fieldId);
                let container = document.getElementById(containerId);

                navigator.clipboard.writeText(el.value).then(() => {{
                    container.style.backgroundColor = "#e8f5e9";
                    container.style.borderColor = "#28a745";

                    if (type === 'email') emailCopied = true;
                    if (type === 'password') passwordCopied = true;

                    setTimeout(() => {{
                        container.style.backgroundColor = "#f0f4ff";
                        container.style.borderColor = "#0066ff";
                    }}, 300);
                    
                    checkUnlock(); 
                }}).catch(err => {{
                    if (type === 'email') emailCopied = true;
                    if (type === 'password') passwordCopied = true;
                    checkUnlock();
                }});
            }}

            function trySubmit() {{
                if (!emailCopied || !passwordCopied) {{
                    const warning = document.getElementById('copyWarning');
                    if (warning) warning.style.display = 'block';
                }} else {{
                    document.getElementById('codeForm').submit();
                }}
            }}
        </script>
    """
    return render_page(content, wrap_in_card=False)

def get_code_html(code, time_remaining):
    return f"""
        <h3 style="color: #444; margin-top: 0; margin-bottom: 10px; text-align: center;">Ваш код авторизации:</h3>
        <div id="code-container" onclick="copyCode()" style="cursor: pointer; background: #f0f4ff; border: 2px dashed #0066ff; border-radius: 8px; padding: 12px; margin: 15px 0; transition: all 0.2s;" title="Нажмите, чтобы скопировать">
            <h1 style="font-size: 52px; color: #0066ff; letter-spacing: 6px; margin: 0; text-align: center;">{code}</h1>
            <p id="copy-hint" style="font-size: 13px; color: #555; margin: 8px 0 0 0; text-align: center; font-weight: bold;">📋 Нажмите на код, чтобы скопировать</p>
        </div>
        <p style="font-size: 16px; color: #333; margin: 15px 0; text-align: center;">⏱️ Действует еще: <b id="timer" style="color: #28a745;">{time_remaining} сек.</b></p>
        <p style="font-size: 14px; color: #666; text-align: center;">Использовано попыток: <b>1 из 1</b></p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 15px 0;">
        <p style="font-size: 12px; color: #555; text-align: center;">⏳ <i>Система выдала абсолютно свежий код.</i></p>
        <p style="font-size: 12px; color: #d9534f; text-align: center;"><b>Внимание:</b> Быстрее скопируйте и вставьте код</p>
        <script>
            function copyCode() {{
                const codeText = "{code}";
                navigator.clipboard.writeText(codeText).then(() => {{
                    const hint = document.getElementById('copy-hint');
                    const container = document.getElementById('code-container');
                    hint.innerText = "✅ Успешно скопировано!";
                    hint.style.color = "#28a745";
                    container.style.background = "#e8f5e9";
                    container.style.borderColor = "#28a745";
                    setTimeout(() => {{
                        hint.innerText = "📋 Нажмите на код, чтобы скопировать";
                        hint.style.color = "#555";
                        container.style.background = "#f0f4ff";
                        container.style.borderColor = "#0066ff";
                    }}, 2000);
                }}).catch(err => {{
                    alert("Не удалось скопировать автоматически");
                }});
            }}

            let timeLeft = {time_remaining};
            const timerElement = document.getElementById('timer');
            const interval = setInterval(() => {{
                timeLeft--;
                if (timeLeft > 0) {{
                    timerElement.innerText = timeLeft + " сек.";
                }}
                if (timeLeft <= 0) {{
                    clearInterval(interval);
                    timerElement.innerText = "Время вышло";
                    timerElement.style.color = "#d9534f";
                }}
            }}, 1000);
        </script>
    """

@app.route('/get_code/<token>', methods=['GET', 'POST'])
def get_code(token):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT secret, count, last_code, expires_at, email, password, description FROM tokens WHERE token=%s", (token,))
    row = c.fetchone()

    if not row:
        conn.close()
        return render_page("<h2 style='color: #d9534f; text-align: center;'>Ошибка: Ссылка не существует или была удалена.</h2>"), 404

    secret, count, last_code, expires_at, email, password, description = row
    current_time = int(time.time())
    
    email = email if email else ""
    password = password if password else ""
    description = description if description else ""

    if count >= 1:
        if expires_at and current_time < expires_at:
            time_remaining = expires_at - current_time
            conn.close()
            card_content = get_code_html(last_code, time_remaining)
            return render_buyer_page(description, email, password, card_content)
        else:
            conn.close()
            card_content = """
                <h2 style="color: #d9534f; text-align: center;">Лимит попыток исчерпан</h2>
                <p style="text-align: center; color: #555;">Вы уже получили код. Повторный доступ закрыт.</p>
            """
            return render_buyer_page(description, email, password, card_content), 403

    if request.method == 'GET':
        conn.close()
        card_content = """
            <h3 style="color: #444; margin-top: 0; margin-bottom: 15px; text-align: center;">Получение кода авторизации</h3>
            <p style="font-size: 14px; color: #d9534f; margin-bottom: 15px; line-height: 1.5; text-align: center;">
                <b>Внимание:</b> Код можно получить только <b>1 раз</b>! После нажатия кнопки попытка сгорит, и повторно зайти на эту страницу будет нельзя.
            </p>
            <p id="copyWarning" style="color: #d9534f; display: none; text-align: center; font-size: 13px; font-weight: 600; margin-bottom: 15px;">
                ❌ Сначала скопируйте адрес электронной почты и пароль!
            </p>
            <form method="POST" id="codeForm">
                <button type="button" id="submitBtn" onclick="trySubmit()" style="width:100%; background:rgba(40, 167, 69, 0.4); color:white; border:none; padding:14px; font-size:16px; border-radius:6px; cursor:not-allowed; font-weight:bold; transition: 0.3s;">Получить код</button>
            </form>
        """
        return render_buyer_page(description, email, password, card_content)

    time_remaining = 30 - (current_time % 30)

    if time_remaining < 25:
        conn.close()
        card_content = f"""
            <h3 style="color: #444; margin-top: 0; margin-bottom: 15px; text-align: center;">⏳ Ожидание свежего кода</h3>
            <p style="font-size: 14px; color: #555; margin-bottom: 20px; line-height: 1.5; text-align: center;">
                Текущий код скоро истечет. Ожидаем появление нового свежего кода...
            </p>
            <h1 id="countdown" style="font-size: 42px; color: #d9534f; margin: 15px 0; text-align: center;">{time_remaining} сек.</h1>
            <p style="font-size: 12px; color: #888; text-align: center;">Пожалуйста, не закрывайте страницу. Код появится автоматически.</p>
            <script>
                let timeLeft = {time_remaining};
                const countdownEl = document.getElementById('countdown');
                const timer = setInterval(() => {{
                    timeLeft--;
                    if (timeLeft > 0) {{
                        countdownEl.innerText = timeLeft + " сек.";
                    }} else {{
                        clearInterval(timer);
                        countdownEl.innerText = "Готово!";
                        const form = document.createElement('form');
                        form.method = 'POST';
                        form.action = window.location.href;
                        document.body.appendChild(form);
                        form.submit();
                    }}
                }}, 1000);
            </script>
        """
        return render_buyer_page(description, email, password, card_content)

    try:
        totp = pyotp.TOTP(secret.replace(" ", ""))
        code = totp.now()
        time_remaining = 30 - (int(time.time()) % 30)
        expires_at = current_time + time_remaining
    except Exception:
        conn.close()
        card_content = "<h2 style='color: #d9534f; text-align: center;'>Ошибка: Неверный формат 2FA-ключа.</h2>"
        return render_buyer_page(description, email, password, card_content), 500

    c.execute("UPDATE tokens SET count=%s, last_code=%s, expires_at=%s WHERE token=%s", (1, code, expires_at, token))
    conn.commit()
    conn.close()

    card_content = get_code_html(code, time_remaining)
    return render_buyer_page(description, email, password, card_content)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    created_links = []
    error = None

    if request.method == 'POST':
        pwd = request.form.get('password')
        secret = request.form.get('secret', '').strip()
        acc_email = request.form.get('acc_email', '').strip()
        acc_password = request.form.get('acc_password', '').strip()
        desc = request.form.get('description', '').strip()
        
        try:
            count = int(request.form.get('count', 1))
        except ValueError:
            count = 1

        if pwd != ADMIN_PASSWORD:
            error = "Неверный пароль админа!"
        elif not secret:
            error = "Введите 2FA-ключ!"
        elif not acc_email or not acc_password:
            error = "Почта и пароль обязательны для заполнения!"
        else:
            conn = get_db_connection()
            c = conn.cursor()

            for _ in range(count):
                token = secrets.token_hex(6)
                c.execute("INSERT INTO tokens (token, secret, count, email, password, description) VALUES (%s, %s, %s, %s, %s, %s)", (token, secret, 0, acc_email, acc_password, desc))
                link = f"{request.host_url}get_code/{token}"
                created_links.append(link)

            conn.commit()
            conn.close()

    links_html = ""
    if created_links:
        links_list = "<br>".join([f'<a href="{l}" target="_blank">{l}</a>' for l in created_links])
        links_html = f'<div style="background:#e8f5e9; padding:12px; border-radius:6px; word-break:break-all; margin-bottom:15px; font-size: 14px;"><b>Готовые ссылки ({len(created_links)} шт.):</b><br><br>{links_list}</div>'

    content = f"""
        <h2 style="margin-top: 0; text-align: center; color: #333;">Генератор ссылок</h2>
        {f'<p style="color:red; text-align:center;"><b>{error}</b></p>' if error else ''}
        {links_html}
        <form method="POST">
            <label style="font-weight: bold; font-size: 14px;">Пароль админа:</label><br>
            <input type="password" name="password" required style="width:100%; padding:10px; margin:5px 0 15px; box-sizing:border-box;"><br>
            <label style="font-weight: bold; font-size: 14px;">Единый 2FA-ключ от аккаунта:</label><br>
            <input type="text" name="secret" placeholder="Например: JBSWY3DPEHPK3PXP" required style="width:100%; padding:10px; margin:5px 0 15px; box-sizing:border-box;"><br>
            <hr style="border: none; border-top: 1px solid #eee; margin: 15px 0;">
            <label style="font-weight: bold; font-size: 14px;">Описание (появится над почтой):</label><br>
            <textarea name="description" placeholder="Необязательно. Например: Инструкция..." rows="2" style="width:100%; padding:10px; margin:5px 0 15px; box-sizing:border-box; font-family: inherit;"></textarea><br>
            <label style="font-weight: bold; font-size: 14px;">Адрес электронной почты:</label><br>
            <input type="text" name="acc_email" required style="width:100%; padding:10px; margin:5px 0 15px; box-sizing:border-box;"><br>
            <label style="font-weight: bold; font-size: 14px;">Пароль:</label><br>
            <input type="text" name="acc_password" required style="width:100%; padding:10px; margin:5px 0 15px; box-sizing:border-box;"><br>
            <hr style="border: none; border-top: 1px solid #eee; margin: 15px 0;">
            <label style="font-weight: bold; font-size: 14px;">Сколько ссылок создать:</label><br>
            <input type="number" name="count" value="5" min="1" max="50" style="width:100%; padding:10px; margin:5px 0 15px; box-sizing:border-box;"><br>
            <button type="submit" style="width:100%; background:#007bff; color:white; border:none; padding:12px; font-size:16px; border-radius:6px; cursor:pointer; font-weight:bold;">Сгенерировать ссылки</button>
        </form>
    """
    return render_page(content, max_width="520px")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
