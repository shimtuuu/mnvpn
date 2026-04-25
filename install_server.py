import paramiko
import time
import sys

IP = '31.177.83.208'
PASSWORD = 'qBP3PP&3G11Q7LQr'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

print("Connecting to server...")
try:
    client.connect(IP, username='ubuntu', password=PASSWORD, timeout=10)
    print("Connected successfully!")
except Exception as e:
    print(f"Failed to connect: {e}")
    sys.exit(1)

shell = client.invoke_shell()

def send_cmd(cmd, wait_for=None, timeout=30):
    print(f"Sending: {cmd}")
    shell.send(cmd + '\n')
    out = ""
    start = time.time()
    while True:
        if shell.recv_ready():
            chunk = shell.recv(4096).decode('utf-8', errors='ignore')
            out += chunk
            sys.stdout.write(chunk)
            sys.stdout.flush()
        if wait_for and wait_for in out:
            return out
        if time.time() - start > timeout:
            break
        time.sleep(0.5)
    return out

print("\nGaining root privileges...")
send_cmd("sudo su", wait_for="root@")
time.sleep(1)

print("\nRunning install script...")
send_cmd("bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)")
time.sleep(5) 

out = send_cmd("y", wait_for="Username:")

out = send_cmd("admin", wait_for="Password:") 
out = send_cmd("admin_vpn!!", wait_for="Port:") 
out = send_cmd("2053") 

print("\n\nInstallation commands sent. Waiting a bit for completion...")
time.sleep(10)

client.close()
print("Done! Panel should be running on http://31.177.83.208:2053")
