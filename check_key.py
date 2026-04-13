import json
with open('serviceAccountKey.json') as f:
    k = json.load(f)
p = k.get('private_key', '')
print("Key length:", len(p))
print("Actual newlines:", p.count('\n'))
print("Literal '\\n':", p.count('\\n'))
print("Spaces:", p.count(' '))
print("Repr:", repr(p[:60]))
