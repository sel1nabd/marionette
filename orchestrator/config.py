"""Configuration management for Marionette orchestrator."""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load .env file
load_dotenv()


@dataclass
class Config:
    """Configuration for Marionette orchestrator."""
    
    # Gemini API settings
    gemini_api_key: str
    flash_model: str = "gemini-2.0-flash-exp"
    pro_model: str = "gemini-exp-1206"
    
    # Monitoring thresholds
    debug_loop_window: int = 5
    context_drift_threshold: float = 0.7
    sycophancy_threshold: int = 3
    
    # Intervention settings
    auto_kill_loops: bool = True
    force_prompt_quality: bool = True
    enable_grounding: bool = True
    
    # Logging
    log_level: str = "INFO"
    save_session_logs: bool = True
    log_dir: str = "./marionette_logs"
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable required.\n"
                "Get your key at: https://aistudio.google.com/apikey"
            )
        
        return cls(
            gemini_api_key=api_key,
            flash_model=os.getenv("GEMINI_FLASH_MODEL", "gemini-2.0-flash-exp"),
            pro_model=os.getenv("GEMINI_PRO_MODEL", "gemini-exp-1206"),
            debug_loop_window=int(os.getenv("DEBUG_LOOP_WINDOW", "5")),
            context_drift_threshold=float(os.getenv("CONTEXT_DRIFT_THRESHOLD", "0.7")),
            auto_kill_loops=os.getenv("AUTO_KILL_LOOPS", "true").lower() == "true",
            force_prompt_quality=os.getenv("FORCE_PROMPT_QUALITY", "true").lower() == "true",
            enable_grounding=os.getenv("ENABLE_GROUNDING", "true").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_dir=os.getenv("LOG_DIR", "./marionette_logs"),
        )
    
    def validate(self) -> None:
        """Validate configuration settings."""
        if self.context_drift_threshold < 0 or self.context_drift_threshold > 1:
            raise ValueError("context_drift_threshold must be between 0 and 1")
        
        if self.debug_loop_window < 2:
            raise ValueError("debug_loop_window must be at least 2")
