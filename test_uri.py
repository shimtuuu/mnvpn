import base64

conf = """[Interface]
PrivateKey = CGVOJnSRkXVTU45I9PJSzND78xkyz/1bCahIwf7PdFY=
Address = 10.66.66.3/32,fd42:42:42::3/128
DNS = 1.1.1.1,1.0.0.1
Jc = 10
Jmin = 50
Jmax = 1000
S1 = 28
S2 = 60
S3 = 135
S4 = 54
H1 = 285870806-385870805
H2 = 879968270-979968269
H3 = 1281432796-1381432795
H4 = 2020331556-2120331555

[Peer]
PublicKey = zgCgJf37DnmPGqwOiUBqBsBqMgeW8qxZBYcSw+QoJ3Y=
PresharedKey = m4WvTRG+Cm77rVIhMG8KiGiXuN7RjtAignLD/ytX280=
Endpoint = 31.177.83.208:52093
AllowedIPs = 0.0.0.0/0,::/0"""

b64 = base64.b64encode(conf.encode()).decode()
uri = f"amneziawg://{b64}#minvpn"
print(uri)
