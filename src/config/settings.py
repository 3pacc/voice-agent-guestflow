from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    runpod_api_key: str = Field(default="", description="RunPod API Key")
    twilio_account_sid: str = Field(default="", description="Twilio Account SID")
    twilio_auth_token: str = Field(default="", description="Twilio Auth Token")
    twilio_phone_number: str = Field(default="+33939037474", description="Twilio Phone Number")
    booking_sms_enabled: bool = Field(default=True, description="Enable booking confirmation SMS")
    booking_sms_fallback_to: str = Field(default="", description="Fallback phone number for booking SMS")
    booking_payment_test_url: str = Field(default="https://example.com/payment-test", description="Test payment URL sent by SMS")
    mistral_api_key: str = Field(default="", description="Mistral API Key for Voxtral Realtime STT")
    inworld_key: str = Field(default="", description="Inworld API Key")
    inworld_secret: str = Field(default="", description="Inworld API Secret")
    inworld_voice_id: str = Field(default="Etienne", description="Inworld voice ID")
    inworld_tts_temperature: float = Field(default=1.2, description="Inworld TTS temperature")
    inworld_tts_speaking_rate: float = Field(default=1.15, description="Inworld TTS speaking rate")
    runpod_webhook_url: str = Field(default="", description="Proxy URL for RunPod Twilio Webhook")

    llm_base_url: str = Field(default="http://vllm:8000/v1", description="vLLM Base URL")
    llm_api_key: str = Field(default="EMPTY", description="vLLM API Key")
    llm_model: str = Field(default="meta-llama/Llama-3.1-8B-Instruct", description="vLLM Model Name")
    llm_primary_enabled: bool = Field(default=True, description="Enable primary vLLM")

    # Fallback LLM (used when self-hosted vLLM fails)
    llm_fallback_enabled: bool = Field(default=True, description="Enable LLM fallback")
    llm_fallback_provider: str = Field(default="mistral", description="Fallback provider")
    llm_fallback_model: str = Field(default="mistral-small-latest", description="Fallback model name")

    database_url: str = Field(default="sqlite:///./hotel_stock.db", description="Database connection URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
