# -*- coding: utf-8 -*-
# owner: niyuhang.nyh
import os
import sys
import time
import requests
from enum import Enum
from urllib.parse import urljoin

output = {}

OBFARM_HOST = os.getenv("OBFARM_HOST")
OBFARM_TOKEN = os.getenv("OBFARM_TOKEN")


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


def run_task(template_name, parameters):
    run_parameters = {
       "parameters": {parameter.split("=")[0]: parameter.split("=")[1] for parameter in parameters.split(";")}
    }
    url = OBFARM_HOST + "templates/{}/tasks".format(template_name)
    response = request(
        "POST",
        url,
        params={"token": OBFARM_TOKEN},
        payload=run_parameters
    )
    try:
        task_id = response.json()["data"]["id"]
        return task_id
    except:
        import traceback
        traceback.print_exc()
        print("任务发起失败，出现异常，请联系管理人员处理")
        exit(1)


def get_task_res(task_id):
    url = OBFARM_HOST + "tasks/{}".format(task_id)
    response = request(
        "GET",
        url,
        params={"token": OBFARM_TOKEN},
        without_check_status=True,
        timeout=60
    )
    if not response:
        return
    else:
        return response.json()["data"]


def get_task_stage_output(task_id, stage_id):
    url = OBFARM_HOST + "tasks/{}/stages/{}/output".format(task_id, stage_id)
    response = request(
        "GET",
        url,
        params={"token": OBFARM_TOKEN},
        without_check_status=True,
        timeout=60
    )
    if not response:
        return
    else:
        return response.text


def generate_the_output(task_id, stage_id):
    end_line = None
    # 每次刷新20
    # todo: 任务结束就退出
    while 1:
        # todo: 验证下是否可以更新
        # 检查任务是不是结束了
        task_data = get_task_res(task_id)
        current_stage = next(filter(lambda stage: str(stage["id"]) == str(stage_id), task_data["stage_info"]), None)
        if not current_stage:
            return
        current_stage_status = current_stage["status"]
        # 如果第一次进来就是直接失败，需要获取一下日志输出
        if end_line is not None and (current_stage_status <= TaskStatusEnum.fail.value or current_stage_status >= TaskStatusEnum.success.value):
            return
        output = get_task_stage_output(task_id, stage_id)
        outputs = output.split("\n")
        if output is None:
            continue
        if not end_line:
            total_length = len(outputs)
            if total_length >= 20:
                start_line = total_length - 20
            else:
                start_line = 0
        else:
            start_line = end_line + 1
        result = "\n".join(outputs[start_line:])
        if result and result != "\n":
            print(result)
        end_line = len(outputs)

        time.sleep(0.2)


def monitor_tasks(task_id, timeout):
    end_time = time.time() + int(timeout)
    # 监控任务，并且不断的打印输出，直到任务结束
    while time.time() <= end_time:
        task_data = get_task_res(task_id)
        task_status = task_data["status"]
        stages = task_data["stage_info"]
        # 不断的开始展示每一个stage的，直到任务结束
        for stage in stages:
            generate_the_output(task_id, stage["id"])

        if task_status is not None:
            if task_status <= TaskStatusEnum.fail.value or task_status >= TaskStatusEnum.success.value:
                print(TaskStatusEnum._value2member_map_[task_status])
                break

        time.sleep(5)
    else:
        # todo: 杀死任务
        ...


def main(template_name, parameters, timeout):
    task_id = run_task(template_name, parameters)
    print("create task, task_id:{}".format(task_id))
    monitor_tasks(task_id, timeout)


def set_output(output):
    values = ";".join(["{}={}".format(key, value) for key, value in output.items()])
    os.system(
        'echo "{}" >> $GITHUB_OUTPUT'.format(values)
    )


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("缺失相关参数")
        output.update({"success": -1})
        exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
