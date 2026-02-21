import codecs
import re

file_path = r"c:\Yash\Arabic-AI-Legal-Case-Analysis-Assistant-working\Arabic-AI-Legal-Case-Analysis-Assistant-working\backend\legal_principles.py"
with codecs.open(file_path, "r", "utf-8") as f:
    content = f.read()

def labor_replacer(match):
    return match.group(1) + '\n        "url": "https://laws.boe.gov.sa/BoeLaws/Laws/LawDetails/16b97fd5-6490-449e-87fe-a9a700f26f25/1",'

content = re.sub(r'(\s*"id":\s*"labor_[^"]+",)', labor_replacer, content)

def general_replacer(match):
    return match.group(1) + '\n        "url": "https://moj.gov.sa/ar/ministry/rules/Pages/default.aspx",'

content = re.sub(r'(\s*"id":\s*"(?!labor_)[^"]+",)', general_replacer, content)

with codecs.open(file_path, "w", "utf-8") as f:
    f.write(content)

print("Injected URLs successfully")
