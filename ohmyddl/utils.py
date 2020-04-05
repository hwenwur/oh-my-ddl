import random
import string
import sys
import threading
from io import StringIO
from pathlib import Path
from typing import List

import requests

from . import DATA_DIR

# ---------------------------------------------


alias_table = {
    "毛泽东思想和中国特色社会主义理论体系概论*": "毛概",
    "马克思主义基本原理概论*": "马原",
    "中国近现代史纲要*": "中近纲",
    "数据结构与算法": "数据结构",
    "电路*": "电路",
    "数字电子技术": "数电",
    "模拟电子技术*": "模电"
}


def get_course_alias(course_name: str):
    keys = alias_table.keys()
    if course_name in keys:
        return alias_table[course_name]
    for k in keys:
        if k.endswith("*"):
            if course_name.startswith(k[:-1]):
                return alias_table[k]
        if k.startswith("*"):
            if course_name.endswith(k[1:]):
                return alias_table[k]
    return course_name


# ----------------------------------------------


def extract_string(source, start):
    """从source中提取第一个以start开头的字符串（单引号或双引号包围的）。
    """
    s = source.index(start)
    quote = source[s - 1]
    if quote == "'" or quote == '"':
        temp = source[s:]
        e = temp.index(quote)
        return temp[:e]
    else:
        raise ValueError


# -----------------------------------------------


def display_length(content):
    """中文单字长度计为2
    """
    content = str(content)
    length = len(content)
    for x in content:
        if 0x4e00 <= ord(x) <= 0x9fa5:
            length += 1
    return length


def print_width(stream: StringIO, content, width: int, align=0):
    content = str(content)
    content_len = display_length(content)
    if content_len <= width:
        a = (width - content_len) // 2
        if align == 0:
            # 居中
            stream.write(" " * a)
            stream.write(content)
            stream.write(" " * a)
        elif align == -1:
            # 左对齐
            stream.write(content)
            stream.write(" " * a * 2)
        elif align == 1:
            # 右对齐
            stream.write(" " * a * 2)
            stream.write(content)
        real_width = a * 2 + display_length(content)
        padding = width - real_width
        if padding > 0:
            stream.write(" " * padding)
    else:
        print(f"WARN content={content},length={content_len},width={width}")
        stream.write(content)


def table(data: List[List[str]], header: List[str]):
    col_max_len = [display_length(x) for x in header]
    for row in data:
        for i, col in enumerate(row):
            if display_length(col) > col_max_len[i]:
                col_max_len[i] = display_length(col)
    col_max_len = [2 + x for x in col_max_len]
    out = StringIO()
    # line 1
    out.write("+")
    for x in col_max_len:
        out.write("-" * x)
        out.write("+")
    out.write("\n")
    # line 2
    out.write("|")
    for i, h in enumerate(header):
        print_width(out, h, col_max_len[i])
        out.write("|")
    out.write("\n")
    # lin 3
    out.write("|")
    for x in col_max_len:
        out.write("-" * x)
        out.write("+")
    out.seek(out.tell() - 1)
    out.write("|\n")
    # line [4,len - 1)
    for row in data:
        out.write("|")
        for i, col in enumerate(row):
            print_width(out, col, col_max_len[i], align=-1)
            out.write("|")
        out.write("\n")
    # line len - 1, (the last line.)
    out.write("+")
    for x in col_max_len:
        out.write("-" * x)
        out.write("+")
    out.write("\n")

    return out.getvalue()

# -----------------------------------------------

def fetch_term_desc(term_id_list, term_id):
    if term_id == -1:
        return term_id_list[0][1]
    elif term_id:
        return "不限"
    for term in term_id_list:
        if term[0] == term_id:
            return term[1]
    return "未知"

# -----------------------------------------------

def geanerate_sid():
    """生成随机32字节小写字母。例如：ruzztvxjrptwryccrrgdbyuzkoozfgua
    """
    return ''.join([random.choice(string.ascii_lowercase) for x in range(32)])


def check_sid_format(sid):
    if sid is not None and isinstance(sid, str) and len(sid) == 32 and sid.isalpha():
        return True
    return False


# -----------------------------------------------

def check_available(blocking=False):
    """判断本程序是否可用。只有得到服务器明确回应后才关闭。
    """
    def print_message():
        print("=============================")
        print("      本程序不再开放使用        ")
        print("=============================")

    file = DATA_DIR / Path("disable")
    if file.exists():
        print_message()
        sys.exit(0)

    if not blocking:
        t = threading.Thread(target=check_available, args=(True, ))
        t.start()
        return
    url = "http://api.qiren.org/ohmyddl/can_i_use"
    try:
        r = requests.get(url)
        if r.status_code == 200 and r.text == "no":
            with file.open("a"):
                pass
            print_message()
            sys.exit(0)
    except:
        pass
