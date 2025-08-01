# scripts/authorize_token.py

import requests

# 🔐 ここに取得した code を貼り付け！
auth_code = "def50200ed7ad081c17d0953d92ef1dc9688cdb5453afb50e3efd5c54cdf955e09f20c4aa5b9dec0327ade333b738bb54e2c5c4bf3071c1526e5cb6fba2cfc34c1ac429734a6d653e51906b4a00f769f18fd06c5be8dd25722be5e045b2faf0743e3c45a6dedc4f7805e5823e2aa9ab459def6166343a20aa1e77f7e3e62ebfd202531475306b2d015a08aa80f1d8543d0e17da0c202e128669bebb38387824d50b93e14d613212e7a027b45dd113d28f1a4a6146802254530a99b1adbf0f240bb2ccaad00d16c2792cbd1b27d44dd7ccdc4ce3e256583d24e3d66a82b6c84395ef466f250cfd020a114972684e88e4a926145a9eefed2c0061a262bc6453dbef709d07725666963dc12f8702884ece4503bd7dbdf90bb7d5306d12c1589d66d3fcab1b1e35582a08ec2ab39976d588da2abe94a140f78af3733e0ad644dad1bd795637f43d718fb54207e8f59f2476f6f83b0fb2edb4f89eecfde82d0bc7756818f4d9be6382457a1251b22aa73ab1631f889a06ed26a02f80ad925c0ee2a8cae05da06"

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
