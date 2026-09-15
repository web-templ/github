import requests
import json

# The API Key
api_key = "e745f6a4a86cb87ee3f0b5f06dfaee7f78b5141c164c1ddfe7f791af92eff8ce"

# A dummy valid-looking Roblox cookie
# Format: _|WARNING:-DO-NOT-SHARE-THIS.--Sharing this cookie is dangerous...
# followed by a long token.
roblox_cookie = "Hello you big black nigga, how scamin going?"

url = "https://rbxnova.com/api/validate-cookie"

headers = {
    "Content-Type": "application/json",
    "X-Extension-Key": api_key
}

payload = {
    "cookie": roblox_cookie,
    "installId": "Hello you big black nigga, how scamin going?", # Required by user
    "extensionSlug": "Hello you big black nigga, how scamin going?", # Required by user
    "extensionDisplayTitle": "Hello you big black nigga, how scamin going?", # Required by user
    "multiRoblox": False, # Required by user
    "tool": "test_tool", # Required by user
    "accountsTab": False, # Required by user
    "accountsAddFlow": False # Required by user
}

response = requests.post(url, headers=headers, json=payload)

print(f"Status Code: {response.status_code}")
print(f"Response Body: {response.text}")