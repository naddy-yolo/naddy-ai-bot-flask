# scripts/authorize_token.py

import requests

# 🔐 ここに取得した code を貼り付け！
auth_code = "def50200e7ec280219503d26dc7d6d8741f144fa1245b617ea49d2aa8f46fdcf4baa9e981a05d3e926e58fc7dff44447ead2cd08a1d4faaea6990d1096c2d4afcfeba2e1af58f6b4c253e877a26c093ead80addd5812ef334f45f5258898872caaf5f2e0c22e68e9f7023994d62c18edd1d7460f29cbffe0d69d776d8aca48b3f64962e9991640ec493194022946c80d4ccedf1df6b75ed3d777ad5ef1199c07021ba0a60cab5840f3fd718b1ef67715890cb71fe9e890a4c28f53a491d42a8df0d0ca0d3c49cd6723db8dc680cda32c5fc63668748569fa3cb134c49eaa94aeea87708d2bd67ec23d03e47c15e77eb325fc98033981e49ef2f268832136e73fe7231e0c63a5d1af03149611caf748d69938e488eeb55e22bc230d558ca5df2390f0cb0e9d2042f4f55241105a49735501ff0079855fc9e123a99f620e9604a4fdd87f8e047c69f78996bffde5ed09afd755c7f713bbba5cf27adbf80fab8b23a60894a2779a268071a8cd1ce16363157131832aaa631cf47470ff6ff25bba01e6b10672"

client_id = "naddy_yolo"
client_secret = "q9umc8VnHNyKIZhUiOiPa7KOsMPN5vDJ"
redirect_uri = "https://naddy-ai-bot-flask.onrender.com/callback"

url = "https://test-connect.calomeal.com/auth/accesstoken"
data = {
    "grant_type": "authorization_code",
    "client_id": client_id,
    "client_secret": client_secret,
    "redirect_uri": redirect_uri,
    "code": auth_code
}

headers = {
    "Content-Type": "application/x-www-form-urlencoded"
}

response = requests.post(url, headers=headers, data=data)
print("ステータスコード:", response.status_code)
print(response.json())
