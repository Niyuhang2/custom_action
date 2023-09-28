# -*- coding: utf-8 -*-
# owner: niyuhang.nyh
import os
import sys
import requests

output = {}

OBFARM_HOST = os.getenv("OBFARM_HOST")
OBFARM_TOKEN = os.getenv("OBFARM_TOKEN")


def run_task():
    ...


def get_task_status_and_output(task_id):
    ...


def main(template_name, parameters):
    res = requests.get("{}/templates".format(OBFARM_HOST), params={"token": OBFARM_TOKEN})
    print(res.text)


def set_output(output):
    values = ";".join(["{}={}".format(key, value) for key, value in output.items()])
    os.system(
        'echo "{}" >> $GITHUB_OUTPUT'.format(values)
    )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("缺失相关参数")
        output.update({"success": -1})
        exit(1)
    main(sys.argv[1], sys.argv[2])
