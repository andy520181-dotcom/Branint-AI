import asyncio
from dotenv import load_dotenv
load_dotenv()
from app.config import settings
from app.service.llm_provider import call_llm_with_tools
import json

async def test():
    dispatch_tool = {
        "type": "function",
        "function": {
            "name": "dispatch_visual_intent",
            "description": "评估当前的视觉需求，决定是否需要生成图片、生成视频或发起反问。你只能从背景档案中提取生成所需的prompt！如果无需生成，则让tasks为空数组。",
            "parameters": {
                "type": "object",
                "properties": {
                    "need_clarify": {"type": "boolean"},
                    "clarify_question": {"type": "string"},
                    "image_tasks": {"type": "array"}
                }
            }
        }
    }
    
    preflight_messages = [{"role": "user", "content": "设计个logo"}]
    
    print("Sending preflight to deepseek...")
    try:
        raw, tool_calls = await call_llm_with_tools(
            messages=preflight_messages,
            tools=[dispatch_tool],
            tool_choice={"type": "function", "function": {"name": "dispatch_visual_intent"}},
            model=settings.default_model,
        )
        print("Raw:", raw)
        print("Tool Calls:", json.dumps(tool_calls, indent=2))
    except Exception as e:
        print("Exception:", e)

asyncio.run(test())
