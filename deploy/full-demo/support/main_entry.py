from app.main import app as application
from demo_guard import DemoGuard

app = DemoGuard(application)
