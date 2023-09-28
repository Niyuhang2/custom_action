# Container image that runs your code
FROM python:3.6

RUN pip3 install requests -i https://mirrors.aliyun.com/pypi/simple/
# Copies your code file from your action repository to the filesystem path `/` of the container
COPY farm2.py /farm2.py

# Code file to execute when the docker container starts up (`entrypoint.sh`)
ENTRYPOINT ["python3", "farm2.py"]
