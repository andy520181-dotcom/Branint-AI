import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM 配置
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    dashscope_api_key: str = ""

    # NOTE: MVP 阶段固定 DeepSeek，Phase 2 根据用户订阅级别动态切换
    default_model: str = "deepseek/deepseek-chat"
    pro_model: str = "gpt-4o"

    # 应用
    secret_key: str = "dev-secret-key"
    frontend_url: str = "http://localhost:3000"

    # 腾讯 QQ 邮箱 SMTP（用于发送 OTP 验证码）
    # NOTE: smtp_password 是『授权码』，不是 QQ 登录密码
    #   获取路径：QQ 邮箱 → 设置 → 账户 → POP3/SMTP 服务 → 开启 → 生成授权码
    smtp_host: str = "smtp.qq.com"
    smtp_port: int = 465        # SSL 加密端口
    smtp_user: str = ""          # 你的 QQ 邮箱地址
    smtp_password: str = ""      # 邮箱授权码（非登录密码）
    smtp_from_name: str = "Brandclaw AI"

    # JWT 认证
    jwt_secret: str = "woloong-jwt-secret-change-in-prod"
    jwt_expire_days: int = 30



    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# NOTE: LiteLLM 需要通过环境变量获取各厂商 API Key
# 在应用启动时统一注入，避免在各处重复设置
def configure_litellm_keys() -> None:
    """将配置中的 API Key 统一注入环境变量供 LiteLLM 读取"""
    if settings.deepseek_api_key:
        os.environ["DEEPSEEK_API_KEY"] = settings.deepseek_api_key
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
