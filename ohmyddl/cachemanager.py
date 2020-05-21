import functools
import pickle
import time
from functools import wraps
import sqlite3

# from .models import ChaoxingUser


class CacheManager:
    def __init__(self, cache_id, data_file=None):
        """cache_id 缓存ID

        data_file 数据库保存路径
        """
        self.cache_id = cache_id
        self.conn = sqlite3.connect(":memory:" if data_file is None else data_file)
        CacheManager.create_table(self.conn)

    @staticmethod
    def create_table(conn: sqlite3.dbapi2.Connection):
        sql = "create table if not exists cache(id integer primary key, cache_id text, key_str text, update_time integer, val blob);"
        cursor = conn.cursor()
        cursor.execute(sql)
        cursor.close()

    def read_cache(self, key_str, ttl):
        cursor = self.conn.cursor()
        sql = "select update_time, val from cache where cache_id=? and key_str=? order by update_time desc;"
        cursor.execute(sql, (self.cache_id, key_str))
        t = cursor.fetchone()
        if t is not None:
            update_time, val = t
            current_time = time.time()
            if (current_time - update_time) < ttl:
                return val
        return None

    def write_cache(self, key_str, update_time, value):
        cursor = self.conn.cursor()
        sql = "insert into cache(cache_id, key_str, update_time, val)values(?,?,?,?);"
        cursor.execute(sql, (self.cache_id, key_str, int(update_time), value))
        self.conn.commit()
        cursor.close()


def cache(ttl, db_path):
    """缓存函数返回值。在 ttl 时间内重复调用某个函数（且str(参数)相同）会使用上次的返回值。
        @ttl 缓存过期时间，单位：秒。

        例子：\n
        @cache(60)\n
        def get_val(x, y, z):
            # something
            time.sleep(1)
            return [x, y, z]
        如果在60s内，重复调用该函数，并且x,y,z值相同的情况下，会直接使用上次运行的返回值。

        在上述例子中，执行10次get_val(1, 2, 3)只消耗约1秒时间。
    """
    def decorator(func):
        @wraps(func)
        def func_wraps(this_object, *vargs, **kwargs):
            # if not isinstance(this_object, ChaoxingUser):
            #     raise ValueError("you mush use this decorator in ChaoxingUser class")
            cache_id = this_object.userName
            key_str = func.__name__
            for x in vargs:
                key_str += str(x)

            for x in kwargs.keys():
                key_str += str(x)
                key_str += str(kwargs[x])
            cm = CacheManager(cache_id, db_path)
            old_val = cm.read_cache(key_str, ttl)
            if old_val is not None:
                result = pickle.loads(old_val)
            else:
                result = func(this_object, *vargs, **kwargs)
                val = pickle.dumps(result)
                cm.write_cache(key_str, time.time(), val)
            return result
        return func_wraps
    return decorator


def make_cache_decorator(db_path):
    return functools.partial(cache, db_path=db_path)
