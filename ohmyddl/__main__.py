import argparse
import logging
import sys
from datetime import datetime
from getpass import getpass
from pathlib import Path

from . import DATA_DIR
from .exceptions import PasswordError
from .models import ChaoxingUser, CourseInfo, WorkInfo
from .utils import fetch_term_desc, get_course_alias, table, check_available

DATA_FILE = DATA_DIR / ".user_data"
logger = logging.getLogger(__name__)
check_available()


def setup_logging(level=logging.ERROR):
    root = logging.getLogger()
    root.addHandler(logging.StreamHandler())
    root.setLevel(level)


def solve_account(relogin=False) -> ChaoxingUser:
    if (not relogin) and DATA_FILE.exists():
        logging.debug(f"read config from {DATA_FILE}")
        user = ChaoxingUser.load_from(str(DATA_FILE))
    else:
        username = input("学号：")
        password = getpass("密码：")
        if len(username) != 8:
            print("学号错误")
            exit(1)
        user = ChaoxingUser(username, password)
        try:
            user.login()
        except PasswordError:
            print("学号或密码错误")
            exit(0)
    try:
        if not user.is_login:
            user.login()
        print("登录成功")
    except Exception as e:
        print(f"登录失败：{e}")
        exit(1)
    return user


def save_user_data(user):
    parent = DATA_FILE.parent
    parent.mkdir(exist_ok=True)
    user.dump_to(str(DATA_FILE))


def main():
    prog = "ohmyddl.exe" if sys.platform == "win32" else "ohmyddl"
    parser = argparse.ArgumentParser(description="超星学习通作业汇总。", prog=prog)
    parser.add_argument("-c", help="不使用已保存学号", action="store_true")
    parser.add_argument(
        "-f", help="强制刷新（若10分钟内查询过，会优先使用缓存的数据）", action="store_true")
    parser.add_argument(
        "-t", help="学期ID，默认使用当前学期。格式：20192表示2019冬季学期。", type=int)
    parser.add_argument("-v", help="输出调试信息", action="store_true")
    args = parser.parse_args()
    if args.v:
        setup_logging(logging.DEBUG)
    else:
        setup_logging()

    user = solve_account(relogin=args.c)
    term_id = args.t if args.t else -1
    disable_cache = args.f
    logger.info(f"disable_cache: {disable_cache}")
    term_id_list = user.get_term_id_list(disable_cache=disable_cache)
    course_list = user.get_course_list(
        term_id=term_id, disable_cache=disable_cache)
    work_list = dict()
    for course in course_list:
        works = user.get_work_list(course.pageUrl, disable_cache=disable_cache)
        work_list[course.courseName] = works

    no_work_course = list()
    tab_content = list()
    for course_name in work_list.keys():
        course_alias = get_course_alias(course_name)
        works = work_list[course_name]
        unfinish_works = [x for x in works if x.workStatus == "待做"]
        if len(unfinish_works) == 0:
            no_work_course.append(course_alias)
            continue
        for work in unfinish_works:
            tab_content.append([
                course_alias + "-" + work.workName,
                work.endTime if work.endTime is not None else "未知"
            ])
    tab_content.sort(key=lambda x: x[1].timestamp() if isinstance(x[1], datetime) else 0x7fffffff)
    print(f"当前学号：{user.userName}")
    print(f"当前学期：{fetch_term_desc(term_id_list, term_id)}")
    print(table(tab_content, ["名称", "截止时间"]))
    print()
    if len(no_work_course) != 0:
        print(f"{'、'.join(no_work_course)}没有未完成作业。")
    save_user_data(user)


def web():
    from . import server
    import webbrowser
    webbrowser.open("http://localhost:5986/")
    server.main()


if __name__ == "__main__":
    main()
