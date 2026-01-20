import requests

url = "https://127.0.0.1:8000/api/v1/workflows"

payload = {'param-name': 'testing webhook url',
'param-species': 'trifolium arvense',
'webhook_url': 'https://webhook.site/c0a4f513-c4bb-4ba3-b90c-2bdd408eb80d/workflows/{workflow_id}'}
files=[
  ('rocratefile',('temp.zip',open('/home/lena/Desktop/temp.zip','rb'),'application/zip'))
]
headers = {
  'Api-Key': '***'
}

response = requests.request("POST", url, headers=headers, data=payload, files=files)

print(response.text)