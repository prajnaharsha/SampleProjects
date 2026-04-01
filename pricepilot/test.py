from google import genai

client = genai.Client(api_key="AIzaSyCLMp8K8s6Y-yt1o2Rmo37XiZbHeLBLmPs")

for m in client.models.list():
    print(m.name)