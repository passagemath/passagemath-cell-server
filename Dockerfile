# docker build --tag=passagemath-cell-server .
# docker run --publish 8888:8888 passagemath-cell-server
FROM ubuntu:noble
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install --yes python3 python3-pip npm && apt-get clean
ADD . /passagemath-cell-server
WORKDIR /passagemath-cell-server
RUN pip install --break-system-packages -e .
RUN sage -sh -c make
ENTRYPOINT sage-cell-server
