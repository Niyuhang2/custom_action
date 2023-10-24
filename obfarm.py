# -*- coding: utf-8 -*-
# owner: niyuhang.nyh
import copy
import os
import sys
import time
import oss2
import json
import requests
from enum import Enum

OUTPUT = {}
RESULT_FILE_KEY = "farm/results/"
TASK_QUEUE_FILE_KEY = "farm/jobs/{}.json"


class OssProxy:

    def __init__(self, bucket, ak, sk, endpoint=""):
        auth = oss2.Auth(ak, sk)
        self.bucket = oss2.Bucket(auth, endpoint, bucket)

    def list_buckets(self, path):
        res = []
        for oss_object in self.bucket.list_objects(prefix=path, delimiter="/").object_list:
            if oss_object:
                res.append(oss_object.key)
        return res

    def delete_object(self, key):
        self.bucket.delete_object(key)

    def get_object(self, key, _range=None):
        result = self.bucket.get_object(key, byte_range=_range).read()
        return result

    def append_object(self, key, position, content):
        """追加文件内容"""
        result = self.bucket.append_object(key, position, content)
        return result

    def put_object(self, key, content):
        """修改文件内容"""
        result = self.bucket.put_object(key, content)
        return result

    def get_object_meta(self, key):
        """修改文件内容"""
        result = self.bucket.get_object_meta(key)
        return result


class TaskStatusEnum(Enum):
    submitting = 0
    pending = 1
    running = 2
    stopping = 3
    success = 4
    fail = -1
    kill = -2
    timeout = -3
    submit_task_fail = -4


def request(method, url, params=None, payload=None, timeout=10, data=None, without_check_status=False):
    params = params or {}
    try:
        response = requests.request(
            method,
            url,
            params=params,
            json=payload,
            data=data,
            timeout=timeout
        )
        if not without_check_status and response.status_code >= 300:
            try:
                msg = response.json()["msg"]
            except:
                msg = response.text
            print("[ERROR] 错误信息:{}".format(msg))
            exit(1)
        return response
    except Exception:
        import traceback
        traceback.print_exc()
        print("请求失败，出现异常，请联系管理人员处理")
        if not without_check_status:
            exit(1)


def monitor_tasks(oss_proxy: OssProxy, github_pipeline_id, timeout):
    end_time = time.time() + int(timeout)
    # 监控任务，并且不断的打印输出，直到任务结束
    end = 0
    end_task = False
    print("{}OUTPUT{}".format("-"*20, "-"*20))
    while time.time() <= end_time:
        # 每次刷新20
        if end_task is True:
            pass
        # 检查任务是不是结束了
        task_data = get_task_res(oss_proxy, github_pipeline_id)
        if task_data:
            end_task = True
        output = get_task_stage_output(oss_proxy, github_pipeline_id, end)
        if output is None:
            continue
        end += len(output)
        need_print_output = output.decode()
        if need_print_output and need_print_output.strip():
            print(need_print_output, end="")

        time.sleep(1)
        if task_data is not None:
            task_status = int(task_data["status"])
            if task_status <= TaskStatusEnum.fail.value:
                print(TaskStatusEnum._value2member_map_[task_status])
                OUTPUT.update({"success": -1})
                return False
            elif task_status >= TaskStatusEnum.success.value:
                print(TaskStatusEnum._value2member_map_[task_status])
                OUTPUT.update({"success": 1})
                return True

        time.sleep(5)
    else:
        ...


def run_task(oss_proxy: OssProxy, repo, pipeline_id, template_name, parameters):
    origin_parameters = {parameter.split("=")[0]: parameter.split("=")[1] for parameter in parameters.split(";")}
    try:
        # todo: 写入文件
        task_key = TASK_QUEUE_FILE_KEY.format(pipeline_id)
        task_data = copy.deepcopy(origin_parameters)
        task_data.update({"pipeline_id": pipeline_id, "repo": repo, "jobname": template_name})
        oss_proxy.put_object(task_key, json.dumps(task_data))
        return True
    except:
        import traceback
        traceback.print_exc()
        print("任务发起失败，出现异常，请联系管理人员处理")
        exit(1)


def get_task_res(oss_proxy: OssProxy, github_pipeline_id):
    try:
        result_key = RESULT_FILE_KEY + "{}.json".format(github_pipeline_id)
        origin_task_data = oss_proxy.get_object(result_key)
        return json.loads(origin_task_data)
    except:
        return


def get_task_stage_output(oss_proxy: OssProxy, github_pipeline_id, start):
    output_key = RESULT_FILE_KEY + "{}.output".format(github_pipeline_id)
    if start:
        output_meta = oss_proxy.get_object_meta(output_key)
        filesize = output_meta.content_length
        if start >= filesize:
            # 超出了之后就不获取了
            start = filesize - 1
    try:
        return oss_proxy.get_object(output_key, _range=(start, None))
    except:
        return b""


def main(pipeline_id, repo, template_name, parameters, timeout):
    ak, sk = os.environ.get("oss_ak") or "", os.environ.get("oss_sk") or ""
    oss_proxy = OssProxy("farm-ce", ak, sk, "http://oss-cn-heyuan.aliyuncs.com")
    run_task(oss_proxy, repo, pipeline_id, template_name, parameters)
    print("create a new task")
    print("working....")
    result = monitor_tasks(oss_proxy, pipeline_id, timeout)
    set_output(OUTPUT)
    if not result:
        exit(1)


def set_output(output):
    values = ";".join(["{}={}".format(key, value) for key, value in output.items()])
    os.system(
        'echo "{}" >> $GITHUB_OUTPUT'.format(values)
    )

if __name__ == "__main__":
    print(sys.argv)
    if len(sys.argv) < 6:
        print("缺失相关参数")
        OUTPUT.update({"success": -1})
        exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])