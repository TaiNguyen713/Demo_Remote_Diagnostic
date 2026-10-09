import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import socket, json, threading, time, os, re

class DataSender:
    def __init__(self, target_ip="172.16.10.138", port=5005):
        self.target_ip = target_ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send_to_pc2(self, req_head, res_body):
        try:
            packet = json.dumps([req_head, res_body]).encode('utf-8')
            self.sock.sendto(packet, (self.target_ip, self.port))
        except: pass

class SimulatorUI:
    def __init__(self, root):
        self.root = root
        self.sender = DataSender()
        self.is_syncing = False
        self.frames_db = []
        self._init_ui()
        
    def get_local_ip():
        """Lấy IP của máy hiện tại trong mạng LAN (Ưu tiên dải 192.168.x.x)"""
        try:
            # Cách lấy IP chủ động bằng cách tạo một kết nối giả định
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80)) # Không thực sự gửi dữ liệu đi
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1" # Trả về localhost nếu không có mạng

    def _init_ui(self):
        self.root.title("PC1 - Master Diagnostic Tool (Full Screen Fixed)")
        
        # FIX: Chế độ phóng to tối đa phù hợp với mọi độ phân giải màn hình
        self.root.state('zoomed') 
        
        # --- Top Bar ---
        top = tk.Frame(self.root, bg="#2c3e50", pady=10)
        top.pack(fill=tk.X)
        tk.Button(top, text="📁 LOAD SIM FILE", command=self.load_sim, font=('Arial', 10, 'bold'), bg="#ecf0f1").pack(side=tk.LEFT, padx=20)
        self.lbl_info = tk.Label(top, text="No file loaded", fg="white", bg="#2c3e50", font=('Arial', 10))
        self.lbl_info.pack(side=tk.LEFT)

        # --- Main Layout sử dụng PanedWindow để co giãn ---
        self.main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashwidth=6, bg="#bdc3c7")
        self.main_paned.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

        # Cột Trái: Request List
        left_frame = tk.LabelFrame(self.main_paned, text=" [1] Request List ", font=('Arial', 10, 'bold'))
        self.main_paned.add(left_frame, stretch="always") # Stretch giúp co giãn đều
        
        self.tree_req = ttk.Treeview(left_frame, columns=("ID", "Req"), show="headings")
        self.tree_req.heading("ID", text="ID"); self.tree_req.heading("Req", text="Request String")
        self.tree_req.column("ID", width=50, stretch=tk.NO)
        self.tree_req.pack(expand=True, fill=tk.BOTH)
        self.tree_req.bind("<<TreeviewSelect>>", self.on_req_click)

        # Cột Phải: Response & Config
        right_frame = tk.Frame(self.main_paned)
        self.main_paned.add(right_frame, stretch="always")

        # Khối Response
        res_labelframe = tk.LabelFrame(right_frame, text=" [2] Response Block ", font=('Arial', 10, 'bold'))
        res_labelframe.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)
        
        self.tree_res = ttk.Treeview(res_labelframe, columns=("Res"), show="headings")
        self.tree_res.heading("Res", text="Response Content (Tab Formatted)")
        self.tree_res.pack(expand=True, fill=tk.BOTH)
        self.tree_res.bind("<<TreeviewSelect>>", self.on_res_click)

        # Khối Config Bytes (Cố định chiều cao ở dưới)
        cfg_frame = tk.LabelFrame(right_frame, text=" [3] Byte Increment Configuration ", font=('Arial', 10, 'bold'))
        cfg_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Hiển thị B0-B7
        self.byte_labels = []
        grid_frame = tk.Frame(cfg_frame)
        grid_frame.pack(pady=10)
        for i in range(8):
            f = tk.Frame(grid_frame, relief="ridge", bd=2, bg="#fdfefe")
            f.grid(row=0, column=i, padx=5)
            tk.Label(f, text=f"B{i}", font=('Arial', 8), bg="#fdfefe").pack()
            l = tk.Label(f, text="00", font=('Consolas', 14, 'bold'), width=5, fg="#2980b9", bg="white")
            l.pack(); self.byte_labels.append(l)

        # Nhập Min/Max cho 3 Rule
        self.configs = []
        for i in range(3):
            r = tk.Frame(cfg_frame); r.pack(pady=3)
            tk.Label(r, text=f"Rule {i+1} Index:").pack(side=tk.LEFT)
            idx = tk.Entry(r, width=4, justify='center'); idx.pack(side=tk.LEFT, padx=5)
            tk.Label(r, text="Min:").pack(side=tk.LEFT)
            mi = tk.Entry(r, width=6, justify='center'); mi.insert(0,"00"); mi.pack(side=tk.LEFT, padx=5)
            tk.Label(r, text="Max:").pack(side=tk.LEFT)
            ma = tk.Entry(r, width=6, justify='center'); ma.insert(0,"FF"); ma.pack(side=tk.LEFT, padx=5)
            self.configs.append({'idx': idx, 'min': mi, 'max': ma})

        # Nút bấm đồng bộ
        self.btn_sync = tk.Button(self.root, text="START SYNC (1ms)", bg="#27ae60", fg="white", 
                                  font=('Arial', 12, 'bold'), height=3, command=self.toggle_sync)
        self.btn_sync.pack(fill=tk.X, padx=10, pady=10)

    def load_sim(self):
        path = filedialog.askopenfilename()
        if not path: return
        self.frames_db = []
        self.tree_req.delete(*self.tree_req.get_children())
        with open(path, 'r', encoding='utf-8') as f:
            curr = None
            for line in f:
                line = line.strip()
                is_flow = bool(re.search(r'[qQ]--.*08\s+30', line))
                if "Req>" in line and not is_flow:
                    curr = {'id': len(self.frames_db)+1, 'req': line, 'res': []}
                    self.frames_db.append(curr)
                    self.tree_req.insert("", "end", values=(curr['id'], line))
                elif curr and ("Res<" in line or is_flow):
                    curr['res'].append(line)

    def on_req_click(self, e):
        sel = self.tree_req.selection()
        if not sel: return
        idx = int(self.tree_req.item(sel[0], "values")[0]) - 1
        self.tree_res.delete(*self.tree_res.get_children())
        for r in self.frames_db[idx]['res']: self.tree_res.insert("", "end", values=(r,))

    def on_res_click(self, e):
        sel = self.tree_res.selection()
        if not sel: return
        res_text = self.tree_res.item(sel[0], "values")[0]
        
        # 1. Tách lấy phần trước dấu Tab chứa NONE (phần dữ liệu chính) và Tách theo khoảng trắng để lấy danh sách các token
        # Ví dụ: 410D0000000000
        main_data_part = res_text.split('\t')[3].replace(" ","")[10:]
        
        # 2. Lấy đúng 8 token cuối cùng (đây chính là 8 byte dữ liệu)
        split_hex_string  = lambda s: [s[i:i+2] for i in range(0, len(s), 2)]
        data_part = split_hex_string(main_data_part)
        
        # Cập nhật lên UI
        for i in range(8):
            val = data_part[i] if i < len(data_part) else "00"
            self.byte_labels[i].config(text=val, fg="blue")

    def toggle_sync(self):
        if not self.tree_res.selection(): 
            messagebox.showwarning("Lỗi", "Vui lòng chọn 1 dòng Response!")
            return
            
        if not self.is_syncing:
            # Bắt đầu Sync
            self.is_syncing = True
            self.btn_sync.config(text="STOP SYNC", bg="#c0392b")
            # Khởi chạy thread mới
            self.sync_thread = threading.Thread(target=self.sync_loop, daemon=True)
            self.sync_thread.start()
        else:
            # Dừng Sync
            self.is_syncing = False
            self.btn_sync.config(text="START SYNC (1ms)", bg="#27ae60")
            # Không cần gọi thread.join() ở đây để tránh treo UI, 
            # vòng lặp while trong sync_loop sẽ tự thoát.

    def sync_loop(self):
        try:
            req_selection = self.tree_req.selection()
            res_selection = self.tree_res.selection()
            if not req_selection or not res_selection:
                self.is_syncing = False
            
            req_head = self.tree_req.item(self.tree_req.selection()[0], "values")[1]
            res_raw = self.tree_res.item(self.tree_res.selection()[0], "values")[0]
            
            rules = []
            for c in self.configs:
                try: rules.append({'idx': int(c['idx'].get()), 'min': int(c['min'].get(), 16), 'max': int(c['max'].get(), 16), 'curr': int(c['min'].get(), 16)})
                except: pass

            last_inc = time.time()
            while self.is_syncing:
                if time.time() - last_inc >= 0.5:
                    for r in rules: r['curr'] = r['min'] if r['curr'] >= r['max'] else r['curr'] + 1
                    last_inc = time.time()

                # --- LOGIC ĐỊNH DẠNG MỚI (FIXED) ---
                # 1. Tách chuỗi theo các Tab (\t) để giữ nguyên phần đuôi NONE 0 0
                parts = res_raw.split('\t')
                data_str = parts[3] # Phần chứa Res<... data ...
                
                # 2. Tách phần nội dung Hex
                # Tìm vị trí bắt đầu của 8 byte dữ liệu (thường sau ID và DLC)
                hex_tokens = re.findall(r'[0-9A-Fa-f]{2,8}', data_str)
                # Giả định: 8 byte data nằm ở các token cuối cùng. 
                # Chúng ta sẽ giữ nguyên phần đầu của data_str và chỉ thay thế 8 byte cuối.
                
                main_tokens = data_str.split() # Tách theo khoảng trắng
                # main_tokens thường có dạng: ['INFO_DATABASE', '=', 'Res<2', '000007E8', '08', '03', '41', '0D', '2F', ...]
                
                # 3. Ghi đè các byte dữ liệu mới (vị trí từ cuối đếm ngược)
                for r in rules:
                    # 8 byte dữ liệu cuối nằm từ index -8 đến -1
                    target_idx = len(main_tokens) - (8 - r['idx'])
                    if target_idx < len(main_tokens):
                        main_tokens[target_idx] = f"{r['curr']:02X}"

                # 4. Tái cấu trúc lại chuỗi theo đúng format của bạn
                # Giữ nguyên khoảng cách Tab ban đầu
                new_data_part = " ".join(main_tokens[:3]) +" "+ main_tokens[3] + " " + main_tokens[4] + " " + " ".join(main_tokens[5:])
                final_res = parts[0] +"\t\t\t" + new_data_part + " \t" + "\t".join(parts[4:])

                self.sender.send_to_pc2(req_head, final_res)
                print(final_res)
                for r in rules: self.byte_labels[r['idx']].config(text=f"{r['curr']:02X}", fg="red")
                time.sleep(0.001)
        except Exception as e:
            print(f"Sync Loop Error: {e}")
            self.is_syncing = False
        finally:
            # Đảm bảo nút bấm quay về trạng thái ban đầu nếu có lỗi
            self.root.after(0, lambda: self.btn_sync.config(text="START SYNC (1ms)", bg="#27ae60"))
            
            
class NetworkManager:
    @staticmethod
    def get_local_ip():
        """Tự động phát hiện IP đang hoạt động trong mạng LAN"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    @staticmethod
    def manage_config(file_name="network_cfg.json", default_ip="127.0.0.1"):
        """Tự tạo file config nếu chưa có, hoặc đọc file cũ"""
        if not os.path.exists(file_name):
            config = {"target_ip": default_ip, "port": 5005}
            with open(file_name, "w") as f:
                json.dump(config, f, indent=4)
            return config
        else:
            with open(file_name, "r") as f:
                return json.load(f)

    @staticmethod
    def save_config(ip, file_name="network_cfg.json"):
        """Lưu IP mới vào file config"""
        config = {"target_ip": ip, "port": 5005}
        with open(file_name, "w") as f:
            json.dump(config, f, indent=4)
            
            
if __name__ == "__main__":
    root = tk.Tk()
    app = SimulatorUI(root)
    root.mainloop()