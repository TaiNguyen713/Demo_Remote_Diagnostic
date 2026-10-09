import socket
import json
import os
import subprocess
import ctypes
import sys

class DiagnosticReceiver:
    def __init__(self, host="0.0.0.0", port=5005, target_file="car_data_received.sim"):
        self.host = host
        self.port = port
        self.target_file = os.path.abspath(target_file)
        self.is_running = False

    def run_as_admin(self):
        """Yêu cầu quyền Administrator để chỉnh sửa Firewall"""
        if ctypes.windll.shell32.IsUserAnAdmin():
            return True
        else:
            print("[!] Đang yêu cầu quyền Administrator để cấu hình Firewall...")
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            return False

    def setup_firewall(self):
        """Tự động mở port 5005 trên Windows Firewall"""
        try:
            # Kiểm tra xem rule đã tồn tại chưa
            check_cmd = f'netsh advfirewall firewall show rule name="{self.rule_name}"'
            res = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
            
            if "no rules match" in res.stdout.lower() or res.return_code != 0:
                print(f"[*] Đang mở port Firewall UDP {self.port}...")
                add_cmd = (
                    f'netsh advfirewall firewall add rule name="{self.rule_name}" '
                    f'dir=in action=allow protocol=UDP localport={self.port} '
                    f'description="Allow Diagnostic Data from PC1"'
                )
                subprocess.run(add_cmd, shell=True, check=True)
                print("[OK] Đã cấu hình Firewall thành công.")
            else:
                print("[OK] Firewall Rule đã tồn tại, không cần tạo mới.")
        except Exception as e:
            print(f"[Lỗi] Không thể cấu hình Firewall: {e}")

    def _read_sim_file(self):
        """Đọc toàn bộ nội dung file .sim"""
        if not os.path.exists(self.target_file):
            return []
        with open(self.target_file, "r", encoding="utf-8") as f:
            return f.readlines()

    def _write_sim_file(self, lines):
        """Ghi lại toàn bộ nội dung vào file .sim"""
        with open(self.target_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

    def process_update(self, req_new, res_new):
        """Logic: Kiểm tra Request -> So sánh Response -> Cập nhật nếu khác"""
        lines = self._read_sim_file()
        found_req = False
        changed = False
        
        new_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            new_lines.append(line)
            
            # Kiểm tra nếu dòng hiện tại là Request khớp với gói tin nhận được
            if req_new.strip() == line.strip():
                found_req = True
                # Kiểm tra dòng tiếp theo (Response)
                if (i + 1) < len(lines):
                    current_res = lines[i+1].strip()
                    if current_res != res_new.strip():
                        # RULE: Nếu Response thay đổi -> Replace
                        print(f"[UPDATE] Request found. Response changed. Updating...")
                        new_lines.append(res_new.strip() + "\n")
                        print(res_new.strip() + "\n")
                        changed = True
                    else:
                        # RULE: Nếu không đổi -> Giữ nguyên
                        new_lines.append(lines[i+1])
                    i += 2 # Bỏ qua dòng Res cũ đã xử lý
                    continue
                else:
                    # Request nằm cuối file mà chưa có Res -> Add mới Res
                    new_lines.append(res_new.strip() + "\n")
                    changed = True
            i += 1

        # RULE: Nếu chưa có Request này -> Add mới vào cuối file
        if not found_req:
            print(f"[NEW] Request not found. Adding new entry...")
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines[-1] += "\n"
            new_lines.append(req_new.strip() + "\n")
            new_lines.append(res_new.strip() + "\n")
            changed = True

        # Chỉ ghi file khi có sự thay đổi thực sự (tối ưu I/O)
        if changed:
            self._write_sim_file(new_lines)
            print(f"[SUCCESS] File updated.")

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind((self.host, self.port))
            self.is_running = True
            print(f"--- PC2 RECEIVER ONLINE ---")
            print(f"Listening on {self.host}:{self.port}")
            print(f"Target file: {self.target_file}")

            while self.is_running:
                data, addr = self.sock.recvfrom(8192)
                try:
                    payload = json.loads(data.decode('utf-8'))
                    if isinstance(payload, list) and len(payload) == 2:
                        req_head, res_updated = payload
                        self.process_update(req_head, res_updated)
                except Exception as e:
                    print(f"Packet error: {e}")
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.stop()

    def stop(self):
        self.is_running = False
        if hasattr(self, 'sock'):
            self.sock.close()

if __name__ == "__main__":
    receiver = DiagnosticReceiver()
    
    # 1. Yêu cầu quyền Admin
    if receiver.run_as_admin():
        # 2. Nếu đã có quyền Admin thì chạy chương trình
        try:
            receiver.start()
        except KeyboardInterrupt:
            receiver.stop()
            sys.exit(0)