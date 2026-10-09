import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import socket, json, threading, time, os, re

class DataSender:
    def __init__(self, target_ip="127.0.0.1", port=5005):
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
        self.is_updating = False
        self.frames_db = [] # Lưu toàn bộ data file
        self.active_tasks = {} # Lưu trạng thái Byte của các frame đang chạy
        self._setup_ui()

    def _setup_ui(self):
        self.root.title("PC1 - Multi-Frame Master (V8.0)")
        self.root.state('zoomed')
        
        # --- Top Bar ---
        top = tk.Frame(self.root, bg="#2c3e50", pady=10)
        top.pack(fill=tk.X)
        tk.Button(top, text="📁 LOAD SIM", command=self.load_sim, font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=20)
        self.lbl_info = tk.Label(top, text="No file", fg="white", bg="#2c3e50").pack(side=tk.LEFT)

        # --- Main Layout ---
        self.main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashwidth=6)
        self.main_paned.pack(expand=True, fill=tk.BOTH, padx=5, pady=5)

        # Cột Trái: Danh sách Request với Checkbox (giả lập bằng tag)
        left_frame = tk.LabelFrame(self.main_paned, text=" [1] Request List (Click to Select/Deselect) ")
        self.main_paned.add(left_frame, stretch="always")
        
        self.tree_req = ttk.Treeview(left_frame, columns=("Sync", "ID", "Req"), show="headings")
        self.tree_req.heading("Sync", text="Sync"); self.tree_req.heading("ID", text="ID"); self.tree_req.heading("Req", text="Request")
        self.tree_req.column("Sync", width=60, anchor="center"); self.tree_req.column("ID", width=50); self.tree_req.column("Req", width=400)
        self.tree_req.pack(expand=True, fill=tk.BOTH)
        
        # Event: Double Click để bật/tắt Sync cho Frame đó
        self.tree_req.bind("<Double-1>", self.toggle_frame_selection)
        self.tree_req.bind("<<TreeviewSelect>>", self.on_req_select)

        # Cột Phải: Response & Rules
        right_frame = tk.Frame(self.main_paned)
        self.main_paned.add(right_frame, stretch="always")

        self.tree_res = ttk.Treeview(right_frame, columns=("Res"), show="headings", height=10)
        self.tree_res.heading("Res", text="Response (Select one for each Request)"); self.tree_res.pack(fill=tk.X, padx=5, pady=5)

        # Config Rules (Áp dụng cho Frame đang chọn ở Treeview)
        cfg_frame = tk.LabelFrame(right_frame, text=" [3] Increment Rules (For Selected Frame) ")
        cfg_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.rule_entries = []
        for i in range(3):
            r = tk.Frame(cfg_frame); r.pack(pady=2)
            tk.Label(r, text=f"Rule {i+1} - Index:").pack(side=tk.LEFT)
            idx = tk.Entry(r, width=3); idx.pack(side=tk.LEFT, padx=2)
            tk.Label(r, text="Min:").pack(side=tk.LEFT); mi = tk.Entry(r, width=5); mi.insert(0,"00"); mi.pack(side=tk.LEFT)
            tk.Label(r, text="Max:").pack(side=tk.LEFT); ma = tk.Entry(r, width=5); ma.insert(0,"FF"); ma.pack(side=tk.LEFT)
            btn_save = tk.Button(r, text="Set", command=lambda x=i: self.save_rule_to_frame(x))
            btn_save.pack(side=tk.LEFT, padx=5)
            self.rule_entries.append({'idx': idx, 'min': mi, 'max': ma})

        # --- Control Buttons ---
        btn_frame = tk.Frame(self.root, pady=10)
        btn_frame.pack(fill=tk.X)
        self.btn_sync = tk.Button(btn_frame, text="START MULTI-SYNC", bg="#27ae60", fg="white", font=('Arial', 12, 'bold'), height=2, command=self.toggle_all_sync)
        self.btn_sync.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.btn_update = tk.Button(btn_frame, text="AUTO UPDATE (OFF)", bg="#7f8c8d", fg="white", font=('Arial', 12, 'bold'), height=2, command=self.toggle_auto_update)
        self.btn_update.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

    def load_sim(self):
        path = filedialog.askopenfilename()
        if not path: return
        self.frames_db = []
        self.tree_req.delete(*self.tree_req.get_children())
        with open(path, 'r', encoding='utf-8') as f:
            curr = None
            for line in f:
                line = line.strip()
                if "Req>" in line and not "08 30" in line:
                    # Mỗi frame giờ có thêm list 'rules' và 'selected_res'
                    curr = {'req': line, 'res_list': [], 'rules': [], 'sel_res_idx': 0, 'sync': False}
                    self.frames_db.append(curr)
                elif curr and "Res<" in line:
                    curr['res_list'].append(line)
        self._refresh_req_tree()

    def _refresh_req_tree(self):
        self.tree_req.delete(*self.tree_req.get_children())
        for i, f in enumerate(self.frames_db):
            status = " [ X ] " if f['sync'] else " [   ] "
            self.tree_req.insert("", "end", iid=i, values=(status, i+1, f['req']))

    def toggle_frame_selection(self, event):
        item_id = self.tree_req.identify_row(event.y)
        if item_id:
            idx = int(item_id)
            self.frames_db[idx]['sync'] = not self.frames_db[idx]['sync']
            self._refresh_req_tree()

    def on_req_select(self, e):
        sel = self.tree_req.selection()
        if not sel: return
        idx = int(sel[0])
        frame = self.frames_db[idx]
        self.tree_res.delete(*self.tree_res.get_children())
        for r in frame['res_list']: self.tree_res.insert("", "end", values=(r,))
        # Load rules cũ của frame này lên Entry
        for i in range(3):
            self.rule_entries[i]['idx'].delete(0, tk.END)
            if i < len(frame['rules']):
                self.rule_entries[i]['idx'].insert(0, frame['rules'][i]['idx'])

    def save_rule_to_frame(self, rule_slot):
        sel = self.tree_req.selection()
        if not sel: return
        idx = int(sel[0])
        r_entry = self.rule_entries[rule_slot]
        new_rule = {
            'idx': int(r_entry['idx'].get()),
            'min': int(r_entry['min'].get(), 16),
            'max': int(r_entry['max'].get(), 16),
            'curr': int(r_entry['min'].get(), 16)
        }
        # Cập nhật hoặc thêm mới rule cho frame
        if rule_slot < len(self.frames_db[idx]['rules']):
            self.frames_db[idx]['rules'][rule_slot] = new_rule
        else:
            self.frames_db[idx]['rules'].append(new_rule)
        messagebox.showinfo("OK", f"Rule saved for Frame {idx+1}")

    def toggle_all_sync(self):
        self.is_syncing = not self.is_syncing
        if self.is_syncing:
            self.btn_sync.config(text="STOP ALL", bg="red")
            threading.Thread(target=self.multi_sync_loop, daemon=True).start()
        else:
            self.btn_sync.config(text="START MULTI-SYNC", bg="green")
            self.is_updating = False

    def toggle_auto_update(self):
        self.is_updating = not self.is_updating
        self.btn_update.config(text="AUTO UPDATE (ON)" if self.is_updating else "AUTO UPDATE (OFF)", 
                               bg="#f39c12" if self.is_updating else "#7f8c8d")

    def multi_sync_loop(self):
        last_inc = time.time()
        while self.is_syncing:
            # Duyệt qua tất cả Frame được tích [ X ]
            for frame in self.frames_db:
                if not frame['sync'] or not frame['res_list']: continue
                
                # 1. Logic Update Byte (0.5s)
                if self.is_updating and (time.time() - last_inc >= 0.5):
                    for r in frame['rules']:
                        r['curr'] = r['min'] if r['curr'] >= r['max'] else r['curr'] + 1
                    last_inc = time.time()

                # 2. Render Data cho từng Frame
                res_raw = frame['res_list'][0] # Mặc định lấy res đầu tiên
                parts = res_raw.split('\t')
                tokens = parts[0].split()
                
                for r in frame['rules']:
                    t_idx = len(tokens) - (8 - r['idx'])
                    if 0 <= t_idx < len(tokens):
                        tokens[t_idx] = f"{r['curr']:02X}"

                # Format đúng chuẩn của bạn
                new_data = " ".join(tokens[:3]) + "\t\t" + tokens[3] + " " + tokens[4] + " " + " ".join(tokens[5:])
                final_res = new_data + "\t" + "\t".join(parts[1:])
                
                # Gửi từng Frame ra UDP
                self.sender.send_to_pc2(frame['req'], final_res)
            
            time.sleep(0.001) # Tổng tốc độ vòng lặp quét các frame là 1ms

if __name__ == "__main__":
    root = tk.Tk(); app = SimulatorUI(root); root.mainloop()