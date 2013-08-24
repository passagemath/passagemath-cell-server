"""
SQLAlchemy Database Adapter
---------------------------
"""

"""
System library imports
"""
import json, uuid
from datetime import datetime
import string
import tornado
import tornado.httpclient
"""
Generic database adapter import
"""
import db
import urllib
valid_query_chars = set(string.letters+string.digits+"-")
from functools import partial

class DB(db.DB):
    """
    :arg URL str: the URL for the key-value store
    """

    def __init__(self, url):
        self.url = url

    def new_exec_msg(self, code, language, interacts, callback):
        """
        See :meth:`db.DB.new_exec_msg`
        """
        post_data = { 'code': code, 'language': language, 'interacts': interacts } #A dictionary of your post data
        body = urllib.urlencode(post_data) #Make it into a post request
        http_client = tornado.httpclient.AsyncHTTPClient()
        exec_callback = partial(self.return_exec_msg_id, callback)
        http_client.fetch(self.url, exec_callback, method="POST", body=body, headers={"Accept": "application/json"})

    def return_exec_msg_id(self, callback, response):
        if response.code != 200:
            raise StandardError("Error in response")
        callback(json.loads(response.body)['query'])

    def get_exec_msg(self, key, callback):
        """
        See :meth:`db.DB.get_exec_msg`
        """
        http_client = tornado.httpclient.AsyncHTTPClient()
        exec_callback = partial(self.return_exec_msg_code, callback)
        http_client.fetch(self.url+"?q=%s"%key, exec_callback, method="GET", headers={"Accept": "application/json"})

    def return_exec_msg_code(self, callback, response):
        if response.code == 200:
            code, language, interacts = json.loads(response.body)
        else:
            raise LookupError("Code lookup produced error")
        callback(code, language, interacts)
