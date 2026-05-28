"""
AI 摘要生成模块
通过 OpenRouter 调用免费大模型，为文章生成摘要，支持自动降级和重试
"""

import time

class AISummarizer:
    """AI摘要生成器，支持多模型自动降级"""

    # 默认模型降级列表（按优先级）
    DEFAULT_MODELS = [
        'qwen/qwen3-next-80b-a3b-instruct:free',  # Qwen3 Next 80B，原生中文
        'moonshotai/kimi-k2.6:free',               # Kimi K2.6，原生中文
        'google/gemma-4-31b-it:free',              # Gemma 4，多语言
        'deepseek/deepseek-v4-flash:free',         # DeepSeek V4 Flash
    ]

    @classmethod
    def generate_summary(cls, title: str, content: str, *,
                         api_key: str = '',
                         base_url: str = 'https://openrouter.ai/api/v1',
                         model: str = None,
                         models: list = None) -> str:
        """
        基于文章标题和内容生成中文摘要，自动尝试多个模型

        Args:
            title: 文章标题
            content: 文章正文
            api_key: OpenRouter API Key
            base_url: OpenRouter Base URL
            model: 单模型名（已弃用，请使用 models）
            models: 模型降级列表

        Returns:
            生成的中文摘要，失败返回空字符串
        """
        if not title and not content:
            return ''

        from openai import OpenAI

        # 截取内容
        content_text = (content or '').strip()
        if len(content_text) > 4000:
            content_text = content_text[:4000] + '…'

        prompt = f"""你是一个教育行业资讯编辑，请根据以下文章内容生成一段简洁的中文摘要（100字左右），
要求：
1. 提取文章核心信息
2. 语言简练、客观
3. 只输出摘要内容，不要多余的开场白或结束语

文章标题：{title}

文章内容：
{content_text}

摘要："""

        # 构建降级模型列表
        if models is None:
            models = cls.DEFAULT_MODELS
        if model:
            # 向后兼容：如果传了单模型，放在列表最前面
            if model not in models:
                models = [model] + list(models)

        client = OpenAI(base_url=base_url, api_key=api_key)

        for i, m in enumerate(models):
            try:
                response = client.chat.completions.create(
                    model=m,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=600,
                )

                summary = response.choices[0].message.content
                if summary and summary.strip():
                    if i > 0:
                        print(f"[AISummarizer] 降级后使用模型 {m} 成功")
                    return summary.strip()

                print(f"[AISummarizer] 模型 {m} 返回空内容")

            except Exception as e:
                if i < len(models) - 1:
                    print(f"[AISummarizer] 模型 {m} 失败，尝试下一个: {e}")
                    time.sleep(1)  # 等1秒再试下一个
                else:
                    print(f"[AISummarizer] 所有模型均失败，最后一个错误: {e}")

        return ''
