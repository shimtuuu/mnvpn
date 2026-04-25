import paramiko
import time
IP = '31.177.83.208'
KEY_FILE = 'vps_key.pem'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(IP, username='root', key_filename=KEY_FILE, timeout=10)
shell = client.invoke_shell()

shell.send("./amneziawg-install.sh\n")
out = ""
start = time.time()
while time.time() - start < 5:
    if shell.recv_ready():
        out += shell.recv(4096).decode('utf-8', errors='ignore')
    time.sleep(0.5)
print(repr(out))

client.close()
