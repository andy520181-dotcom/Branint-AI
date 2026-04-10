import re

with open("backend/app/service/agent_orchestrator.py", "r") as f:
    lines = f.readlines()

new_lines = []
in_decision_block = False
i = 0
while i < len(lines):
    line = lines[i]
    if "# NOTE: 将高耗时的 JSON 路由决策放进无阻塞的后台 task" in line:
        new_lines.append(line)
        new_lines.append('            plan_accumulated = ""\n')
        new_lines.append('            \n')
        new_lines.append('            while True:\n')
        new_lines.append('                decision_task = asyncio.create_task(run_ogilvy_decision(effective_prompt, conversation_history))\n')
        new_lines.append('                decision = await decision_task\n')
        new_lines.append('                action = decision.get("action", "none")\n')
        new_lines.append('                args = decision.get("args", {})\n\n')
        new_lines.append('                if action == "conduct_brand_diligence":\n')
        new_lines.append('                    search_query = args.get("search_query", "品牌全景研究")\n')
        new_lines.append('                    logger.info("品牌顾问 — 触发前置初调: %s", search_query)\n')
        new_lines.append('                    diligence_text = "\\n> 🔎 正在为您抽调该赛道的底层商业架构与最新市场动态...\\n\\n"\n')
        new_lines.append('                    plan_accumulated += diligence_text\n')
        new_lines.append('                    yield _sse_raw("agent_chunk", json.dumps({"id": "consultant_plan", "chunk": diligence_text}, ensure_ascii=False))\n')
        new_lines.append('                    try:\n')
        new_lines.append('                        search_result = await execute_tavily_search(search_query)\n')
        new_lines.append('                    except Exception as e:\n')
        new_lines.append('                        logger.error("初调搜索失败: %s", e)\n')
        new_lines.append('                        search_result = "搜索暂无确切开源结果或网络异常。"\n')
        new_lines.append('                    dossier = f"\\n[核心参谋部·品牌背调档案]\\n全网搜索关键词：{search_query}\\n情报摘要：\\n{search_result}\\n\\n"\n')
        new_lines.append('                    project_context["brand_dossier"] = dossier\n')
        new_lines.append('                    effective_prompt += f"\\n\\n{dossier}\\n(以上为搜集的最新背景资料，请基于此立刻下发路由或流转)"\n')
        new_lines.append('                    plan_accumulated += "> 📊 架构抽调完成。\\n\\n"\n')
        new_lines.append('                    yield _sse_raw("agent_chunk", json.dumps({"id": "consultant_plan", "chunk": "> 📊 架构抽调完成。\\n\\n"}, ensure_ascii=False))\n')
        new_lines.append('                    continue\n\n')
        
        # Skip the original definition
        i += 9
        in_decision_block = True
        continue
        
    if in_decision_block:
        if "plan_handoff = plan_text" in line:
            new_lines.append("    " + line)
            new_lines.append('                break\n')
            in_decision_block = False
            i += 1
            continue
        elif line.startswith("            ") and line.strip() != "":
            # Indent existing block by 4 spaces
            new_lines.append("    " + line)
            i += 1
            continue
        elif line.strip() == "":
            new_lines.append(line)
            i += 1
            continue
            
    new_lines.append(line)
    i += 1

with open("backend/app/service/agent_orchestrator.py", "w") as f:
    f.writelines(new_lines)
print("Patch applied.")
