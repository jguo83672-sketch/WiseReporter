"""
AI 摘要生成模块
通过 OpenRouter 调用百度千帆文本模型，为文章生成摘要
"""


class AISummarizer:
    """AI摘要生成器"""

    @classmethod
    def generate_summary(cls, title: str, content: str, *,
                         api_key: str = '',
                         base_url: str = 'https://openrouter.ai/api/v1',
                         model: str = 'baidu/cobuddy:free') -> str:
        """
        基于文章标题和内容生成中文摘要

        Args:
            title: 文章标题
            content: 文章正文
            api_key: OpenRouter API Key
            base_url: OpenRouter Base URL
            model: 模型名称

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

        prompt = f"""你是一个教育行业资讯编辑，请根据以下文章内容生成一段简洁的中文摘要（100-200字），
要求：
1. 提取文章核心信息
2. 语言简练、客观
3. 只输出摘要内容，不要多余的开场白或结束语

文章标题：{title}

文章内容：
{content_text}

摘要："""

        try:
            client = OpenAI(base_url=base_url, api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=600,
            )

            summary = response.choices[0].message.content
            if summary:
                return summary.strip()
            return ''

        except Exception as e:
            print(f"[AISummarizer] 摘要生成失败: {e}")
            return ''
