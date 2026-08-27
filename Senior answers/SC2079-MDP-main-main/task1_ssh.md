Do the command below to establish keys from raspberry pi:
# Step 1 - generate key
```bash
ssh-keygen -t rsa -f "$env:USERPROFILE\.ssh\id_rsa"
```

- Noneed passpharse

# Step 2 - copy to RPi (type 'pi' when prompted - last time ever)
```bash
type "$env:USERPROFILE\.ssh\id_rsa.pub" | ssh mdp@192.168.20.1 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

# Step 3 - run
``` bash
.\task1_ssh.ps1
```
It should not prompt you any password.