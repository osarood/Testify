"""
Client-server setup for evenly distributing tests across multiple processes.
See the test_runner_server module.
"""
import urllib2
try:
    import simplejson as json
    _hush_pyflakes = [json]
    del _hush_pyflakes
except ImportError:
    import json
import time
import logging

import test_discovery
from test_runner import TestRunner


class TestRunnerClient(TestRunner):
    def __init__(self, *args, **kwargs):
        self.connect_addr = kwargs.pop('connect_addr')
        self.runner_id = kwargs.pop('runner_id')
        self.revision = kwargs['options'].revision

        self.retry_limit = kwargs['options'].retry_limit
        self.retry_interval = kwargs['options'].retry_interval
        self.reconnect_retry_limit = kwargs['options'].reconnect_retry_limit
        logging.warning('===== INIT CLIENT ====')
        print ' ----- IN TestRunnerClient ------'
        super(TestRunnerClient, self).__init__(*args, **kwargs)
        fName = '/nail/home/osarood/logs/latency_'+str(self.runner_id)
        self.fd_latency = open(fName,'w')
        logging.warning('---- FILE CREATED --- f->'+str(fName))

    def discover(self):
        finished = False
        first_connect = True
        while not finished:
            st_time = time.time()
            #class_path, methods, finished = self.get_next_tests(
            d_list = self.get_next_tests(
                retry_limit=(self.retry_limit if first_connect else self.reconnect_retry_limit),
                retry_interval=self.retry_interval,
            )
            #python.warning('---> req sent-> '+str(st_time)+' req rec->'+str(time.time())+' ->'+class_path)
            first_connect = False
            #if class_path and methods:
            for d_ins in d_list:
                print 'rrr d_ins->',d_ins
                class_path = d_ins.get('class')
                methods = d_ins.get('methods')
                finished = d_ins.get('finished')
                module_path, _, class_name = class_path.partition(' ')

                klass = test_discovery.import_test_class(module_path, class_name)
                yield klass(name_overrides=methods)

    def get_next_tests(self, retry_interval=2, retry_limit=0):
        try:
            if self.revision:
                url = 'http://%s/tests?runner=%s&revision=%s' % (self.connect_addr, self.runner_id, self.revision)
            else:
                url = 'http://%s/tests?runner=%s' % (self.connect_addr, self.runner_id)
            st_time = time.time()*1000
            response = urllib2.urlopen(url)
            res_time = time.time()*1000
            d_list = json.load(response)
            #class_path = d.get('class')
            self.fd_latency.write(str(st_time)+' '+str(res_time)+' '+str(res_time-st_time)+'\n')
            self.fd_latency.flush()
            logging.warning('-- 11 ---> req sent-> '+str(st_time)+' req rec->'+str(res_time)+' json->'+str(time.time()))
            #return (class_path, d.get('methods'), d['finished'])
            return d_list
        except urllib2.HTTPError, e:
            logging.warning("Got HTTP status %d when requesting tests -- bailing" % (e.code))
            return None, None, True
        except urllib2.URLError, e:
            if retry_limit > 0:
                logging.warning("Got error %r when requesting tests, retrying %d more times." % (e, retry_limit))
                time.sleep(retry_interval)
                return self.get_next_tests(retry_limit=retry_limit-1, retry_interval=retry_interval)
            else:
                return None, None, True # Stop trying if we can't connect to the server.
