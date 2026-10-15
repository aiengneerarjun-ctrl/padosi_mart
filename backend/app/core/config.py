from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "db"
    postgres_port: int = 5432
    redis_url: str = "redis://redis:6379/0"

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    otp_ttl_seconds: int = 300
    sms_provider: str = "console"
    # Product photos ka storage. dev: "local" (backend ke volume me), production: "s3" (koi bhi S3-compatible)
    storage_backend: str = "local"  # "local" ya "s3"
    media_dir: str = "/code/media"  # sirf local ke liye
    media_public_url: str = "http://localhost:8000/media"  # photo ka public base URL
    s3_endpoint_url: str | None = None  # AWS S3 ke liye khali; R2/Wasabi jaise ke liye unka URL
    s3_bucket: str = "padosi-media"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"
    # KYC jaisi PRIVATE files (ID photo). Ye public /media se kabhi nahi dikhti, sirf backend se (admin) milti hain.
    private_media_dir: str = "/code/private_media"  # sirf local ke liye
    s3_private_bucket: str = "padosi-private"  # production me alag, private bucket (public access band)

        # Online payment (Cashfree). cashfree_client_id, cashfree_client_secret aur payment_notify_url teeno bhare ho tabhi ONLINE payment chalu hota hai.
    cashfree_client_id: str = ""
    cashfree_client_secret: str = ""
    cashfree_env: str = "sandbox"  # "sandbox" (test) ya "production" (asli paisa)
    cashfree_api_version: str = "2026-01-01"
    payment_notify_url: str = ""  # PUBLIC https URL: https://<aapka-domain>/api/v1/payments/cashfree/webhook
    payment_return_url: str = ""  # payment ke baad customer jahan wapas aaye (app ka link / web page); khali bhi chalega
    payment_window_minutes: int = 15  # itne minute me payment na hui to order cancel ho jaata hai (stock wapas)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def payments_enabled(self) -> bool:
        return bool(self.cashfree_client_id and self.cashfree_client_secret and self.payment_notify_url)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()