from .models import ChaoxingUser, WorkInfo, CourseInfo
from .utils import get_course_alias
from pathlib import Path
from getpass import getpass
from tabulate import tabulate
from datetime import datetime
import argparse
import logging


def setup_logging(level=logging.ERROR):
    root = logging.getLogger()
    root.addHandler(logging.StreamHandler())
    root.setLevel(level)


def solve_account(relogin=False) -> ChaoxingUser:
    cache_file = ".user_data"
    if (not relogin) and Path(cache_file).exists():
        user = ChaoxingUser.load_from(cache_file)
    else:
        username = input("学号：")
        password = getpass("密码：")
        if len(username) != 8:
            print("学号错误")
            exit(1)
        user = ChaoxingUser(username, password)
    try:
        user.login()
        print("登录成功")
    except Exception as e:
        print(f"登录失败：{e}")
        exit(1)
    return user


def main():
    parser = argparse.ArgumentParser(description="超星学习通作业汇总。", prog="ohmyddl")
    parser.add_argument("-v", help="输出调试信息", action="store_true")
    parser.add_argument("-c", help="不使用已保存学号", action="store_true")
    parser.add_argument("-f", help="强制刷新（若10分钟内查询过，会优先使用缓存的数据）", action="store_true")
    args = parser.parse_args()
    if args.v:
        setup_logging(logging.DEBUG)
    else:
        setup_logging()
    
    user = solve_account(relogin=args.c)
    course_list = user.get_course_list(useCache=(not args.f))
    work_list = dict()
    for course in course_list:
        works = user.get_work_list(course.pageUrl, useCache=(not args.f))
        work_list[course.courseName] = works
    
    no_work_course = list()
    temp = list()
    for course_name in work_list.keys():
        course_alias = get_course_alias(course_name)
        works = work_list[course_name]
        unfinish_works = [x for x in works if x.workStatus == "待做"]
        if len(unfinish_works) == 0:
            no_work_course.append(course_alias)
            continue
        for work in unfinish_works:
            temp.append([
                course_alias + "-" + work.workName, 
                work.endTime if work.endTime is not None else "未知"
            ])
    temp.sort(key=lambda x: x[1].timestamp() if isinstance(x[1], datetime) else 0x7fffffff)
    print(f"当前学号：{user.userName}")
    print(tabulate(temp, headers=["名称", "截止时间"]))
    print()
    if len(no_work_course) != 0:
        print(f"{'、'.join(no_work_course)}没有未完成作业。")
    user.dump_to(".user_data")


if __name__ == "__main__":
    main()
