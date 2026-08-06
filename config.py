import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    # Falls back to a local SQLite file so the app is runnable before Neon
    # is wired up. Set DATABASE_URL (Neon pooled connection string) for
    # real/deployed use.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(os.getcwd(), "instance", "dev.db")
    )
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
