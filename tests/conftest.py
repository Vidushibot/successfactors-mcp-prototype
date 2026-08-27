import os

os.environ["APP_MODE"] = "mock"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
