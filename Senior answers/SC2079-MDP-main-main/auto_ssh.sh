#!/usr/bin/env bash
# Usage: ./run_task1_expect.sh
# Requires: expect installed (brew install expect)

REMOTE_USER="mdp"
REMOTE_HOST="192.168.20.1"
REMOTE_PASS="pi"
REMOTE_DIR="mdp"
# Put python in the foreground of the TTY so it receives SIGINT
REMOTE_CMD="cd ${REMOTE_DIR} && sudo bash -lc 'exec python3 task2.py'"

expect <<EOF
  # Expect script begins here
  set timeout -1

  # Forward local Ctrl-C to the remote program (send ASCII ETX)
  trap {
    if {[info exists spawn_id]} {
      send \003
    }
  } SIGINT

  # Start SSH with a TTY and run the command directly
  spawn ssh -tt -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} "${REMOTE_CMD}"

  # Handle host key prompt, SSH password, and sudo password
  expect {
    -re "Are you sure you want to continue connecting.*" {
      send "yes\r"
      exp_continue
    }
    -re "(?i)password:" {
      # Matches either SSH password or sudo password prompt
      send "${REMOTE_PASS}\r"
      exp_continue
    }
    eof
  }
EOF