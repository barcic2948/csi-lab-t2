sudo socat PTY,link=/dev/ttyV0,raw,echo=0 PTY,link=/dev/ttyV1,raw,echo=0 &
sudo chmod 666 /dev/ttyV0 /dev/ttyV1