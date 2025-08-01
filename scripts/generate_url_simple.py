import urllib.parse

base_url = "https://test-connect.calomeal.com/auth/request"
params = {
    "response_type": "code",
    "client_id": "naddy_yolo",
    "redirect_uri": "https://naddy-ai-bot-flask.onrender.com/callback",
    "state": "securetoken20250627naddyxyzABC9876543210"
}

url = f"{base_url}?{urllib.parse.urlencode(params)}"
print("🔗 認証URL：", url)
