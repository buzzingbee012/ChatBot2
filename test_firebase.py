import firebase_admin
from firebase_admin import credentials, db
import traceback

try:
    cred = credentials.Certificate('serviceAccountKey.json')
    app = firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://chatbot-943de-default-rtdb.firebaseio.com'  # Let's see if we have database URL in config
    })
    print("App initialized")
    ref = db.reference('stats')
    print("Reference obtained:", ref)
    data = ref.get()
    print("Data:", data)
except Exception as e:
    print("Error:", repr(e))
    traceback.print_exc()

