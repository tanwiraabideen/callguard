"""
backend settings live here. Any field can be overridden by an environment 
variable of the same name.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # Server
    host: str = "127.0.0.1"
    port: int = 8100
    reload: bool = True  # restart on code changes; turn off when deployed

    # Browser origins allowed to call the API, comma-separated
    cors_origins: str = "http://localhost:3100,http://127.0.0.1:3100"

    # Used for live transcription and by tools/generate_audio.py
    elevenlabs_api_key: str = ""

    # Call audio generation
    tts_model: str = "eleven_multilingual_v2"
    tts_caller_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"  # George
    tts_user_voice_id: str = "Xb7hH8MSUJpSbSDYk0k2"  # Alice
    tts_default_gap_ms: int = 350  # silence between turns unless a turn sets gap_ms

    # Call audio format
    audio_sample_rate: int = 16000
    audio_channels: int = 2  # left = caller, right = user

    # How often the backend reports how much call audio it has received
    audio_progress_interval_seconds: float = 1.0

    # Transcription. "auto" uses ElevenLabs if a key is set, otherwise mock.
    # Set to "elevenlabs" or "mock" to force one.
    transcription_mode: str = "auto"
    scribe_url: str = "wss://api.elevenlabs.io/v1/speech-to-text/realtime"
    scribe_model: str = "scribe_v2_realtime"
    scribe_language: str = "en"
    scribe_vad_silence_seconds: float = 0.4  # silence that ends a segment
    scribe_close_timeout_seconds: float = 3.0  # wait for last words after a call

    # Risk engine, Tier 1: points added the first time each red flag is heard
    rule_weight_codes_or_pins: float = 35
    rule_weight_safe_account: float = 35
    rule_weight_gift_cards_or_crypto: float = 40
    rule_weight_remote_access: float = 40
    rule_weight_secrecy: float = 25
    rule_weight_urgency_or_threats: float = 20
    rule_repeat_factor: float = 0.25  # share of the points for a repeated red flag

    # Risk engine: voice pressure signals from word timestamps
    pressure_window_seconds: float = 30
    pressure_min_caller_words: int = 20  # words needed before judging rate or share
    pressure_fast_wpm: float = 230  # caller words per minute; the test voices do ~200
    pressure_talk_share: float = 0.85  # caller's share of recent speech
    pressure_interruption_min_overlap_seconds: float = 0.2
    pressure_weight_fast_speech: float = 5
    pressure_weight_interruption: float = 8
    pressure_weight_talk_share: float = 3
    pressure_points_cap: float = 15  # pressure alone can't raise an alarm

    # Risk engine, Tier 2: small LLM, only run when Tier 1 or pressure fires
    llm_enabled: bool = True
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-5-5"
    llm_effort: str = "low"
    llm_max_tokens: int = 1024
    llm_context_sentences: int = 6
    llm_timeout_seconds: float = 8.0
    llm_weight: float = 0.6  # share of the LLM score in the target risk

    # Risk engine: how the running score follows the evidence, per sentence
    risk_rise_rate: float = 0.5
    risk_fall_rate: float = 0.2
    risk_medium_threshold: float = 40
    risk_high_threshold: float = 70

    # Alerts: share of a dismissed red flag's points that remain
    dismiss_points_factor: float = 0.25

    # Spoken output. Without an ElevenLabs key the browser's own voice is used.
    speech_enabled: bool = True
    speech_model: str = "eleven_flash_v2_5"
    speech_timeout_seconds: float = 10.0
    tts_whisper_voice_id: str = "pFZP5JQG7iQjIQuC4Bku"  # Lily
    tts_agent_voice_id: str = "onwK4e9ZLuTAKqWW03F9"  # Daniel

    # Agent. Without an Anthropic key it follows a fixed policy instead.
    agent_enabled: bool = True
    agent_model: str = "claude-haiku-5-5"  # fast enough to help mid-call
    agent_effort: str = "low"
    agent_max_tokens: int = 2048
    agent_max_steps: int = 6
    agent_timeout_seconds: float = 12.0
    agent_context_sentences: int = 40
    whisper_max_words: int = 15
    trigger_phrases: str = "let me grab a pen,let me find my glasses"
    trigger_cooldown_seconds: float = 8.0
    takeover_silence_seconds: float = 20.0  # user silence at high risk

    # LangSmith tracing, on when a key is set
    langsmith_api_key: str = ""
    langsmith_project: str = "callguard"

    # Protecting the hosted demo
    demo_passcode: str = ""  # empty means no passcode is asked for
    auth_timeout_seconds: float = 30.0  # wait for the passcode after connecting
    auth_failure_delay_seconds: float = 1.0
    max_call_seconds: float = 180.0  # applies to every call

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def audio_bytes_per_frame(self) -> int:
        return 2 * self.audio_channels  # 2 bytes per sample, per channel

    @property
    def audio_bytes_per_second(self) -> int:
        return self.audio_sample_rate * self.audio_bytes_per_frame

    @property
    def trigger_phrase_list(self) -> list[str]:
        return [phrase.strip() for phrase in self.trigger_phrases.split(",") if phrase.strip()]

    @property
    def agent_llm_active(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def llm_active(self) -> bool:
        return self.llm_enabled and bool(self.anthropic_api_key)

    @property
    def active_transcription_mode(self) -> str:
        if self.transcription_mode == "auto":
            return "elevenlabs" if self.elevenlabs_api_key else "mock"
        return self.transcription_mode


settings = Settings()
