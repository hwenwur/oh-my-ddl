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
