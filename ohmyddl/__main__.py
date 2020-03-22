from .models import ChaoxingUser, WorkInfo, CourseInfo
from .utils import get_course_alias
from pathlib import Path
from getpass import getpass
from tabulate import tabulate
from datetime import datetime
import logging


def setup_logging():
    root = logging.getLogger()
    root.addHandler(logging.StreamHandler())
    root.setLevel(logging.DEBUG)


def solve_account():
    cache_file = ".user_data"
    if Path(cache_file).exists():
        user = ChaoxingUser.load_from(cache_file)
    else:
        username = input("学号：")
        password = getpass("密码：")
        if len(username) != 8:
            print("学号错误")
            exit(0)
        user = ChaoxingUser(username, password)
    user.login()
    return user


def main():
    setup_logging()
    user = solve_account()
    course_list = user.get_course_list()
    work_list = dict()
    for course in course_list:
        works = user.get_work_list(course.pageUrl)
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
    print(tabulate(temp, headers=["名称", "截止时间"]))
    print()
    if len(no_work_course) != 0:
        print(f"{'、'.join(no_work_course)}没有未完成作业。")
    user.dump_to(".user_data")


if __name__ == "__main__":
    main()
