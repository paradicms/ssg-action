FROM ghcr.io/paradicms/ssg:latest

ADD action.py /action.py

ENTRYPOINT ["/action.py"]
