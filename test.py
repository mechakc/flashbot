import requests

uuid = "9c4c3a3e-035a-40db-9818-6bf468735770"
subscription_key = "a14abebe38bb48a7baf2ea5a851c3bec"

url = f"https://sandbox.momodeveloper.mtn.com/v1_0/apiuser/{uuid}/apikey"
headers = {
    "Ocp-Apim-Subscription-Key": subscription_key
}

r = requests.post(url, headers=headers)
print(r.status_code)
print(r.text)