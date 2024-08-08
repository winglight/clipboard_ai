# core/ai_interface.py

from openai import OpenAI
import aiohttp
import asyncio
import json
from PyQt6.QtCore import QObject, pyqtSignal

PROMPT_IMAGE="解释此图:"
PROMPT_TEXT="翻译并解释以下内容:"

class AIInterface(QObject):
    def __init__(self):
        super().__init__()
        self.current_config = None

    def set_config(self, config):
        self.current_config = config
        if self.current_config['type'] == "openai":
            # 初始化 OpenAI 客户端
            self.openai_client = OpenAI(api_key=self.current_config['api_key'])

    async def send_to_ai(self, content, prompt):
        if not self.current_config:
            return "No AI model selected"

        try:
            if self.current_config['type'] == "openai":
                response = await self.send_to_openai(content, prompt)
            elif self.current_config['type'] == "ollama":
                response = await self.send_to_ollama(content, prompt)
            else:
                return "Unsupported AI model type"

            print(response)
            return response
        except Exception as e:
            print(f"Error: {e}")
            return str(e)

    async def send_to_openai(self, content, prompt):
        # 构建消息列表
        messages = []

        # 添加系统角色的消息
        system_message = {"role": "system", "content": "You are a helpful assistant."}
        messages.append(system_message)

        # 添加用户输入的文本消息
        if prompt == PROMPT_IMAGE:
            user_message = {"role": "user", "content": f"{prompt}"}
        else:
            user_message = {"role": "user", "content": f"{prompt}\n\n{content}"}    
        messages.append(user_message)

        # 如果 content 是图片数据，则转换为多模态输入格式
        if prompt == PROMPT_IMAGE:
            # 构建图片消息
            image_message = {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{content}"}}
            ]}
            messages.append(image_message)

        try:
            response = self.openai_client.chat.completions.create(
                model=self.current_config['model'],
                messages=messages
            )
            return response.choices[0].message.content

        except Exception as e:
            print(f"Error communicating with OpenAI: {e}")
            return f"Error communicating with OpenAI: {e}"


    async def send_to_ollama(self, content, prompt):
        # print(content, prompt)
        other_settings = self.current_config['other_settings']
        print(f"Other settings: {other_settings}")
        url = other_settings.get('api_url', 'http://localhost:11434') + '/api/generate'
        print(url)
        
        payload = {
            "model": self.current_config['model'],
            "stream": False,
            "prompt": f"{prompt}\n\n{content}"
        }

        if prompt == PROMPT_IMAGE:
            payload["prompt"] = f"{prompt}"
            payload["images"] = [content]

        print(f"Sending to Ollama API: {payload}")
        # 添加其他可能的配置选项
        # if 'temperature' in other_settings:
        #     payload['temperature'] = float(other_settings['temperature'])
        # if 'top_p' in other_settings:
        #     payload['top_p'] = float(other_settings['top_p'])
        # if 'max_tokens' in other_settings:
        #     payload['max_tokens'] = int(other_settings['max_tokens'])

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                response_text = await response.text()
                print(f"Ollama API response: {response_text}")
                # print(f"Ollama API response: {response}")
                if response.status == 200:
                    result = json.loads(response_text)
                    print(f"Ollama API result: {result}")
                    return result['response']
                else:
                    raise Exception(f"Ollama API error: {response.status}")