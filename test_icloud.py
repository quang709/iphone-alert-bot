import os
from pyicloud_ipd import PyiCloudService

alias = "QUANGLVN"
email = os.getenv(f"ICLOUD_{alias}_EMAIL")
password = os.getenv(f"ICLOUD_{alias}_PASS")

print(f"📧 Email: {email}")
print(f"🔑 Password: {password}")

try:
    api = PyiCloudService(email, password)
    if api.requires_2fa:
        print("✅ Đăng nhập thành công, nhưng cần nhập mã 2FA.")
    else:
        print("✅ Đăng nhập thành công, không cần 2FA.")

    devices = api.devices
    print(f"📱 Tìm thấy {len(devices)} thiết bị")
    for dev in devices.values():
        print(f" - {dev['name']} ({dev['modelDisplayName']})")

except Exception as e:
    print("❌ Lỗi đăng nhập:", repr(e))
