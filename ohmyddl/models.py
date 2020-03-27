import requests
import logging
import lxml.etree
from collections import namedtuple
import pickle
from datetime import datetime
import time
from typing import List, Dict, Tuple
from .utils import extract_string


WorkInfo = namedtuple("WorkInfo", ["workName", "startTime", "endTime", "workStatus"])
CourseInfo = namedtuple("CourseInfo", ["pageUrl", "courseName", "teacherName", "courseSeq"])


class ChaoxingUser:
    HTTP_HEADERS = {
        # dummy user-agent
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13) AppleWebKit/603.1.13 (KHTML, like Gecko) Version/10.1 Safari/603.1.13',
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,zh-TW;q=0.7"
    }
    CACHE_EXPIRE_TIME = 600

    def __init__(self, userName, password):
        self.userName = userName
        self.password = password
        self.session = requests.Session()
        self.session.headers.update(self.HTTP_HEADERS)
        self._logger = logging.getLogger(__name__)
        self._cache_table : Dict[str, Tuple[List, float]]= dict()

    def http_request(self, url, method, params=None, data=None, referer=None, auto_retry=3) -> requests.models.Response:
        session = self.session
        if referer:
            session.headers.update({
                "Referer": referer
            })
        request = getattr(session, method.lower())
        while True:
            try:
                r = request(url, params=params, data=data)
                return r
            except requests.exceptions.RequestException as e:
                self._logger.error(f"请求时发生错误：{e}")
                if isinstance(e, ValueError):
                    raise
                if auto_retry > 0:
                    time.sleep(1)
                    auto_retry -= 1
                    self._logger.error(f"自动重试: {auto_retry}")
                else:
                    raise

    def http_get(self, url, **kargs):
        return self.http_request(url, "get", **kargs)

    def http_post(self, url, **kargs):
        return self.http_request(url, "post", **kargs)

    def _read_cache(self, key, expire_time=None):
        if key in self._cache_table.keys():
            cached_time = self._cache_table[key][1]
            if expire_time is None:
                expire_time = self.CACHE_EXPIRE_TIME
            if (time.time() - cached_time) < expire_time:
                return self._cache_table[key][0].copy()
        return None

    def _write_cache(self, key, val: list):
        self._cache_table[key] = (val.copy(), time.time())

    @property
    def is_login(self):
        r = self.http_get("http://www.elearning.shu.edu.cn/topjs?index=1")
        if "afterLogin" in r.text:
            return True
        elif "beforLogin" in r.text:
            return False
        else:
            self._logger.error(f"无法判断登录状态。status_code:{r.status_code},text:\n{r.text}")
            raise RuntimeError("无法判断登录状态")

    def login(self):
        # step 1
        r = self.http_get("http://shu.fysso.chaoxing.com/sso/shu", referer="http://www.elearning.shu.edu.cn/portal")
        if r.url.startswith("http://www.elearning.shu.edu.cn/sso/logind"):
            self._logger.debug("use oauth to login")
        elif r.url == "https://oauth.shu.edu.cn/login":
            # step 2
            self._logger.debug("use username and password to login")
            form = {
                "username": self.userName,
                "password": self.password,
                "login_submit": "登录/Login"
            }
            r = self.http_post("https://oauth.shu.edu.cn/login", data=form)
            assert r.url.startswith("http://www.elearning.shu.edu.cn/sso/logind"), f"unexpected url(2): {r.url}"
        else:
            error = f"login failed. unexpected url(1): {r.url}"
            self._logger.critical(error)
            raise RuntimeError(error)

        # step 3
        # r.url start with http://www.elearning.shu.edu.cn/sso/logind
        html = lxml.etree.HTML(r.text)
        form = html.xpath("//form[@id='userLogin']")[0]
        inputs = form.xpath("input[@type='hidden']")
        request_url = form.attrib["action"]
        data = dict()
        for i in inputs:
            name = i.attrib["name"]
            value = i.attrib["value"]
            data[name] = value
            if name == "fid":
                fid = value
        r = self.http_post(request_url, data=data)
        assert r.url == "http://www.elearning.shu.edu.cn/portal", f"unexpected url(3): {r.url}"

        # step 4
        params = {"fid": fid}
        self.http_get("http://www.elearning.shu.edu.cn/setcookie.jsp", params=params)
    
    def get_term_id_list(self, use_cache=600) -> List[Tuple[int, str]]:
        """获取学期id
        @return [(20193, "2019-2020学年春季学期"), (20192, "2019-2020学年秋季学期"), ...]
        """
        cache_key = "term_id_list"
        if t := self._read_cache(cache_key, expire_time=use_cache):
            self._logger.info("get_term_id_list use cache value.")
            return t
        # step 1 获取请求url
        r = self.http_get("http://i.mooc.elearning.shu.edu.cn/space/index.shtml", referer="http://www.elearning.shu.edu.cn/portal")
        url = extract_string(r.text, "http://www.elearning.shu.edu.cn/courselist/study?s=")
        self._logger.info(f"get_term_id_list request url: {url}")
        # step 2
        result = list()
        r = self.http_get(url)
        html = lxml.etree.HTML(r.text)
        term_list_li = html.xpath("//ul[@class='zse_ul']/li[@class='zse_li']/a")
        for x in term_list_li:
            year = x.xpath("@data_year")[0]
            term = x.xpath("@data_term")[0]
            comment = x.text.strip()
            try:
                term_id = int(year + term)
            except ValueError as e:
                self._logger.error(f"term_id转换错误：{e}, 略过：{comment}")
                term_id = -2
            result.append((term_id, comment))
        result.sort(key=lambda x: x[0], reverse=True)
        self._logger.info(f"term_id: {result}")
        self._write_cache(cache_key, result)
        return result

    def get_course_list(self, term_id: int=-1, use_cache: int=600) -> List[CourseInfo]:
        """获取课程列表
        @params term_id 学期ID，-1表示当前学期, 0表示所有课程。20193表示2019-2020春季学期。

        @return [CourseInfo(pageUrl='', courseName='', teacherName='', courseSeq=''), ...]
        """
        cache_key = "course_list_" + str(term_id)
        if t := self._read_cache(cache_key, expire_time=use_cache):
            self._logger.info("get_course_list use cache value.")
            return t
        # step 1 获取请求url
        r = self.http_get("http://i.mooc.elearning.shu.edu.cn/space/index.shtml", referer="http://www.elearning.shu.edu.cn/portal")
        url = extract_string(r.text, "http://www.elearning.shu.edu.cn/courselist/study?s=")
        self._logger.info(f"get_course_list request url: {url}")

        # step 2
        term_id_list = self.get_term_id_list()
        request_data = {
            "year": "0",
            "term": "0",
            "showContent": "000"
        }
        if term_id == -1:
            term_id = term_id_list[0][0]
        if term_id // 10000 == 2:
            request_data["year"] = str(term_id // 10)
            request_data["term"] = str(term_id % 10)
        elif term_id != 0:
            self._logger.error(f"invalid term_id: {term_id}")
            raise ValueError(f"invalid term_id: {term_id}")
        self._logger.debug(f"get_course_list term_id: {term_id}")

        r = self.http_get(url, params=request_data)
        html = lxml.etree.HTML(r.text)
        courses = html.xpath("//li[contains(@class, 'zmy_item')]")
        course_list = list()
        for c in courses:
            course_list.append(CourseInfo(
                pageUrl=c.xpath("a/@href")[0],
                courseName=c.xpath("dl/dt[@name='courseNameHtml']")[0].text.strip(),
                teacherName=c.xpath("dl/dd[@name='userNameHtml']")[0].text.strip(),
                courseSeq=c.xpath("dl/dt/span/text()")[0].strip()[1:-1]
            ))
        self._write_cache(cache_key, course_list)
        return course_list

    def get_work_list(self, page_url, use_cache=600) -> List[WorkInfo]:
        """获取作业列表
        """
        # 注意此处：如果缓存结果为 [] 的话，也应该使用。
        cache_key = "work_list_" + page_url
        if (t := self._read_cache(cache_key, expire_time=use_cache)) is not None:
            self._logger.info("get_work_list use cache value")
            return t
        result = list()
        r = self.http_get(page_url)
        # step 1 获取url
        request_path = extract_string(r.text, "/work/getAllWork?")
        request_url = "http://mooc1.elearning.shu.edu.cn" + request_path
        self._logger.info(f"get_work_list request_url: {request_url}")
        # step 2
        r = self.http_get(request_url)
        html = lxml.etree.HTML(r.text)
        works = html.xpath("//div[@class='ulDiv']/ul/li")
        self._logger.info(f"get_work_list len(works) = {len(works)}")
        for x in works:
            workName = x.xpath("div[@class='titTxt']/p/a/@title")[0]
            t = x.xpath("div[@class='titTxt']/span[@class='pt5']/text()")
            t = [i.strip() for i in t]
            time_format = r"%Y-%m-%d %H:%M"
            startTime = datetime.strptime(t[0], time_format) if t[0] else None
            endTime = datetime.strptime(t[1], time_format) if t[1] else None
            workStatus = x.xpath("div[@class='titTxt']/span/strong")[0].text.strip()
            result.append(WorkInfo(
                workName=workName,
                startTime=startTime,
                endTime=endTime,
                workStatus=workStatus
            ))
        self._write_cache(cache_key, result)
        return result

    def dump_to(self, file_path):
        self._logger.debug(f"dump object to {file_path}")
        with open(file_path, "wb") as f:
            pickle.dump(self, f)
    
    @staticmethod
    def load_from(file_path):
        with open(file_path, "rb") as f:
            return pickle.load(f)
