import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ─── 数据库 ──────────────────────────────────────
    # NOTE: 使用 postgresql:// 格式；db/database.py 内部自动转换为 asyncpg DSN
    database_url: str = "postgresql://branin_user:password@localhost:5432/branin_db"

    # ─── 阿里云 OSS ──────────────────────────────────
    oss_access_key_id: str = ""
    oss_access_key_secret: str = ""
    oss_bucket_name: str = "branin-assets"
    oss_endpoint: str = "oss-cn-guangzhou.aliyuncs.com"
    # NOTE: 公共读 Bucket 的访问域名，上传后直接拼接文件路径即得公开 URL
    oss_public_url: str = "https://branin-assets.oss-cn-guangzhou.aliyuncs.com"

    # LLM 配置
    deepseek_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    dashscope_api_key: str = ""
    tavily_api_key: str = ""  # NOTE: Wacksman 市场研究 Agent 联网检索能力
    volc_accesskey: str = ""
    volc_secretkey: str = ""
    
    # NLP API Keys
    baidu_nlp_app_id: str = ""
    baidu_nlp_api_key: str = ""
    baidu_nlp_secret_key: str = ""
    aliyun_access_key: str = ""
    aliyun_nlp_secret: str = ""

    # NOTE: Kling AI 视频生成（快手可图）
    # 申请地址：https://klingai.kuaishou.com → API管理 → 创建密鑰
    # 鉴权方式：用 access_key + secret_key 动态生成 JWT Token
    kling_access_key: str = ""
    kling_secret_key: str = ""

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
    smtp_from_name: str = "Branin AI"

    # JWT 认证
    jwt_secret: str = "woloong-jwt-secret-change-in-prod"
    jwt_expire_days: int = 30

    # 单条用户输入（user_prompt）最大字符数；正式上线可与 DB/对象存储及模型上下文策略一并调整（环境变量 USER_PROMPT_MAX_CHARS）
    user_prompt_max_chars: int = 500_000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# NOTE: LiteLLM 需要通过环境变量获取各厂商 API Key
# 在应用启动时统一注入，避免在各处重复设置
def configure_litellm_keys() -> None:
    """将配置中的 API Key 统一注入环境变量供 LiteLLM 及各 SDK 读取"""
    if settings.deepseek_api_key:
        os.environ["DEEPSEEK_API_KEY"] = settings.deepseek_api_key
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key
    if settings.google_api_key:
        # NOTE: LiteLLM 使用 GEMINI_API_KEY；Google GenAI SDK 使用 GOOGLE_API_KEY
        # 两个都注入，确保所有 SDK 均可读取
        os.environ["GEMINI_API_KEY"] = settings.google_api_key
        os.environ["GOOGLE_API_KEY"] = settings.google_api_key
    if settings.volc_accesskey:
        os.environ["VOLC_ACCESSKEY"] = settings.volc_accesskey
    if settings.volc_secretkey:
        os.environ["VOLC_SECRETKEY"] = settings.volc_secretkey
    if settings.tavily_api_key:
        os.environ["TAVILY_API_KEY"] = settings.tavily_api_key
