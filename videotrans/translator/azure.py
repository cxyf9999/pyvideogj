# -*- coding: utf-8 -*-
import re
import time
import httpx
from openai import AzureOpenAI
from videotrans.configure import config
from videotrans.util import tools

def trans(text_list, target_language="English", *, set_p=True,inst=None,stop=0,source_code=None):
    """
    text_list:
        可能是多行字符串，也可能是格式化后的字幕对象数组
    target_language:
        目标语言
    set_p:
        是否实时输出日志，主界面中需要
    """
    proxies = None
    serv = tools.set_proxy()
    if serv:
        proxies = {
            'http://': serv,
            'https://': serv
        }

    # 翻译后的文本
    target_text = []
    index = 0  # 当前循环需要开始的 i 数字,小于index的则跳过
    iter_num = 0  # 当前循环次数，如果 大于 config.settings.retries 出错
    err = ""
    while 1:
        if config.current_status!='ing' and config.box_trans!='ing':
            break
        if iter_num >= config.settings['retries']:
            raise Exception(
                f'{iter_num}{"次重试后依然出错" if config.defaulelang == "zh" else " retries after error persists "}:{err}')
        iter_num += 1
        print(f'第{iter_num}次')
        if iter_num > 1:
            if set_p:
                tools.set_process(
                    f"第{iter_num}次出错重试" if config.defaulelang == 'zh' else f'{iter_num} retries after error')
            time.sleep(5)


        # 整理待翻译的文字为 List[str]
        if isinstance(text_list, str):
            source_text = text_list.strip().split("\n")
        else:
            source_text = [f"{t['line']}\n{t['time']}\n{t['text']}" for t in text_list]

        client = AzureOpenAI(
            api_key=config.params["azure_key"],
            api_version="2023-05-15",
            azure_endpoint=config.params["azure_api"],
            http_client=httpx.Client(proxies=proxies)
        )
        split_size = int(config.settings['trans_thread'])
        split_source_text = [source_text[i:i + split_size] for i in range(0, len(source_text), split_size)]

        for i,it in enumerate(split_source_text):
            if config.current_status != 'ing' and config.box_trans != 'ing':
                break
            if i<index:
                continue
            if stop>0:
                time.sleep(stop)
            try:
                source_length = len(it)
                message = [
                    {'role': 'system',
                     'content': config.params["azure_template"].replace('{lang}', target_language)},
                    {'role': 'user', 'content': "\n".join(it)},
                ]

                config.logger.info(f"\n[Azure start]待翻译:{message=}")
                response = client.chat.completions.create(
                    model=config.params["azure_model"],
                    messages=message
                )

                config.logger.info(f'Azure 返回响应:{response}')

                if response.choices:
                    result = response.choices[0].message.content.strip()
                elif response.data and response.data['choices']:
                    result = response.data['choices'][0]['message']['content'].strip()
                else:
                    raise Exception(f"[error]:Azure {response}")
                result=result.strip().replace('&#39;','"').replace('&quot;',"'")
                if inst and inst.precent < 75:
                    inst.precent += round((i + 1) * 5 / len(split_source_text), 2)
                if set_p:
                    tools.set_process( result, 'subtitle')
                    tools.set_process(config.transobj['starttrans']+f' {i*split_size+1} ')
                else:
                    tools.set_process(result, func_name="set_fanyi")
                target_text.append(result)
                iter_num=0
            except Exception as e:
                error = str(e)+f'目标文件夹下{source_code}.srt文件第{(i*split_size)+1}条开始的{split_size}条字幕'
                err = error
                index = i
                break
        else:
            break


    if isinstance(text_list, str):
        return "\n".join(target_text)

    target = tools.get_subtitle_from_srt("\n\n".join(target_text),is_file=False)
    return target
