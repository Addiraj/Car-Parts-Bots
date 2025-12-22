
print("WSGI: starting import")
from app import create_app
print("WSGI: creating app")
app = create_app()
print("WSGI: app created")

